#!/usr/bin/env python3
"""Generate the front-panel line drawings from the KiCad faceplate file.

Writes docs/images/panel.svg (annotated front view, for the user manual) and
docs/images/panel-plain.svg (the panel alone, for packaging labels where small
captions would be lost).
Run from anywhere: python3 docs/drawings/make_panel_svg.py
"""
import math
from pathlib import Path

import kicad

ROOT = Path(__file__).resolve().parents[2]
PCB = ROOT / "hardware" / "panel" / "4ch Mixer Faceplate.kicad_pcb"
OUT = ROOT / "docs" / "images"

INK = "#1a1a1a"
DIM = "#555"
FONT = "font-family='DejaVu Sans, Helvetica, Arial, sans-serif'"

KNOB_R = 4.8  # radius of the knob as drawn
JACK_R = 3.9  # radius of the jack's nut as drawn
MOUNT_R = 1.6


def load_panel():
    """Return (outline, holes, silk). Holes are (kind, x, y, diameter)."""
    board = kicad.load(PCB)
    outline = kicad.edge_bbox(board)
    holes, silk = [], dict(lines=[], arcs=[], circles=[], texts=[], polys=[])
    for fp in kicad.footprints(board):
        name = fp["name"].split(":")[-1]
        if name.startswith("PotShaft"):
            holes.append(("pot", fp["x"], fp["y"], 7.0))
        elif name.startswith("Jack"):
            holes.append(("jack", fp["x"], fp["y"], 6.0))
        elif name.startswith("MountingHole"):
            holes.append(("mount", fp["x"], fp["y"], 3.2))
        # Footprint silkscreen (the logo is a set of filled polygons).
        for item in fp["node"]:
            if not (isinstance(item, list) and item and item[0] in ("fp_poly", "fp_line")):
                continue
            if kicad.value(item, "layer") != "F.SilkS":
                continue
            if item[0] == "fp_poly":
                pts = kicad.child(item, "pts")
                polygon = [kicad.place(fp, *kicad.xy(p)) for p in kicad.children(pts, "xy")]
                silk["polys"].append(polygon)
            else:
                s, e = kicad.child(item, "start"), kicad.child(item, "end")
                width = float(kicad.child(kicad.child(item, "stroke"), "width")[1])
                a, b = kicad.place(fp, *kicad.xy(s)), kicad.place(fp, *kicad.xy(e))
                silk["lines"].append((a[0], a[1], b[0], b[1], width))
    board_items = kicad.graphics(board, "F.SilkS")
    for kind, item in board_items:
        width = kicad.child(item, "stroke")
        width = float(kicad.child(width, "width")[1]) if width else 0.2
        if kind == "gr_line":
            s, e = kicad.child(item, "start"), kicad.child(item, "end")
            silk["lines"].append((float(s[1]), float(s[2]), float(e[1]), float(e[2]), width))
        elif kind == "gr_arc":
            silk["arcs"].append(tuple(
                float(v) for k in ("start", "mid", "end") for v in kicad.xy(kicad.child(item, k))) + (width,))
        elif kind == "gr_circle":
            c, e = kicad.xy(kicad.child(item, "center")), kicad.xy(kicad.child(item, "end"))
            silk["circles"].append((c[0], c[1], math.hypot(e[0] - c[0], e[1] - c[1]), width))
        elif kind == "gr_text":
            at = kicad.child(item, "at")
            font = kicad.child(kicad.child(item, "effects"), "font")
            size = float(kicad.child(font, "size")[1])
            silk["texts"].append(dict(text=item[1], x=float(at[1]), y=float(at[2]), size=size,
                                      italic=kicad.child(font, "italic") is not None))
    return outline, holes, silk


def arc_path(x1, y1, xm, ym, x2, y2):
    """SVG path for a KiCad three-point arc, from start through mid to end."""
    # Circumcentre of the three points.
    d = 2 * (x1 * (ym - y2) + xm * (y2 - y1) + x2 * (y1 - ym))
    cx = ((x1 ** 2 + y1 ** 2) * (ym - y2) + (xm ** 2 + ym ** 2) * (y2 - y1) + (x2 ** 2 + y2 ** 2) * (y1 - ym)) / d
    cy = ((x1 ** 2 + y1 ** 2) * (x2 - xm) + (xm ** 2 + ym ** 2) * (x1 - x2) + (x2 ** 2 + y2 ** 2) * (xm - x1)) / d
    r = math.hypot(x1 - cx, y1 - cy)
    a_s, a_m, a_e = (math.atan2(y - cy, x - cx) % (2 * math.pi) for x, y in ((x1, y1), (xm, ym), (x2, y2)))
    d_m, d_e = (a_m - a_s) % (2 * math.pi), (a_e - a_s) % (2 * math.pi)
    if d_m < d_e:  # mid lies on the positive-angle sweep
        sweep, large = 1, int(d_e > math.pi)
    else:
        sweep, large = 0, int((2 * math.pi - d_e) > math.pi)
    return f"M{x1:.3f} {y1:.3f} A{r:.3f} {r:.3f} 0 {large} {sweep} {x2:.3f} {y2:.3f}"


