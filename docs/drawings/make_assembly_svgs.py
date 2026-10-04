#!/usr/bin/env python3
"""Generate the assembly-guide drawings from the main PCB's KiCad file.

Board views (front and back) are drawn exactly, from the pads, outline and
silkscreen in the PCB file. The side view is a diagram: its heights are approximate.

Writes docs/images/assembly-*.svg.
Run from anywhere: python3 docs/drawings/make_assembly_svgs.py
"""
import math
from pathlib import Path

import kicad
from make_panel_svg import load_panel

ROOT = Path(__file__).resolve().parents[2]
PCB = ROOT / "hardware" / "mixer" / "4ch Mixer.kicad_pcb"
OUT = ROOT / "docs" / "images"

INK = "#1a1a1a"
GREY = "#888"
PAD = "#d2d2d2"
RED = "#d9302c"
FONT = "font-family='DejaVu Sans, Helvetica, Arial, sans-serif'"
SCALE = 6  # px per mm in the saved SVG

# Board outline, from the Edge.Cuts lines: x 100 to 130, y 50 to 150.
# The back view mirrors the board left to right, so the SMD side reads as you see it.
X0, Y0, X1, Y1 = kicad.edge_bbox(kicad.load(PCB))
MIRROR_SUM = X0 + X1


def load():
    board = kicad.load(PCB)
    return board, kicad.footprints(board)


def view_point(view, x, y):
    return (MIRROR_SUM - x, y) if view == "back" else (x, y)


def pad_outline(fp, pad, view):
    """SVG for one pad: its shape, size and rotation, on the board."""
    cx, cy = view_point(view, *kicad.place(fp, pad["x"], pad["y"]))
    # KiCad stores each pad's angle as it sits on the board, footprint rotation included,
    # so the angle alone decides which way the pad's width runs. A 90° angle swaps the axes.
    total = pad["angle"] % 180
    w, h = (pad["h"], pad["w"]) if abs(total - 90) < 1 else (pad["w"], pad["h"])
    if pad["shape"] == "circle":
        return f"<circle cx='{cx:.3f}' cy='{cy:.3f}' r='{w / 2:.3f}' fill='{PAD}' stroke='{INK}' stroke-width='0.08'/>"
    rx = min(w, h) / 2 if pad["shape"] == "oval" else min(w, h) * 0.2
    return (f"<rect x='{cx - w / 2:.3f}' y='{cy - h / 2:.3f}' width='{w:.3f}' height='{h:.3f}' rx='{rx:.3f}' "
            f"fill='{PAD}' stroke='{INK}' stroke-width='0.08'/>")


def pad_hole(fp, pad, view):
    cx, cy = view_point(view, *kicad.place(fp, pad["x"], pad["y"]))
    return f"<circle cx='{cx:.3f}' cy='{cy:.3f}' r='{pad['drill'] / 2:.3f}' fill='#fff' stroke='{INK}' stroke-width='0.06'/>"


def fp_silk(fp, view, layer):
    """Footprint silkscreen lines on one side, in board coordinates."""
    out = []
    for item in fp["node"]:
        if not (isinstance(item, list) and item and item[0] in ("fp_line", "fp_rect", "fp_circle")):
            continue
        if kicad.value(item, "layer") != layer:
            continue
        width = kicad.child(kicad.child(item, "stroke") or [], "width")
        w = float(width[1]) if width else 0.12
        if item[0] == "fp_line":
            a = view_point(view, *kicad.place(fp, *kicad.xy(kicad.child(item, "start"))))
            b = view_point(view, *kicad.place(fp, *kicad.xy(kicad.child(item, "end"))))
            out.append(f"<line x1='{a[0]:.3f}' y1='{a[1]:.3f}' x2='{b[0]:.3f}' y2='{b[1]:.3f}' stroke='{INK}' "
                       f"stroke-width='{w}' stroke-linecap='round'/>")
        elif item[0] == "fp_rect":
            a = view_point(view, *kicad.place(fp, *kicad.xy(kicad.child(item, "start"))))
            b = view_point(view, *kicad.place(fp, *kicad.xy(kicad.child(item, "end"))))
            out.append(f"<rect x='{min(a[0], b[0]):.3f}' y='{min(a[1], b[1]):.3f}' width='{abs(a[0] - b[0]):.3f}' "
                       f"height='{abs(a[1] - b[1]):.3f}' fill='none' stroke='{INK}' stroke-width='{w}'/>")
    return out


