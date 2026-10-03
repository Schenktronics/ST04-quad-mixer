"""Generate the front-panel PCB for the 4ch mixer.

The panel is a 6HP (30.48 mm) board with a solid copper pour on the front
copper layer. Holes are placed on the centres of the footprint circles on the
mixer board, so they line up with the pots and jacks. Hole sizes, tick marks
and the output jack rings follow the Attenuverter faceplate.

Usage (from the project root):
    python3 tools/panel/make_panel.py --board "Schematic/4ch Mixer.kicad_pcb" \
        --template "Schematic/4ch Mixer.kicad_pcb" --out "Faceplate/4ch Mixer Faceplate.kicad_pcb"

The copper pour is a zone on F.Cu; run kicad-cli pcb drc --refill-zones to fill it.
"""
import argparse
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pcb"))
import place_rest  # noqa: E402
import pcbgen  # noqa: E402
import sexpr  # noqa: E402
from sexpr import Str  # noqa: E402

PANEL_W = 30.48          # 6HP
PANEL_H = 128.5          # Eurorack height
SHAFT_D = 7.0            # pot shaft hole (Attenuverter)
JACK_D = 6.0             # jack hole (Attenuverter)
MOUNT_D = 3.2            # M3 mounting hole (Attenuverter)
RING_R = 2.45            # output jack ring radius (Attenuverter)
RING_W = 5.0             # output jack ring stroke width (Attenuverter)
TICK_IN = 3.5            # tick starts at the hole edge
TICK_LONG = 7.25         # long tick end (every 45 degrees)
TICK_SHORT = 6.75        # short tick end
TICK_RADIUS_ARC = 8.25
POINTER_W = 0.5
WIDTH_LONG = 0.3
WIDTH_SHORT = 0.2
EDGE_CLEAR = 0.5

# tick angles in degrees, counter-clockwise from +x as drawn (screen y up)
TICK_ANGLES = [a for a in range(-180, 180, 15) if not (-105 <= a <= -75)]


LOGO_LIB = os.path.join(os.path.dirname(__file__), "..", "..", "Faceplate", "lib",
                        "_NTSFootprints.pretty", "SchentronicsLogo.kicad_mod")


def load_footprint_file(path):
    return sexpr.parse(open(path, encoding="utf-8").read())


def uid():
    return Str(str(uuid.uuid4()))


def hole_fp(name, x, y, d, ref):
    return ["footprint", Str(name), ["layer", Str("F.Cu")], ["uuid", uid()],
            ["at", x, y], ["attr", "board_only", "exclude_from_pos_files", "exclude_from_bom"],
            ["property", Str("Reference"), Str(ref), ["at", 0, 0, 0], ["layer", Str("F.SilkS")],
             ["hide", "yes"], ["effects", ["font", ["size", 1, 1], ["thickness", 0.15]]]],
            ["pad", Str(""), "np_thru_hole", "circle", ["at", 0, 0], ["size", d, d],
             ["drill", d], ["layers", Str("*.Cu"), Str("*.Mask")], ["uuid", uid()]]]


def gr_line(x1, y1, x2, y2, width, layer):
    return ["gr_line", ["start", round(x1, 4), round(y1, 4)], ["end", round(x2, 4), round(y2, 4)],
            ["stroke", ["width", width], ["type", "default"]], ["layer", Str(layer)], ["uuid", uid()]]


def gr_circle(cx, cy, r, width, layer):
    return ["gr_circle", ["center", cx, cy], ["end", round(cx + r, 4), cy],
            ["stroke", ["width", width], ["type", "default"]], ["fill", "none"],
            ["layer", Str(layer)], ["uuid", uid()]]


def gr_arc(cx, cy, r, start_deg, sweep_deg, width, layer):
    """Arc on a circle of radius r about (cx, cy), from start_deg sweeping sweep_deg.

    Angles are counter-clockwise as seen on screen, the same convention as the
    Attenuverter's arcs. KiCad 10 wants start, mid and end points.
    """
    def pt(a):
        rad = math.radians(a)
        return round(cx + r * math.cos(rad), 4), round(cy - r * math.sin(rad), 4)
    a0, a1 = start_deg, start_deg + sweep_deg
    return ["gr_arc", ["start", *pt(a0)], ["mid", *pt((a0 + a1) / 2)], ["end", *pt(a1)],
            ["stroke", ["width", width], ["type", "default"]],
            ["layer", Str(layer)], ["uuid", uid()]]