def knob(x, y):
    """A knob seen from the front, pointer at 12 o'clock (the center, half gain)."""
    return [f"<circle cx='{x}' cy='{y}' r='{KNOB_R}' fill='#fff' stroke='{INK}' stroke-width='0.35'/>",
            f"<circle cx='{x}' cy='{y}' r='{KNOB_R - 1.3}' fill='#fff' stroke='{INK}' stroke-width='0.25'/>",
            f"<line x1='{x}' y1='{y - KNOB_R}' x2='{x}' y2='{y - 2}' stroke='{INK}' stroke-width='0.6' "
            f"stroke-linecap='round'/>"]


def panel_body(outline, holes, silk):
    """SVG elements for the faceplate itself, in board coordinates (mm)."""
    x0, y0, x1, y1 = outline
    el = [f"<rect x='{x0}' y='{y0}' width='{x1 - x0}' height='{y1 - y0}' rx='0.4' "
          f"fill='#fff' stroke='{INK}' stroke-width='0.3'/>"]
    for pts in silk["polys"]:
        el.append(f"<polygon points='{' '.join(f'{x:.3f},{y:.3f}' for x, y in pts)}' fill='{INK}'/>")
    for xa, ya, xb, yb, w in silk["lines"]:
        el.append(f"<line x1='{xa:.3f}' y1='{ya:.3f}' x2='{xb:.3f}' y2='{yb:.3f}' stroke='{INK}' "
                  f"stroke-width='{w}' stroke-linecap='round'/>")
    for xs, ys, xm, ym, xe, ye, w in silk["arcs"]:
        el.append(f"<path d='{arc_path(xs, ys, xm, ym, xe, ye)}' fill='none' stroke='{INK}' stroke-width='{w}'/>")
    for cx, cy, r, w in silk["circles"]:
        # The thick rings around the outputs. KiCad draws them as a circle with a wide stroke.
        el.append(f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='{INK}' stroke-width='{w}'/>")
    for t in silk["texts"]:
        style = " font-style='italic'" if t["italic"] else ""
        for i, line in enumerate(t["text"].split("\n")):
            dy = (i - (t["text"].count("\n") / 2)) * t["size"] * 1.3
            el.append(f"<text x='{t['x']}' y='{t['y'] + dy:.3f}' {FONT} font-size='{t['size'] * 1.15:.3f}'"
                      f"{style} fill='{INK}' text-anchor='middle' dominant-baseline='central'>{line}</text>")
    for kind, x, y, d in holes:
        if kind == "jack":
            # Jack nut with the socket opening.
            el.append(f"<circle cx='{x}' cy='{y}' r='{JACK_R}' fill='#fff' stroke='{INK}' stroke-width='0.35'/>")
            el.append(f"<circle cx='{x}' cy='{y}' r='{JACK_R - 0.8}' fill='none' stroke='{INK}' stroke-width='0.2'/>")
            el.append(f"<circle cx='{x}' cy='{y}' r='1.8' fill='{INK}'/>")
        elif kind == "pot":
            el += knob(x, y)
        else:
            el.append(f"<circle cx='{x}' cy='{y}' r='{MOUNT_R}' fill='#fff' stroke='{INK}' stroke-width='0.3'/>")
    return el


def svg(view, body, title):
    vx, vy, vw, vh = view
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{vx:.3f} {vy:.3f} {vw:.3f} {vh:.3f}' "
            f"width='{vw * 4:.0f}' height='{vh * 4:.0f}'>\n<title>{title}</title>\n"
            f"<rect x='{vx:.3f}' y='{vy:.3f}' width='{vw:.3f}' height='{vh:.3f}' fill='#fff'/>\n"
            + "\n".join(body) + "\n</svg>\n")