def board_text(board, view, layer):
    """Board-level silkscreen text on one side, as a viewer on that side reads it.

    KiCad stores back-side text mirrored, with its justification in board
    coordinates. In the back view the mirror is undone, so left-justified text
    starts at its anchor and runs to the right.
    """
    out = []
    for kind, item in kicad.graphics(board, layer):
        if kind != "gr_text":
            continue
        at = kicad.child(item, "at")
        x, y = view_point(view, float(at[1]), float(at[2]))
        angle = float(at[3]) if len(at) > 3 else 0.0
        effects = kicad.child(item, "effects")
        justify = kicad.child(effects, "justify")
        font = kicad.child(effects, "font")
        size = float(kicad.child(font, "size")[1])
        anchor = "middle"
        if justify and "left" in justify:
            anchor = "start"
        elif justify and "right" in justify:
            anchor = "end"
        # Rotation is counter-clockwise in KiCad. The back view mirrors the board, so the sign flips there.
        turn = angle if view == "back" else -angle
        transform = f" transform='rotate({turn:.1f} {x:.3f} {y:.3f})'" if turn else ""
        for i, line in enumerate(item[1].split("\n")):
            dy = (i - item[1].count("\n") / 2) * size * 1.3
            out.append(f"<text x='{x:.3f}' y='{y + dy:.3f}' {FONT} font-size='{size:.3f}' fill='{INK}' "
                       f"text-anchor='{anchor}' dominant-baseline='central'{transform}>{line}</text>")
    return out


def ref_label(fp, view, size=1.5, color=INK, weight="normal"):
    cx, cy = view_point(view, fp["x"], fp["y"])
    return (f"<text x='{cx:.3f}' y='{cy:.3f}' {FONT} font-size='{size}' fill='{color}' font-weight='{weight}' "
            f"text-anchor='middle' dominant-baseline='central'>{fp['ref']}</text>")


def outline_box(fp, view, pad_margin=1.2):
    """The bounding box of a footprint's pads, with a margin, for highlighting a part."""
    pts = [view_point(view, *kicad.place(fp, p["x"], p["y"])) for p in fp["pads"]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs) - pad_margin, min(ys) - pad_margin, max(xs) + pad_margin, max(ys) + pad_margin


def board_svg(board, fps, view, title, highlight=None, labels=(), silk_layer=None, extra=()):
    """A board view. `highlight` maps (ref, pad number) to a colour; `labels` are references to name."""
    side = "B" if view == "back" else "F"
    highlight = highlight or {}
    body = [f"<rect x='{X0}' y='{Y0}' width='{X1 - X0}' height='{Y1 - Y0}' rx='0.3' fill='#fff' stroke='{INK}' "
            f"stroke-width='0.3'/>"]
    # Pads first, then the silkscreen on top.
    for fp in fps:
        if fp["layer"] == f"{side}.Cu" or any(p["type"] == "thru_hole" for p in fp["pads"]):
            for pad in fp["pads"]:
                if pad["type"] == "np_thru_hole":
                    continue  # the jacks' centre holes are drawn by the panel, not the board
                key = (fp["ref"], pad["num"])
                if key in highlight:
                    body.append(pad_outline(fp, pad, view).replace(f"fill='{PAD}'", f"fill='{highlight[key]}'"))
                else:
                    body.append(pad_outline(fp, pad, view))
                if pad["drill"]:
                    body.append(pad_hole(fp, pad, view))
    for fp in fps:
        layer = silk_layer or f"{side}.SilkS"
        if fp["layer"] == f"{side}.Cu" or any(p["type"] == "thru_hole" for p in fp["pads"]):
            body += fp_silk(fp, view, layer)
    body += board_text(board, view, f"{side}.SilkS")
    for fp in fps:
        if fp["ref"] in labels:
            body.append(ref_label(fp, view))
    body += list(extra)
    return svg(view_box(), body, title)


def view_box(pad=2):
    return (X0 - pad, Y0 - pad, (X1 - X0) + 2 * pad, (Y1 - Y0) + 2 * pad)


