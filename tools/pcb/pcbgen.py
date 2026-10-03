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


def bbox_of(fp_tree, x, y, rot, margin=0.5, side="F", pads_only=False):
    """Axis-aligned bounding box after flip/rotation/translation, plus margin.

    side="B" mirrors the footprint across its y axis first (SMD on the back).
    Uses the courtyard when the footprint has one, otherwise the pads.
    """
    # KiCad mirrors back-side parts and turns them the other way: the global
    # position is mirror-x then rotate by -rot (checked against drill holes).
    back = side in ("B", "B.Cu")
    flip = -1.0 if back else 1.0
    eff_rot = -rot if back else rot
    xs, ys = [], []
    if not pads_only:
        for px, py in courtyard_points(fp_tree):
            rx, ry = rotate(flip * px, py, eff_rot)
            xs.append(rx)
            ys.append(ry)
    if not xs:
        for name, px, py, w, h in pads_of(fp_tree):
            rx, ry = rotate(flip * px, py, eff_rot)
            xs += [rx - w / 2, rx + w / 2]
            ys += [ry - h / 2, ry + h / 2]
    if not xs:
        return (x - 1, y - 1, x + 1, y + 1)
    return (x + min(xs) - margin, y + min(ys) - margin,
            x + max(xs) + margin, y + max(ys) + margin)


def is_smd(fp_tree):
    return any(str(pad[2]) == "smd" for pad in sexpr.find_all(fp_tree, "pad") if len(pad) > 2)


SWAP = {"F.Cu": "B.Cu", "B.Cu": "F.Cu", "F.Mask": "B.Mask", "B.Mask": "F.Mask",
        "F.Paste": "B.Paste", "B.Paste": "F.Paste", "F.SilkS": "B.SilkS", "B.SilkS": "F.SilkS",
        "F.CrtYd": "B.CrtYd", "B.CrtYd": "F.CrtYd", "F.Fab": "B.Fab", "B.Fab": "F.Fab",
        "F.Adhes": "B.Adhes", "B.Adhes": "F.Adhes"}


def mirror_tree(node):
    """Mirror a footprint subtree across its y axis (for a back-side part)."""
    if not isinstance(node, list):
        if isinstance(node, Str) and node in SWAP:
            return Str(SWAP[node])
        return node
    if not node:
        return node
    head = node[0]
    if head == "at" and len(node) >= 3:
        rot = -float(node[3]) if len(node) > 3 else None
        out = ["at", -float(node[1]), float(node[2])] + ([rot] if rot is not None else [])
        return out
    if head in ("start", "end", "center", "mid") and len(node) >= 3:
        return [head, -float(node[1]), float(node[2])]
    if head == "pts":
        return ["pts"] + [["xy", -float(p[1]), float(p[2])] for p in node[1:]]
    return [mirror_tree(x) for x in node]


def rotate(x, y, deg):
    """Rotate a point counter-clockwise by deg as KiCad does (y axis down)."""
    import math
    a = math.radians(-deg)  # KiCad rotation is clockwise on screen (y down)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def wrap_footprint(fp_tree, ref, value, x, y, rot, net_index, layer="F.Cu"):
    """Turn a library footprint into a board footprint at (x, y, rot).

    layer="B.Cu" mirrors the footprint onto the back of the board.
    """
    if layer == "B.Cu":
        fp_tree = mirror_tree(fp_tree)
    fpid = fp_tree[1]
    out = ["footprint", fpid, ["layer", Str(layer)], ["uuid", Str(str(uuid.uuid4()))],
           ["at", x, y] + ([rot] if rot else [])]
    # Labels follow the part's side: back-mounted parts get B.* layers.
    back = layer == "B.Cu"
    silk = "B.SilkS" if back else "F.SilkS"
    fab = "B.Fab" if back else "F.Fab"
    ref_prop = ["property", Str("Reference"), Str(ref),
                ["at", 0, -2.5 if not back else 2.5, 0], ["layer", Str(silk)],
                ["effects", ["font", ["size", 1, 1], ["thickness", 0.15]]]]
    val_prop = ["property", Str("Value"), Str(value),
                ["at", 0, 2.5 if not back else -2.5, 0], ["layer", Str(fab)],
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
            # keep the library's pad fields but drop any uuid it already has
            pad = [x for x in child if not (isinstance(x, list) and x and x[0] == "uuid")]
            name = str(pad[1])
            # KiCad stores each pad's angle including the part's rotation; without it
            # the pad shape stays unrotated when the part is turned.
            at = [x for x in pad if isinstance(x, list) and x and x[0] == "at"]
            if at and rot:
                local = float(at[0][3]) if len(at[0]) > 3 else 0.0
                at[0][:] = ["at", at[0][1], at[0][2], (local + rot) % 360] if local + rot else ["at", at[0][1], at[0][2]]
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


def pack_remaining(placed_boxes, refs, footprints, outline, step=(1.0, 1.0), rotations=(0, 90)):
    """Greedy grid packer for parts without a planned position.

    Tries each rotation on a 1 mm grid, left to right, bottom to top, and
    keeps the first spot that is inside the outline and clear of every box
    already placed.
    """
    x0, y0, x1, y1 = outline
    gx, gy = step
    result = {}
    boxes = list(placed_boxes)
    for ref in refs:
        fp = footprints[ref]
        spot = None
        for rot in rotations:
            y = y0 + 1
            while y < y1 - 1 and spot is None:
                x = x0 + 1
                while x < x1 - 1 and spot is None:
                    bx = bbox_of(fp, x, y, rot, margin=0.3, side="B")
                    inside = bx[0] >= x0 and bx[2] <= x1 and bx[1] >= y0 and bx[3] <= y1
                    clear = all(bx[2] <= b[0] or bx[0] >= b[2] or bx[3] <= b[1] or bx[1] >= b[3] for b in boxes)
                    if inside and clear:
                        spot = (x, y, rot, bx)
                    x += gx
                y += gy
            if spot:
                break
        if spot is None:
            raise RuntimeError("no room for " + ref)
        x, y, rot, bx = spot
        result[ref] = (x, y, rot)
        boxes.append(bx)
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
    # Through-hole parts go through both sides, so their pads block the back too.
    overrides = getattr(layout, "SIDE", {})
    sides = {r: overrides.get(r, "B.Cu" if is_smd(footprints[r]) else "F.Cu") for r in footprints}
    # Back-side parts block the back by their courtyard; front-side
    # through-hole parts only block the back through their pads.
    back_boxes = [bbox_of(footprints[r], x, y, rot, side=sides[r],
                          pads_only=(sides[r] != "B.Cu"))
                  for r, (x, y, rot) in place.items() if r in footprints]
    remaining = [r for r in sorted(footprints, key=lambda s: (re.sub(r"\d+", "", s), int(re.sub(r"\D", "", s) or 0)))
                 if r not in place]
    if remaining:
        place.update(pack_remaining(back_boxes, remaining, footprints, outline))
    for r in remaining:
        if sides[r] != "B.Cu":
            raise RuntimeError("packer can only place SMD parts, not " + r)

    body = [["version", 20260206], ["generator", Str("pcbgen")],
            ["general", ["thickness", 1.6]], ["paper", Str("A4")], layers, setup]
    body += net_decl
    body += edge_cuts(*outline)
    for ref in sorted(footprints):
        x, y, rot = place[ref]
        c = comps[ref]
        index = pad_nets.get(ref, {})
        fp = wrap_footprint(footprints[ref], ref, c["value"], x, y, rot, index, sides[ref])
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
