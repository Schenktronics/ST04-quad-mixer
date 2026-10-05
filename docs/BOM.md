# Bill of Materials — 4ch Mixer v1.0

A machine-readable copy is in [BOM.csv](BOM.csv). The fabrication files are in [manufacturing/mixer/](../manufacturing/mixer/): the surface-mount list and placement file for the board house are `mixer-bom-smd-fab.csv` and `mixer-pos-smd-fab.csv`, and the hand-assembly list for the through-hole parts is `mixer-bom-tht-handsolder.csv`.

All the resistors, capacitors, diodes, fuses and chips are surface-mount parts on the back of the board. The resistors and capacitors are 0805 size. Parts marked "or equivalent" can be swapped for any part with the same value, package and pinout.

The **Easy Build Kit** includes a PCB with every surface-mount part below already soldered and tested, so you only need to source the through-hole parts.

## Surface-mount parts (back of the board)

| Qty | Reference | Part | Manufacturer / Part No. | Notes |
|----:|-----------|------|--------------------------|-------|
| 1 | U1 | Quad JFET op-amp, SOIC-14 | Texas Instruments TL074CDR (TI, Microchip or Analog Devices only) | [Datasheet](https://www.ti.com/lit/ds/symlink/tl074.pdf). Pin 1 is marked on the board. |
| 1 | U2 | Dual JFET op-amp, SOIC-8 | Texas Instruments TL072CDR (TI, Microchip or Analog Devices only) | Pin 1 is marked on the board. |
| 17 | R1–R17 | Resistor, 10 kΩ, 1%, 0805 | Yageo RC0805FR-0710KL, or equivalent | Mixing and gain resistors. |
| 6 | R18–R23 | Resistor, 1 kΩ, 1%, 0805 | Yageo RC0805FR-071KL, or equivalent | R18 and R19 are the output resistors. R20–R23 sit between each channel's knob and its op-amp. |
| 4 | C1–C4 | Capacitor, 0.1 µF, 25 V, X7R, 0805 | AVX 08053C104KAT2A, or equivalent | Decoupling on the ±12 V rails. |
| 2 | C5, C6 | Capacitor, 10 µF, 25 V, X5R, 0805 | Taiyo Yuden TMK212BBJ106KG-T, or equivalent | Bulk decoupling on the ±12 V rails. |
| 2 | C7, C8 | Capacitor, 10 pF, 50 V, C0G/NP0, 0805 | Yageo CC0805JRNPO9BN100, or equivalent | Feedback capacitors on the output stage. |
| 2 | D1, D2 | Diode, 1 A, 300 V, SMA | ON Semiconductor MRA4003T3G, or equivalent | Reverse-power protection. The cathode (stripe) end matters. |
| 8 | D3–D10 | Diode, 1N4148, SOD-323, 75 V, 150 mA | Diodes Incorporated 1N4148WS-7-F, or equivalent | [Datasheet](https://datasheet.octopart.com/1N4148WS-7-F-Diodes-Inc.-datasheet-7284054.pdf). Input clamps. The cathode (stripe) end matters. |
| 2 | F1, F2 | Resettable fuse (PTC), 200 mA hold, 30 V, 1206 | Bel Fuse 0ZCJ0020FF2E, or equivalent | Either way round. F1 is on +12 V, F2 on −12 V. |

## Through-hole parts

| Qty | Reference | Part | Manufacturer / Part No. | Notes |
|----:|-----------|------|--------------------------|-------|
| 1 | P1 | Shrouded pin header, 2 × 5, 2.54 mm, vertical | On Shore Technology 302-S101, or equivalent | Eurorack power connector. Pins 1–2 are −12 V, pins 9–10 are +12 V, pins 3–8 are ground. |
| 6 | J1–J6 | 3.5 mm mono switched jack, vertical PCB mount, with nut | CUI Devices MJ-3507, or QingPu WQP-PJ398SM or WQP518MA | The inputs (J1–J4) need the switched contact: it grounds an empty input. The outputs (J5, J6) don't use it. Any of these fits the PJ398SM footprint. The CUI part needs a short wire from its sleeve lug to the square ground pad (see the [assembly guide](assembly-guide.md#step-6--solder-the-pots-and-jacks)). |
| 4 | RV1–RV4 | Potentiometer, 10 kΩ linear, center detent, 6 mm D shaft, no bushing | Panasonic EVU-F3AF20B14 | The pot's three pins go to the input, the wiper and ground. It mounts on its board-lock lugs and passes through the 7 mm panel hole. Clockwise from the detent boosts the channel to ×2; anticlockwise attenuates it to silence. |
| 4 | — | Knob, for 6 mm D shaft | Davies Molding 1221-J, or equivalent | Fits the pot's 6 mm D shaft. |
| 1 | — | Main PCB, 30 × 100 mm, 2-layer, 1.6 mm | Schenktronics | Fabrication files: [manufacturing/mixer/](../manufacturing/mixer/) |
| 1 | — | Faceplate, 6HP (30.48 × 128.5 mm), 1.6 mm aluminium PCB | Schenktronics | Fabrication files: [manufacturing/panel/](../manufacturing/panel/). Single-sided, so it can also be made in FR4. |
| 1 | — | Eurorack power cable, 10-pin to 16-pin | | Red stripe marks −12 V. |

## Not included

| Qty | Part | Notes |
|----:|------|-------|
| 4 | M3 rack screws | Supplied with most Eurorack cases. Two, in diagonally opposite corners, will hold the module. |

## Ordering the parts

The surface-mount parts and the through-hole parts are listed separately in the fabrication folder, so you can order each from its own supplier.