LIGHT = "#f4f4f4"  # bodies of the pots and jacks
TINT = "#fbe3e2"  # a pot's shaft, behind the jacks
PANEL_Y0, PANEL_Y1 = load_panel()[0][1], load_panel()[0][3]  # the faceplate's length along the board


def text(x, y, s, size=2.6, weight="normal", color=INK, anchor="start"):
    return (f"<text x='{x:.2f}' y='{y:.2f}' {FONT} font-size='{size}' font-weight='{weight}' fill='{color}' "
            f"text-anchor='{anchor}' dominant-baseline='central'>{s}</text>")


def arrow_defs():
    return (f"<defs><marker id='head' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='4' markerHeight='4' "
            f"orient='auto'><path d='M0 1 L10 5 L0 9 z' fill='{INK}'/></marker></defs>")


def arrow(x1, y1, x2, y2, color=INK, width=0.35):
    return (f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' stroke='{color}' "
            f"stroke-width='{width}' marker-end='url(#head)'/>")


def shaft(pot):
    """A pot's shaft sits midway between its two mounting lugs (the unnamed pads)."""
    lugs = [kicad.place(pot, p["x"], p["y"]) for p in pot["pads"] if p["num"] == ""]
    return ((lugs[0][0] + lugs[1][0]) / 2, (lugs[0][1] + lugs[1][1]) / 2)


def jack_hole(jack):
    """A jack's centre hole: the unnamed non-plated pad, in board coordinates."""
    return next(kicad.place(jack, p["x"], p["y"]) for p in jack["pads"] if p["type"] == "np_thru_hole")


def svg(view, body, title):
    vx, vy, vw, vh = view
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{vx:.3f} {vy:.3f} {vw:.3f} {vh:.3f}' "
            f"width='{vw * SCALE:.0f}' height='{vh * SCALE:.0f}'>\n<title>{title}</title>\n"
            f"<rect x='{vx:.3f}' y='{vy:.3f}' width='{vw:.3f}' height='{vh:.3f}' fill='#fff'/>\n"
            + "\n".join(body) + "\n</svg>\n")


def outline_element(box, color, width=0.5):
    x0, y0, x1, y1 = box
    return (f"<rect x='{x0:.3f}' y='{y0:.3f}' width='{x1 - x0:.3f}' height='{y1 - y0:.3f}' rx='0.8' fill='none' "
            f"stroke='{color}' stroke-width='{width}' stroke-dasharray='1.2 0.8'/>")


def fig_smd(board, fps):
    """Back view: every surface-mount part, with U1's pin 1 and the diode cathodes marked."""
    hl = {("U1", "1"): RED}
    for fp in fps:
        if fp["ref"].startswith("D") and fp["ref"] != "D":
            hl[(fp["ref"], "1")] = RED
    smd = [f for f in fps if f["layer"] == "B.Cu" and f["ref"] and not f["ref"].startswith("FID")]
    labels = [f["ref"] for f in smd if f["ref"].startswith(("R", "C", "U", "D", "F"))]
    return board_svg(board, fps, "back", "Back of the board: surface-mount parts", highlight=hl,
                     labels=labels, silk_layer="B.SilkS")


def fig_header(board, fps):
    """Back view: the power header, with pin 1 marked and the notch position."""
    byref = {f["ref"]: f for f in fps}
    p1 = byref["P1"]
    hl = {("P1", "1"): RED}
    box = outline_box(p1, "back", pad_margin=2.6)
    extra = [outline_element(box, RED, 0.6)]
    return board_svg(board, fps, "back", "Power header, from the back", highlight=hl,
                     labels=[], extra=extra)


def fig_parts(board, fps):
    """Front view: the pots and jacks, outlined and labelled."""
    front = [f for f in fps if f["layer"] == "F.Cu" and f["ref"] and not f["ref"].startswith(("FID", "G", "H"))]
    extra = []
    for f in front:
        if f["ref"].startswith(("RV", "J")):
            extra.append(outline_element(outline_box(f, "front", pad_margin=3.6), RED, 0.5))
    labels = [f["ref"] for f in front if f["ref"].startswith("J")]  # the pot labels would sit on the pins
    return board_svg(board, fps, "front", "Front of the board: pots and jacks", labels=labels,
                     silk_layer="F.SilkS", extra=extra)


