"""Generate a KiCad PCB file from a KiCad netlist and a placement.

Usage (from the project root):
    python3 tools/pcb/pcbgen.py --netlist netlist.net --board "Schematic/4ch Mixer.kicad_pcb" \
        --layout tools/pcb/layout_mixer.py

The layout module defines OUTLINE (x0, y0, x1, y1) and PLACE, a dict of
reference -> (x, y, rotation_deg). Parts not listed in PLACE are placed by
the simple grid packer in this module.
"""
import argparse
import importlib.util
import os
import re
import uuid

import sexpr
from sexpr import Str

KICAD_FP_DIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
PROJECT_FP_DIRS = []  # filled from the project's fp-lib-table if needed


def load_netlist(path):
    tree = sexpr.parse(open(path, encoding="utf-8").read())
    comps = {}
    comps_node = sexpr.find_one(tree, "components")
    for comp in sexpr.find_all(comps_node, "comp"):
        ref = str(sexpr.find_one(comp, "ref")[1])
        value = str(sexpr.find_one(comp, "value")[1])
        fp = str(sexpr.find_one(comp, "footprint")[1]) if sexpr.find_one(comp, "footprint") else ""
        comps[ref] = {"value": value, "footprint": fp}
    nets = {}
    nets_node = sexpr.find_one(tree, "nets")
    for net in sexpr.find_all(nets_node, "net"):
        name = str(sexpr.find_one(net, "name")[1])
        nodes = []
        for node in sexpr.find_all(net, "node"):
            ref = str(sexpr.find_one(node, "ref")[1])
            pin = str(sexpr.find_one(node, "pin")[1])
            nodes.append((ref, pin))
        nets[name] = nodes
    return comps, nets


def footprint_file(fpid, extra_dirs=()):
    lib, name = fpid.split(":", 1)
    for base in list(extra_dirs) + [KICAD_FP_DIR]:
        path = os.path.join(base, lib + ".pretty", name + ".kicad_mod")
        if os.path.exists(path):
            return path
    raise FileNotFoundError(fpid)


def load_footprint(fpid, extra_dirs=()):
    return sexpr.parse(open(footprint_file(fpid, extra_dirs), encoding="utf-8").read())


def pads_of(fp_tree):
    """Return list of (name, x, y, w, h) in footprint-local coordinates (unrotated)."""
    out = []
    for pad in sexpr.find_all(fp_tree, "pad"):
        name = str(pad[1])
        at = sexpr.find_one(pad, "at")
        size = sexpr.find_one(pad, "size")
        x, y = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        w, h = float(size[1]), float(size[2])
        if rot in (90.0, 270.0):
            w, h = h, w
        out.append((name, x, y, w, h))
    return out


def courtyard_points(fp_tree):
    """Points of the F.CrtYd outline in footprint-local coordinates."""
    pts = []
    for child in fp_tree[2:]:
        if not isinstance(child, list) or not child or child[0] not in (
                "fp_rect", "fp_line", "fp_circle", "fp_poly"):
            continue
        layer = sexpr.find_one(child, "layer")
        if not layer or layer[1] != "F.CrtYd":
            continue
        if child[0] in ("fp_rect", "fp_line"):
            for key in ("start", "end"):
                n = sexpr.find_one(child, key)
                pts.append((float(n[1]), float(n[2])))
        elif child[0] == "fp_circle":
            c = sexpr.find_one(child, "center")
            r = float(sexpr.find_one(child, "end")[1]) - float(c[1])
            cx, cy = float(c[1]), float(c[2])
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        else:
            for p in sexpr.find_one(child, "pts")[1:]:
                pts.append((float(p[1]), float(p[2])))
    return pts


def bbox_of(fp_tree, x, y, rot, margin=0.5):
    """Axis-aligned bounding box after rotation/translation, plus margin.

    Uses the courtyard when the footprint has one, otherwise the pads.
    """
    xs, ys = [], []
    for px, py in courtyard_points(fp_tree):
        rx, ry = rotate(px, py, rot)
        xs.append(rx)
        ys.append(ry)
    if not xs:
        for name, px, py, w, h in pads_of(fp_tree):
            rx, ry = rotate(px, py, rot)
            xs += [rx - w / 2, rx + w / 2]
            ys += [ry - h / 2, ry + h / 2]
    if not xs:
        return (x - 1, y - 1, x + 1, y + 1)
    return (x + min(xs) - margin, y + min(ys) - margin,
            x + max(xs) + margin, y + max(ys) + margin)