def polar(cx, cy, r, deg):
    """Point at angle deg (counter-clockwise on screen) on a circle of radius r."""
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


POT_RING_R = 8.25
JACK_RING_R = 5.0


def channel_group(pot, jack, r_pot=POT_RING_R, r_jack=JACK_RING_R):
    """Outline around one pot and its jack: the outer arcs of a ring around each,
    joined by the two external tangent lines (top and bottom). The inner arc
    segments between the tangent points are trimmed away, leaving one smooth
    oblong shape per channel."""
    px, py = pot
    jx, jy = jack
    # Work in y-up coordinates. A tangent normal n touches both rings when
    # n . (jack - pot) = r_pot - r_jack; the two solutions are the top and bottom tangents.
    dx, dy = jx - px, -(jy - py)
    d = math.hypot(dx, dy)
    ux, uy = dx / d, dy / d
    k = (r_pot - r_jack) / d
    perp = math.sqrt(1 - k * k)
    normals = []
    for s in (1, -1):
        nx = k * ux - s * perp * uy
        ny = k * uy + s * perp * ux
        normals.append((nx, ny))
    top = max(normals, key=lambda n: n[1])
    bot = min(normals, key=lambda n: n[1])
    ang_top = math.degrees(math.atan2(top[1], top[0]))
    ang_bot = math.degrees(math.atan2(bot[1], bot[0]))
    out = []
    # outer arc of the pot ring: from the top tangent point clockwise round the far side to the bottom
    out.append(gr_arc(px, py, r_pot, ang_top, -((ang_top - ang_bot) % 360), WIDTH_SHORT, "F.SilkS"))
    # outer arc of the jack ring: from the bottom tangent point clockwise round the far side to the top
    out.append(gr_arc(jx, jy, r_jack, ang_bot, -((ang_bot - ang_top) % 360), WIDTH_SHORT, "F.SilkS"))
    # the two tangent lines, top and bottom
    for ang in (ang_top, ang_bot):
        a = polar(px, py, r_pot, ang)
        b = polar(jx, jy, r_jack, ang)
        out.append(gr_line(a[0], a[1], b[0], b[1], WIDTH_SHORT, "F.SilkS"))
    return out


def pot_ticks(cx, cy, x_max=None):
    """Radial tick marks around a pot shaft, as on the Attenuverter faceplate.

    Ticks that would run past x_max are clipped to it.
    """
    out = []
    for a in TICK_ANGLES:
        rad = math.radians(a)
        dx, dy = math.cos(rad), -math.sin(rad)     # screen y is down
        if a == 90:                                # the pointer at the top
            outer, width = TICK_LONG, POINTER_W
        elif a % 45 == 0:
            outer, width = TICK_LONG, WIDTH_LONG
        else:
            outer, width = TICK_SHORT, WIDTH_SHORT
        ex = cx + dx * outer
        if x_max is not None and ex > x_max:
            outer = (x_max - cx) / dx
        out.append(gr_line(cx + dx * TICK_IN, cy + dy * TICK_IN,
                           cx + dx * outer, cy + dy * outer, width, "F.SilkS"))
    return out