def fig_solder(board, fps):
    """Back view: the one pad to tack first on each pot and jack, filled red."""
    hl = {}
    for f in fps:
        if f["ref"].startswith("J"):
            hl[(f["ref"], "S")] = RED
        if f["ref"].startswith("RV"):
            hl[(f["ref"], "2")] = RED
    return board_svg(board, fps, "back", "Tack the pads marked red", highlight=hl)


def fig_side(board, fps):
    """Step 4: exploded side view of the pots, jacks, faceplate and nuts, along the board's length.

    The faceplate's holes and the board's pots and jacks share one set of
    coordinates, so the parts are placed from the PCB and the holes from the faceplate.
    """
    _, holes, _ = load_panel()
    panel_top, panel_bot = PANEL_Y0, PANEL_Y1
    u = lambda y: y - panel_top + 2  # drawing x for a board y

    byref = {f["ref"]: f for f in fps}
    pots = [byref[f"RV{n}"] for n in range(1, 5)]
    jacks = [byref[f"J{n}"] for n in range(1, 7)]
    pcb_y, body_h, bush_h = 60, 9, 4.5
    body_top = pcb_y - body_h
    panel_y = body_top - 18  # exploded gap
    nut_y = panel_y - 9

    body = [arrow_defs()]
    body.append(f"<rect x='{u(panel_top)}' y='{pcb_y}' width='{panel_bot - panel_top}' height='1.6' "
                f"fill='{LIGHT}' stroke='{INK}' stroke-width='0.3'/>")
    # The power header hangs under the board, on the back.
    header = byref["P1"]
    ys = [kicad.place(header, p["x"], p["y"])[1] for p in header["pads"]]
    hx, hw = u((min(ys) + max(ys)) / 2), max(ys) - min(ys) + 2.5
    body.append(f"<rect x='{hx - hw / 2:.2f}' y='{pcb_y + 1.6}' width='{hw:.2f}' height='6' rx='0.3' fill='#fff' "
                f"stroke='{INK}' stroke-width='0.3'/>")
    # Surface-mount parts underneath.
    for f in fps:
        if f["layer"] == "B.Cu" and f["ref"][:1] in "RCDUF" and f["ref"]:
            body.append(f"<rect x='{u(f['y']) - 1:.2f}' y='{pcb_y + 1.6}' width='2' height='0.8' fill='{PAD}' "
                        f"stroke='{GREY}' stroke-width='0.1'/>")

    def legs(f, pad_names):
        out = []
        for p in f["pads"]:
            if p["num"] in pad_names:
                _, py = kicad.place(f, p["x"], p["y"])
                out.append(f"<line x1='{u(py):.2f}' y1='{pcb_y + 1.6}' x2='{u(py):.2f}' y2='{pcb_y + 3.2}' "
                           f"stroke='{INK}' stroke-width='0.35'/>")
        return out

    # Pots sit beside the jacks, so from this side they're behind them. No threaded bushing: a body and a D shaft.
    for f in pots:
        sx, sy = shaft(f)
        x = u(sy)
        body.append(f"<rect x='{x - 5:.2f}' y='{body_top + 1}' width='10' height='{body_h - 1}' rx='0.4' "
                    f"fill='{LIGHT}' stroke='{GREY}' stroke-width='0.3'/>")
        body.append(f"<rect x='{x - 3:.2f}' y='{body_top - 20}' width='6' height='20' fill='{TINT}' "
                    f"stroke='{RED}' stroke-width='0.35'/>")
        body += legs(f, ("1", "2", "3"))
    for f in jacks:
        hole_y = jack_hole(f)[1]
        x = u(hole_y)
        body.append(f"<rect x='{x - 4.5:.2f}' y='{body_top}' width='9' height='{body_h}' rx='0.4' fill='#fff' "
                    f"stroke='{INK}' stroke-width='0.35'/>")
        body.append(f"<rect x='{x - 3:.2f}' y='{body_top - bush_h}' width='6' height='{bush_h}' fill='#fff' "
                    f"stroke='{INK}' stroke-width='0.35'/>")
        body += [f"<line x1='{x - 3:.2f}' y1='{body_top - bush_h + dy}' x2='{x + 3:.2f}' y2='{body_top - bush_h + dy}' "
                 f"stroke='{GREY}' stroke-width='0.15'/>" for dy in (1.2, 2.4, 3.6)]
        body += legs(f, ("S", "T", "TN"))

    # Faceplate, cut away at each hole. Overlapping cuts (the two outputs share a height) are merged.
    cuts = sorted((u(y) - d / 2, u(y) + d / 2) for _, x, y, d in holes)
    merged = []
    for a, b in cuts:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    edges = [u(panel_top)]
    for a, b in merged:
        edges += [a, b]
    edges.append(u(panel_bot))
    for a, b in zip(edges[::2], edges[1::2]):
        if b > a:
            body.append(f"<rect x='{a:.2f}' y='{panel_y}' width='{b - a:.2f}' height='1.6' fill='{INK}'/>")

    # Jack nuts. The pots have none. The two outputs share one height, so one nut shows there.
    for y in sorted({round(jack_hole(f)[1], 2) for f in jacks}):
        x = u(y)
        body.append(f"<rect x='{x - 4:.2f}' y='{nut_y}' width='8' height='2.2' rx='0.3' fill='#fff' "
                    f"stroke='{INK}' stroke-width='0.35'/>")
        for dx in (-2.5, -0.8, 0.8, 2.5):
            body.append(f"<line x1='{x + dx:.2f}' y1='{nut_y}' x2='{x + dx:.2f}' y2='{nut_y + 2.2}' "
                        f"stroke='{GREY}' stroke-width='0.15'/>")

    # Arrows and labels.
    top_jack = jack_hole(jacks[0])[1]
    body.append(arrow(u(top_jack), nut_y + 3, u(top_jack), panel_y - 0.8, width=0.3))
    body.append(arrow(u(top_jack), panel_y + 2.8, u(top_jack), body_top - bush_h - 0.8, width=0.3))
    lx = u(panel_bot) + 3
    body.append(text(lx, nut_y + 1.1, "Jack nuts", 2.6, "bold"))
    body.append(text(lx, nut_y + 4.3, "finger-tight first", 2.2, color=GREY))
    body.append(text(lx, panel_y + 0.8, "Faceplate", 2.6, "bold"))
    body.append(text(lx, panel_y + 4, "“Quad Mixer” end over In 1", 2.2, color=GREY))
    body.append(text(lx, body_top + 3, "Pots and jacks", 2.6, "bold"))
    body.append(text(lx, body_top + 6.2, "not soldered yet", 2.2, color=GREY))
    body.append(text(lx, pcb_y + 0.8, "PCB", 2.6, "bold"))
    body.append(text(lx, pcb_y + 4, "SMD parts and header below", 2.2, color=GREY))
    mid = (u(shaft(pots[1])[1]) + u(shaft(pots[2])[1])) / 2
    body.append(text(mid, pcb_y + 11, "Center the pot shafts in their holes,", 2.6, "bold", color=RED, anchor="middle"))
    body.append(text(mid, pcb_y + 14.2, "then tighten the jack nuts", 2.2, color=GREY, anchor="middle"))
    body.append(text(u(PANEL_Y0), pcb_y + 11, "Top (In 1 end)", 2, color=GREY))
    body.append(text(u(PANEL_Y1), pcb_y + 11, "Bottom (+ and − outputs)", 2, color=GREY, anchor="end"))
    body.append(text(u(panel_top), pcb_y + 19, "Side view, not to scale vertically", 2, color=GREY))
    return svg((u(panel_top) - 2, nut_y - 4, (panel_bot - panel_top) + 48, pcb_y - nut_y + 26), body,
               "Step 4: fit the faceplate")


def main():
    board, fps = load()
    OUT.mkdir(parents=True, exist_ok=True)
    figures = (
        ("assembly-1-smd.svg", fig_smd(board, fps)),
        ("assembly-2-header.svg", fig_header(board, fps)),
        ("assembly-3-parts.svg", fig_parts(board, fps)),
        ("assembly-4-faceplate.svg", fig_side(board, fps)),
        ("assembly-5-solder.svg", fig_solder(board, fps)),
    )
    for name, text in figures:
        (OUT / name).write_text(text)
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