def controls(holes, silk):
    """Each channel's (knob, input jack) as (x, y), top to bottom, plus the two outputs by polarity.

    The four pots and the four input jacks share a row each. The outputs are the
    two jacks at the bottom of the panel. Each is matched to the "+" or "-" printed
    beside it, so the drawings follow the faceplate if the outputs are swapped.
    """
    pots = sorted(((x, y) for k, x, y, d in holes if k == "pot"), key=lambda p: p[1])
    inputs = sorted(((x, y) for k, x, y, d in holes if k == "jack" and y < 140), key=lambda p: p[1])
    jacks = [(x, y) for k, x, y, d in holes if k == "jack" and y >= 140]
    labels = {t["text"]: (t["x"], t["y"]) for t in silk["texts"] if t["text"] in ("+", "-")}
    nearest = lambda label: min(jacks, key=lambda j: math.dist(j, labels[label]))
    outputs = {"+": nearest("+"), "−": nearest("-")}
    channels = [(pots[i], inputs[i]) for i in range(len(pots))]
    return channels, outputs


def annotated(outline, holes, silk):
    x0, y0, x1, y1 = outline
    body = panel_body(outline, holes, silk)
    lx = x1 + 5  # leader lines end here
    tx = lx + 2  # labels start here
    lx_left = x0 - 5
    tx_left = lx_left - 2

    def label_right(y, title, sub, from_x, from_y):
        return [f"<polyline points='{from_x},{from_y} {x1 + 2},{y} {lx},{y}' fill='none' stroke='{DIM}' stroke-width='0.3'/>",
                f"<circle cx='{from_x}' cy='{from_y}' r='0.5' fill='{DIM}'/>",
                f"<text x='{tx}' y='{y - 1.6}' {FONT} font-size='3.2' font-weight='bold' fill='{INK}' "
                f"dominant-baseline='central'>{title}</text>",
                f"<text x='{tx}' y='{y + 2.4}' {FONT} font-size='2.4' fill='{DIM}' "
                f"dominant-baseline='central'>{sub}</text>"]

    def label_left(y, title, sub, from_x, from_y):
        return [f"<polyline points='{from_x},{from_y} {x0 - 2},{y} {lx_left},{y}' fill='none' stroke='{DIM}' stroke-width='0.3'/>",
                f"<circle cx='{from_x}' cy='{from_y}' r='0.5' fill='{DIM}'/>",
                f"<text x='{tx_left}' y='{y - 1.6}' {FONT} font-size='3.2' font-weight='bold' fill='{INK}' "
                f"text-anchor='end' dominant-baseline='central'>{title}</text>",
                f"<text x='{tx_left}' y='{y + 2.4}' {FONT} font-size='2.4' fill='{DIM}' "
                f"text-anchor='end' dominant-baseline='central'>{sub}</text>"]

    channels, outputs = controls(holes, silk)
    (kx, ky), (ix, iy) = channels[0]
    # Channel 1 is labelled in full. The jack's label goes out to the left, the knob's to the right.
    body += label_left(iy - 4, "In 1", "input. Empty: silent", ix - 4, iy)
    body += label_right(ky, "Knob 1", "anticlockwise silent, clockwise ×1", kx + KNOB_R, ky)
    for n, ((kx, ky), _) in enumerate(channels[1:], start=2):
        body += label_right(ky, f"Channel {n}", "same as channel 1", x1 - 1, ky)
    centre = (x0 + x1) / 2
    for polarity, title, sub in (("+", "+ output", "non-inverting mix"), ("−", "− output", "inverted mix")):
        ox, oy = outputs[polarity]
        if ox < centre:
            body += label_left(oy, title, sub, ox - 6.2, oy)
        else:
            body += label_right(oy, title, sub, ox + 6.2, oy)
    pad = 4
    return svg((x0 - pad - 46, y0 - pad, (x1 - x0) + 2 * pad + 92, (y1 - y0) + 2 * pad), body,
               "Quad Mixer front panel")


def plain(outline, holes, silk):
    x0, y0, x1, y1 = outline
    pad = 1
    return svg((x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad), panel_body(outline, holes, silk),
               "Quad Mixer front panel")


def main():
    data = load_panel()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panel.svg").write_text(annotated(*data))
    (OUT / "panel-plain.svg").write_text(plain(*data))
    print("wrote", OUT / "panel.svg", "and", OUT / "panel-plain.svg")


if __name__ == "__main__":
    main()
