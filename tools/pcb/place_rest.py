"""Place the movable parts of an existing board, keeping hand-placed parts fixed.

Usage (from the project root):
    python3 tools/pcb/place_rest.py --board "Schematic/4ch Mixer.kicad_pcb" \
        --netlist netlist.net --movable R C --fp-dir Schematic/lib

Each movable part goes to the free spot nearest the centroid of the parts it
is wired to (ignoring the ground and power nets). Back-side parts block each
other by courtyard, and every through-hole pad blocks the back side. The
board file is edited in place: only the (at ...) of movable parts changes.
"""
import argparse
import re

import pcbgen
import sexpr

POWER_NETS = {"GNDA", "+12VA", "-12VA", "GND", "+12V", "-12V"}


def board_footprints(path):
    """Return {ref: dict(lib, x, y, rot, side)} from the board file."""
    tree = sexpr.parse(open(path, encoding="utf-8").read())
    out = {}
    for f in tree[1:]:
        if not (isinstance(f, list) and f and f[0] == "footprint"):
            continue
        ref = [x for x in f if isinstance(x, list) and x and x[0] == "property" and x[1] == "Reference"][0][2]
        at = [x for x in f if isinstance(x, list) and x and x[0] == "at"][0]
        side = [x for x in f if isinstance(x, list) and x and x[0] == "layer"][0][1]
        out[str(ref)] = {"lib": str(f[1]), "x": float(at[1]), "y": float(at[2]),
                         "rot": float(at[3]) if len(at) > 3 else 0.0, "side": str(side)}
    return out


def connections(netlist_path):
    """Return {ref: set of refs wired to it through non-power nets}."""
    comps, nets = pcbgen.load_netlist(netlist_path)
    links = {}
    for name, nodes in nets.items():
        if not name or name in POWER_NETS or name.startswith("unconnected"):
            continue
        refs = {r for r, _ in nodes}
        for r in refs:
            links.setdefault(r, set()).update(refs - {r})
    return links


def set_position(path, ref, x, y, rot):
    """Rewrite the (at ...) of one footprint in the board file."""
    t = open(path, encoding="utf-8").read()
    starts = [m.start() for m in re.finditer(r"\n\t\(footprint ", t)] + [len(t)]
    for a, b in zip(starts, starts[1:]):
        blk = t[a:b]
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        if not m or m.group(1) != ref:
            continue
        am = re.search(r"\n\t\t\(at [-\d.]+ [-\d.]+(?: [-\d.]+)?\)", blk)
        new = "\n\t\t(at %.3f %.3f %g)" % (x, y, rot)
        t = t[:a + am.start()] + new + t[a + am.end():]
        open(path, "w", encoding="utf-8").write(t)
        return
    raise KeyError(ref)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--movable", nargs="+", required=True, help="reference prefixes, e.g. R C")
    ap.add_argument("--fp-dir", action="append", default=[])
    ap.add_argument("--outline", default="100,50,130,150")
    ap.add_argument("--step", type=float, default=0.5)
    a = ap.parse_args()

    x0, y0, x1, y1 = map(float, a.outline.split(","))
    parts = board_footprints(a.board)
    links = connections(a.netlist)
    fps = {}
    for ref, p in parts.items():
        fps[ref] = pcbgen.load_footprint(p["lib"], a.fp_dir)

    def movable(ref):
        return any(ref.startswith(prefix) and ref[len(prefix):].isdigit() for prefix in a.movable)

    # Blocking boxes: back-side parts by courtyard, through-hole parts by pads.
    boxes = []
    for ref, p in parts.items():
        if movable(ref):
            continue
        front_tht = p["side"] == "F.Cu"          # front through-hole: its pads block the back
        boxes.append(pcbgen.bbox_of(fps[ref], p["x"], p["y"], p["rot"],
                                    side=p["side"], pads_only=front_tht))

    todo = sorted((r for r in parts if movable(r)),
                  key=lambda r: (re.sub(r"\d+", "", r), int(re.sub(r"\D", "", r))))
    # Place the most connected parts first, then the rest.
    todo.sort(key=lambda r: -len(links.get(r, ())))
    for ref in todo:
        neigh = [parts[n] for n in links.get(ref, ()) if n in parts]
        if neigh:
            cx = sum(p["x"] for p in neigh) / len(neigh)
            cy = sum(p["y"] for p in neigh) / len(neigh)
        else:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        best = None
        for rot in (0, 90):
            # Spiral search outward from the centroid on a grid.
            for ring in range(0, 400):
                found = None
                for dx in range(-ring, ring + 1):
                    for dy in range(-ring, ring + 1):
                        if max(abs(dx), abs(dy)) != ring:
                            continue
                        x = round(cx + dx * a.step, 3)
                        y = round(cy + dy * a.step, 3)
                        bx = pcbgen.bbox_of(fps[ref], x, y, rot, margin=0.3, side="B.Cu")
                        if bx[0] < x0 or bx[2] > x1 or bx[1] < y0 or bx[3] > y1:
                            continue
                        if all(bx[2] <= b[0] or bx[0] >= b[2] or bx[3] <= b[1] or bx[1] >= b[3] for b in boxes):
                            d = (x - cx) ** 2 + (y - cy) ** 2
                            if found is None or d < found[0]:
                                found = (d, x, y, rot, bx)
                if found:
                    break
            if found and (best is None or found[0] < best[0]):
                best = found
        if best is None:
            raise RuntimeError("no room for " + ref)
        d, x, y, rot, bx = best
        boxes.append(bx)
        parts[ref].update(x=x, y=y, rot=rot)
        set_position(a.board, ref, x, y, rot)
        print("%-5s -> (%.2f, %.2f) rot %d  (links: %s)" % (ref, x, y, rot,
              ", ".join(sorted(links.get(ref, ()))[:4])))


if __name__ == "__main__":
    main()
