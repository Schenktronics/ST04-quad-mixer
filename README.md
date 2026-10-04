# 4ch Mixer

Four-channel active mixer for Eurorack, 6HP. Each input has a pot and a
switched jack. Two outputs: J5 is non-inverting (+) and J6 is inverting (−).

## Layout

```
hardware/
  mixer/        KiCad 10 project: schematic, PCB, library tables, lib/ (custom symbols and footprints)
  panel/        KiCad 10 front-panel PCB (aluminium, single-sided), lib/ (logo footprint)
manufacturing/
  mixer/        Gerbers, drill, BOMs (SMD for the fab, hand assembly), placement files
  panel/        Gerbers and drill for the front panel
tools/
  pcb/          Board generator, placement and annealing scripts, S-expression reader
  panel/        Front-panel generator (holes, ticks, rings, logo, title)
```

## Build notes

- **Mixer PCB:** 1.6 mm, two layers, SMD parts on both sides. The pot,
  jack, and header are through-hole and are hand-soldered.
- **Front panel:** 1.6 mm aluminium, single-sided. Unplated holes for pot
  shafts (7 mm), jacks (6 mm), and mounting (3.2 mm).
- **Fab order:** the SMD BOM and placement file are for the fab. Use the
  hand-assembly list for the through-hole parts and knobs.

## Regenerating the panel

```
python3 tools/panel/make_panel.py --board "hardware/mixer/4ch Mixer.kicad_pcb" \
    --template "hardware/mixer/4ch Mixer.kicad_pcb" --out "hardware/panel/4ch Mixer Faceplate.kicad_pcb"
```

Run `kicad-cli pcb drc --refill-zones` on the result to fill the copper pour.