def build(board, template, out_path):
    parts = place_rest.board_footprints(board)

    def centre(ref, lx, ly):
        p = parts[ref]
        rx, ry = pcbgen.rotate(lx, ly, p["rot"])
        return round(p["x"] + rx, 3), round(p["y"] + ry, 3)

    pots = [centre("RV%d" % k, 7.5, -2.5) for k in range(1, 5)]          # shaft circle
    jacks_in = [centre("J%d" % k, 0.0, 6.477) for k in range(1, 5)]      # jack centre hole
    jacks_out = [centre("J5", 0.0, 6.477), centre("J6", 0.0, 6.477)]

    # Panel: same x as the board, centred on the board's vertical centre.
    bx0, by0, bx1, by1 = 100.0, 50.0, 130.0, 150.0
    # centre the panel on the board horizontally (the board is 30 mm, the panel 30.48 mm)
    bw = bx1 - bx0
    x0 = bx0 - (PANEL_W - bw) / 2
    x1 = x0 + PANEL_W
    y_mid = (by0 + by1) / 2
    y0, y1 = y_mid - PANEL_H / 2, y_mid + PANEL_H / 2

    layers = sexpr.find_one(sexpr.parse(open(template, encoding="utf-8").read()), "layers")
    setup = sexpr.find_one(sexpr.parse(open(template, encoding="utf-8").read()), "setup")
    body = [["version", 20260206], ["generator", Str("make_panel")],
            ["general", ["thickness", 1.6]], ["paper", Str("A4")], layers, setup,
            ["net", 0, Str("")], ["net", 1, Str("GND")]]

    # outline
    for seg in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
        body.append(gr_line(*seg, 0.05, "Edge.Cuts"))

    # solid copper pour on the front layer, clear of every hole
    body.append(["zone", ["net", 1], ["net_name", Str("GND")], ["layer", Str("F.Cu")], ["uuid", uid()],
                 ["hatch", "edge", 0.5],
                 ["connect_pads", ["clearance", EDGE_CLEAR]],
                 ["min_thickness", 0.25], ["filled_areas_thickness", "no"],
                 ["fill", "yes", ["thermal_gap", 0.5], ["thermal_bridge_width", 0.5]],
                 ["polygon", ["pts", ["xy", x0, y0], ["xy", x1, y0], ["xy", x1, y1], ["xy", x0, y1]]]])

    # mounting holes: match the Attenuverter faceplate
    # Attenuverter: holes 7.5 mm and 22.75 mm from the left edge, 3 mm from top and bottom
    mx_left, mx_right = x0 + 7.5, x0 + 22.75
    my_top, my_bot = y0 + 3.0, y1 - 3.0
    for i, (mx, my) in enumerate([(mx_left, my_top), (mx_right, my_top),
                                  (mx_left, my_bot), (mx_right, my_bot)], start=1):
        body.append(hole_fp("Panel:MountingHole_3.2mm", round(mx, 3), round(my, 3), MOUNT_D, "H%d" % i))

    # Schentronics logo, same offset from the panel's top-left corner as on the
    # Attenuverter faceplate (logo at 130.25, 146.5 with the panel at 115, 25.75).
    logo = load_footprint_file(LOGO_LIB)
    logo_fp = pcbgen.wrap_footprint(logo, "LOGO", "", round(x0 + 15.25, 3),
                                    round(y0 + 120.75, 3), 0, {}, "F.Cu")
    for child in logo_fp:                       # the value field is a placeholder: hide it
        if isinstance(child, list) and child and child[0] == "property" and child[1] == "Value":
            child.append(["hide", "yes"])
    body.append(logo_fp)

    # pot shafts and jacks
    for i, (x, y) in enumerate(pots, start=1):
        body.append(hole_fp("Panel:PotShaft_7mm", x, y, SHAFT_D, "PS%d" % i))
        body.extend(pot_ticks(x, y, x_max=x1 - 0.05))
    for i, (x, y) in enumerate(jacks_in, start=1):
        body.append(hole_fp("Panel:Jack_6mm", x, y, JACK_D, "JH%d" % i))
    # each input jack grouped with its own pot
    for (px, py), (jx, jy) in zip(pots, jacks_in):
        body.extend(channel_group((px, py), (jx, jy)))
    for i, (x, y) in enumerate(jacks_out, start=5):
        body.append(hole_fp("Panel:Jack_6mm", x, y, JACK_D, "JH%d" % i))
        body.append(gr_circle(x, y, RING_R, RING_W, "F.SilkS"))

    board_tree = ["kicad_pcb"] + body
    text = sexpr.dumps(board_tree) + "\n"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(text)
    return dict(panel=(x0, y0, x1, y1), pots=pots, jacks_in=jacks_in, jacks_out=jacks_out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    info = build(a.board, a.template, a.out)
    for k, v in info.items():
        print(k, v)
