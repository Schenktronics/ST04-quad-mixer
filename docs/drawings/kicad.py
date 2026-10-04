"""Read the parts of a KiCad 6+ board or faceplate file that the drawings need.

Stdlib only. The file is parsed into nested lists, so the drawing scripts can
ask for footprints, pads and graphics by name instead of matching text.
"""
import math
import re
from pathlib import Path

TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(\()|(\))|([^\s()"]+)')


def parse(text):
    """Return the top-level s-expression of a KiCad file as nested lists."""
    stack = [[]]
    for quoted, open_, close, bare in TOKEN.findall(text):
        if open_:
            stack.append([])
        elif close:
            node = stack.pop()
            stack[-1].append(node)
        elif quoted:
            stack[-1].append(quoted.replace('\\"', '"').replace("\\n", "\n"))
        else:
            stack[-1].append(bare)
    return stack[0][0]


def children(node, name):
    """Every child list whose first item is `name`."""
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def child(node, name):
    found = children(node, name)
    return found[0] if found else None


def value(node, name, default=None):
    """The single value after `name`, e.g. (layer "F.Cu") -> "F.Cu"."""
    c = child(node, name)
    return c[1] if c and len(c) > 1 else default


def xy(node):
    return float(node[1]), float(node[2])


def rotate(x, y, degrees):
    """Rotate counter-clockwise on screen, the way KiCad rotates footprints."""
    a = math.radians(degrees)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def load(path):
    return parse(Path(path).read_text())


def footprints(board):
    """Each footprint as a dict with its ref, layer, placement, pads and graphics."""
    out = []
    for fp in children(board, "footprint"):
        at = child(fp, "at")
        x, y = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        layer = value(fp, "layer", "F.Cu")
        ref = ""
        for prop in children(fp, "property"):
            if prop[1] == "Reference":
                ref = prop[2]
        pads = []
        for pad in children(fp, "pad"):
            pat = child(pad, "at")
            size = child(pad, "size")
            drill = child(pad, "drill")
            net = child(pad, "net")
            pads.append(dict(
                num=pad[1],
                type=pad[2],
                shape=pad[3] if len(pad) > 3 and isinstance(pad[3], str) else "",
                x=float(pat[1]), y=float(pat[2]),
                angle=float(pat[3]) if len(pat) > 3 else 0.0,
                w=float(size[1]), h=float(size[2]),
                drill=float(drill[1]) if drill and isinstance(drill[1], str) and drill[1] not in ("oval",) else None,
                net=net[-1] if net and len(net) > 1 else "",
            ))
        out.append(dict(ref=ref, name=fp[1], layer=layer, x=x, y=y, rot=rot,
                        pads=pads, node=fp))
    return out


def place(fp, lx, ly):
    """Board coordinates of a footprint-local point, given the footprint's placement.

    KiCad 6+ stores pads in the footprint's own frame, already mirrored for
    footprints on the back, so a back-side footprint only needs its rotation.
    """
    rx, ry = rotate(lx, ly, fp["rot"])
    return fp["x"] + rx, fp["y"] + ry


def edge_bbox(board):
    """Bounding box (x0, y0, x1, y1) of the Edge.Cuts outline."""
    xs, ys = [], []
    for item in board:
        if not (isinstance(item, list) and item and item[0] in ("gr_line", "gr_rect", "gr_arc", "gr_circle")):
            continue
        if value(item, "layer") != "Edge.Cuts":
            continue
        for key in ("start", "end", "mid", "center"):
            p = child(item, key)
            if p:
                xs.append(float(p[1]))
                ys.append(float(p[2]))
    return min(xs), min(ys), max(xs), max(ys)


def graphics(board, layer):
    """Board-level graphic items on one layer, as (kind, node) pairs."""
    out = []
    for item in board:
        if isinstance(item, list) and item and item[0].startswith("gr_") and value(item, "layer") == layer:
            out.append((item[0], item))
    return out
