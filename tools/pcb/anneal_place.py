"""Optimise the positions of movable parts to shorten wires, with spacing.

Simulated annealing over the (x, y, rotation) of the movable parts. The cost
is the total half-perimeter wire length of every net (power nets weighted
lower), plus a large penalty for any overlap or for leaving the outline.
Spacing is enforced: back-side parts keep `gap` mm between courtyards, and
every through-hole pad keeps `gap` mm from back-side parts, so there is room
to solder by hand.

Usage (from the project root):
    python3 tools/pcb/anneal_place.py --board "Schematic/4ch Mixer.kicad_pcb" \
        --netlist netlist.net --movable R C --fixed P1 F1 F2 D1 D2 U1 U2 \
        --fp-dir Schematic/lib
"""
import argparse
import math
import random
import re

import pcbgen
from place_rest import board_footprints, set_position

# Ground connects to a pour through vias, so it doesn't count toward wire length.
GROUND_NETS = {"GNDA", "GND"}
RAIL_NETS = {"+12VA", "-12VA", "+12V", "-12V"}
OVERLAP_PENALTY = 1000.0


def nets_of(netlist_path):
    comps, nets = pcbgen.load_netlist(netlist_path)
    out = []
    for name, nodes in nets.items():
        if not name or name.startswith("unconnected"):
            continue
        refs = sorted({r for r, _ in nodes})
        if len(refs) < 2:
            continue
        if name in GROUND_NETS:
            weight = 0.0
        elif name in RAIL_NETS:
            weight = 0.3
        else:
            weight = 1.0
        out.append((weight, refs))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--movable", nargs="+", required=True)
    ap.add_argument("--fixed", nargs="*", default=[])
    ap.add_argument("--fp-dir", action="append", default=[])
    ap.add_argument("--outline", default="100,50,130,150")
    ap.add_argument("--gap", type=float, default=1.0, help="min clearance between parts (mm)")
    ap.add_argument("--iters", type=int, default=60000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rotate", action="store_true",
                    help="allow 90 degree moves (off by default: rotated SMD pads don't turn with the part)")
    ap.add_argument("--fixed-margin", type=float, default=1.5,
                    help="extra clearance around fixed back-side parts (covers model error)")
    a = ap.parse_args()
    random.seed(a.seed)

    x0, y0, x1, y1 = map(float, a.outline.split(","))
    parts = board_footprints(a.board)
    fps = {r: pcbgen.load_footprint(p["lib"], a.fp_dir) for r, p in parts.items()}
    nets = nets_of(a.netlist)

    def is_movable(ref):
        return any(ref.startswith(pre) and ref[len(pre):].isdigit() for pre in a.movable)

    movable = [r for r in parts if is_movable(r)]
    fixed = {r: parts[r] for r in parts if not is_movable(r)}
    half_gap = a.gap / 2.0
    state = {r: dict(parts[r]) for r in parts}

    def box(ref, st, margin, pads_only=None):
        p = st[ref]
        if pads_only is None:
            pads_only = p["side"] == "F.Cu"
        return pcbgen.bbox_of(fps[ref], p["x"], p["y"], p["rot"], margin=margin,
                              side=p["side"], pads_only=pads_only)

    def overlaps(b1, b2):
        return not (b1[2] <= b2[0] or b1[0] >= b2[2] or b1[3] <= b2[1] or b1[1] >= b2[3])

    def violations(ref):
        """Gap conflicts and outline violations for one movable (back-side) part.

        Back-side parts keep `gap` between courtyards. Through-hole parts only
        block through their pads, so their pads must keep `gap` clear too.
        """
        bad = 0
        mine = box(ref, state, half_gap)
        if mine[0] < x0 + 0.2 or mine[2] > x1 - 0.2 or mine[1] < y0 + 0.2 or mine[3] > y1 - 0.2:
            bad += 1
        for other in parts:
            if other == ref:
                continue
            if state[other]["side"] == "F.Cu":
                ob = box(other, state, half_gap, pads_only=True)
            elif other in fixed:
                ob = box(other, state, half_gap + a.fixed_margin)
            else:
                ob = box(other, state, half_gap)
            if overlaps(mine, ob):
                bad += 1
        return bad

    def total_violations():
        return sum(violations(r) for r in movable)

    def hpwl():
        total = 0.0
        for weight, refs in nets:
            xs = [state[r]["x"] for r in refs if r in state]
            ys = [state[r]["y"] for r in refs if r in state]
            if len(xs) >= 2:
                total += weight * ((max(xs) - min(xs)) + (max(ys) - min(ys)))
        return total

    def cost():
        return hpwl() + OVERLAP_PENALTY * total_violations()

    # Start from the current positions; movable parts are free to move.
    for ref in movable:
        state[ref]["rot"] = 0
    cur = cost()
    temp = 8.0
    cooling = (0.02 / 8.0) ** (1.0 / a.iters)
    for it in range(a.iters):
        ref = random.choice(movable)
        old = dict(state[ref])
        span = max(0.5, 12.0 * temp / 8.0)
        if a.rotate and random.random() < 0.1:
            state[ref]["rot"] = 90 if old["rot"] == 0 else 0
        else:
            state[ref]["x"] = round(min(max(old["x"] + random.gauss(0, span), x0 + 1), x1 - 1), 2)
            state[ref]["y"] = round(min(max(old["y"] + random.gauss(0, span), y0 + 1), y1 - 1), 2)
        new = cost()
        if new <= cur or random.random() < math.exp((cur - new) / temp):
            cur = new
        else:
            state[ref] = old
        temp *= cooling

    final_v = total_violations()
    print("final cost %.1f, hpwl %.1f, violations %d" % (cur, hpwl(), final_v))
    for ref in sorted(movable, key=lambda r: (re.sub(r"\d+", "", r), int(re.sub(r"\D", "", r)))):
        s = state[ref]
        set_position(a.board, ref, s["x"], s["y"], s["rot"])
        print("%-4s (%.2f, %.2f) rot %d" % (ref, s["x"], s["y"], s["rot"]))


if __name__ == "__main__":
    main()