def rotate(x, y, deg):
    """Rotate a point counter-clockwise by deg as KiCad does (y axis down)."""
    import math
    a = math.radians(-deg)  # KiCad rotation is clockwise on screen (y down)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def wrap_footprint(fp_tree, ref, value, x, y, rot, net_index, layer="F.Cu"):
    """Turn a library footprint into a board footprint at (x, y, rot)."""
    fpid = fp_tree[1]
    out = ["footprint", fpid, ["layer", Str(layer)], ["uuid", Str(str(uuid.uuid4()))],
           ["at", x, y] + ([rot] if rot else [])]
    ref_prop = ["property", Str("Reference"), Str(ref),
                ["at", 0, -2.5, 0], ["layer", Str("F.SilkS")],
                ["effects", ["font", ["size", 1, 1], ["thickness", 0.15]]]]
    val_prop = ["property", Str("Value"), Str(value),
                ["at", 0, 2.5, 0], ["layer", Str("F.Fab")],
                ["effects", ["font", ["size", 1, 1], ["thickness", 0.15]]]]
    out += [ref_prop, val_prop]
    for child in fp_tree[2:]:
        if not isinstance(child, list) or not child:
            continue
        head = child[0]
        if head in ("layer", "version", "generator", "descr", "tags", "fp_text",
                    "uuid", "path", "sheetname", "sheetfile"):
            continue
        if head == "property":
            continue
        if head == "pad":
            pad = list(child)
            name = str(pad[1])
            nets = net_index.get(name)
            if nets is not None:
                code, netname = nets
                pad.append(["net", code, Str(netname)])
            pad.append(["uuid", Str(str(uuid.uuid4()))])
            out.append(pad)
        else:
            out.append(child)
    return out


def edge_cuts(x0, y0, x1, y1):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    out = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        out.append(["gr_line", ["start", ax, ay], ["end", bx, by],
                    ["stroke", ["width", 0.05], ["type", "default"]],
                    ["layer", Str("Edge.Cuts")], ["uuid", Str(str(uuid.uuid4()))]])
    return out


def pack_remaining(placed_boxes, refs, footprints, outline, start_grid=(2.0, 2.0)):
    """Greedy grid packer for parts without a planned position."""
    x0, y0, x1, y1 = outline
    gx, gy = start_grid
    result = {}
    boxes = list(placed_boxes)
    for ref in refs:
        fp = footprints[ref]
        placed = False
        y = y0 + 3
        while y < y1 - 3 and not placed:
            x = x0 + 2.5
            while x < x1 - 2.5 and not placed:
                bx = bbox_of(fp, x, y, 0)
                inside = bx[0] >= x0 and bx[2] <= x1 and bx[1] >= y0 and bx[3] <= y1
                clear = all(bx[2] <= b[0] or bx[0] >= b[2] or bx[3] <= b[1] or bx[1] >= b[3] for b in boxes)
                if inside and clear:
                    result[ref] = (x, y, 0)
                    boxes.append(bx)
                    placed = True
                x += gx
            y += gy
        if not placed:
            raise RuntimeError("no room for " + ref)
    return result


def build(netlist_path, board_template, layout_path, out_path, fp_dirs=()):
    spec = importlib.util.spec_from_file_location("layout", layout_path)
    layout = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(layout)

    comps, nets = load_netlist(netlist_path)
    template = sexpr.parse(open(board_template, encoding="utf-8").read())
    layers = sexpr.find_one(template, "layers")
    setup = sexpr.find_one(template, "setup")

    # net codes
    net_names = sorted(n for n in nets if n)
    net_codes = {name: i + 1 for i, name in enumerate(net_names)}
    net_decl = [["net", 0, Str("")]] + [["net", net_codes[n], Str(n)] for n in net_names]

    # pad -> (code, netname) per ref
    pad_nets = {}
    for netname, nodes in nets.items():
        if not netname:
            continue
        for ref, pin in nodes:
            pad_nets.setdefault(ref, {})[pin] = (net_codes[netname], netname)

    footprints = {}
    for ref, c in comps.items():
        if not c["footprint"]:
            continue
        footprints[ref] = load_footprint(c["footprint"], fp_dirs)

    place = dict(layout.PLACE)
    outline = layout.OUTLINE
    boxes = [bbox_of(footprints[r], x, y, rot) for r, (x, y, rot) in place.items() if r in footprints]
    remaining = [r for r in sorted(footprints, key=lambda s: (re.sub(r"\d+", "", s), int(re.sub(r"\D", "", s) or 0)))
                 if r not in place]
    if remaining:
        place.update(pack_remaining(boxes, remaining, footprints, outline))

    body = [["version", 20260206], ["generator", Str("pcbgen")],
            ["general", ["thickness", 1.6]], ["paper", Str("A4")], layers, setup]
    body += net_decl
    body += edge_cuts(*outline)
    for ref in sorted(footprints):
        x, y, rot = place[ref]
        c = comps[ref]
        index = pad_nets.get(ref, {})
        fp = wrap_footprint(footprints[ref], ref, c["value"], x, y, rot, index)
        body.append(fp)

    board = ["kicad_pcb"] + body
    text = sexpr.dumps(board) + "\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return place


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--template", required=True, help="existing .kicad_pcb to copy layers/setup from")
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fp-dir", action="append", default=[], help="extra .pretty parent folders")
    a = ap.parse_args()
    placed = build(a.netlist, a.template, a.layout, a.out, a.fp_dir)
    print("placed", len(placed), "parts")
