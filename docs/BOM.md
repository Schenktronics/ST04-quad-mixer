# Bill of Materials: ST-04 Quad Mixer v1.0

A machine-readable copy is in [BOM.csv](BOM.csv).

All the resistors, capacitors, diodes, fuses, and chips are surface-mount parts on the back of the board. The resistors and capacitors are 0805 size. Parts marked "or equivalent" can be swapped for any part with the same value, package, and pinout.

Kits ship with every surface-mount part below already soldered by the board house and tested, so you only need these if you're making your own boards.

## Surface-mount parts (back of the board)

| Qty | Reference | Part | Manufacturer / Part No. | Notes |
|----:|-----------|------|--------------------------|-------|
| 1 | U1 | Quad JFET op-amp, SOIC-14 | Texas Instruments TL074CDR (TI, Microchip, or Analog Devices only) | [Datasheet](https://www.ti.com/lit/ds/symlink/tl074.pdf). Pin 1 is marked on the board. |
| 1 | U2 | Dual JFET op-amp, SOIC-8 | Texas Instruments TL072CDR (TI, Microchip, or Analog Devices only) | Pin 1 is marked on the board. |
| 13 | R1-R4, R9-R17 | Resistor, 10 kΩ, 1%, 0805 | Yageo RC0805FR-0710KL, or equivalent | Gain-setting and mixing resistors. |
| 4 | R5-R8 | Resistor, 0 Ω jumper, 0805 | Yageo RC0805FR-070RL, or equivalent | Feedback link for each channel's op-amp, set for unity gain. |
| 6 | R18-R23 | Resistor, 1 kΩ, 1%, 0805 | Yageo RC0805FR-071KL, or equivalent | R18 and R19 are the output resistors. R20-R23 sit between each channel's knob and its op-amp. |
| 4 | C1-C4 | Capacitor, 0.1 µF, 25 V, X7R, 0805 | AVX 08053C104KAT2A, or equivalent | Decoupling on the ±12 V rails. |
| 2 | C5, C6 | Capacitor, 10 µF, 25 V, X5R, 0805 | Taiyo Yuden TMK212BBJ106KG-T, or equivalent | Bulk decoupling on the ±12 V rails. |
| 2 | C7, C8 | Capacitor, 10 pF, 50 V, C0G/NP0, 0805 | Yageo CC0805JRNPO9BN100, or equivalent | Feedback capacitors on the output stage. |
| 2 | D1, D2 | Diode, 1 A, 300 V, SMA | ON Semiconductor MRA4003T3G, or equivalent | Reverse-power protection. The cathode (stripe) end matters. |
| 8 | D3-D10 | Diode, 1N4148, SOD-323, 75 V, 150 mA | Diodes Incorporated 1N4148WS-7-F, or equivalent | [Datasheet](https://datasheet.octopart.com/1N4148WS-7-F-Diodes-Inc.-datasheet-7284054.pdf). Input clamps. The cathode (stripe) end matters. |
| 2 | F1, F2 | Resettable fuse (PTC), 200 mA hold, 30 V, 1206 | Bel Fuse 0ZCJ0020FF2E, or equivalent | Either way round. F1 is on +12 V, F2 on -12 V. |

## Through-hole parts

| Qty | Reference | Part | Manufacturer / Part No. | Notes |
|----:|-----------|------|--------------------------|-------|
| 1 | P1 | Shrouded pin header, 2 x 5, 2.54 mm, vertical | On Shore Technology 302-S101, or equivalent | Eurorack power connector. Pins 1-2 are -12 V, pins 9-10 are +12 V, pins 3-8 are ground. |
| 6 | J1-J6 | 3.5 mm mono switched jack, vertical PCB mount, with nut | QingPu WQP-PJ398SM or WQP518MA, or equivalent. Either one works. | [Datasheet / product page](http://www.qingpu-electronics.com/en/products/WQP-PJ398SM-362.html). The inputs (J1-J4) need the switched contact: it grounds an empty input. The outputs (J5, J6) don't use it. The pads are oval so the board can also take panel-mount style jacks such as the CUI MJ-3507 ([datasheet](https://www.cuidevices.com/product/resource/mj-3507.pdf)), which may be easier to source. Its sleeve is a solder lug rather than a pin, so it needs a short wire from the lug to the square pad. |
| 4 | RV1-RV4 | Potentiometer, 100 kΩ linear, 6 mm D shaft, no bushing | Bourns PTV09A-4020F-B104 | [Datasheet](http://www.farnell.com/datasheets/2259384.pdf). The pot's three pins go to the input, the wiper and ground. It mounts on its board-lock lugs and passes through the 7 mm panel hole. Clockwise turns the channel up to x1, and counterclockwise turns it down to silence. |
| 4 | | Knob, for 6 mm D shaft | Davies Molding 1221-J, or equivalent | Fits the pot's 6 mm D shaft. |
| 1 | | Main PCB, 30 x 100 mm, 2-layer, 1.6 mm | Schenktronics | |
| 1 | | Faceplate, 6HP (30 x 128.5 mm), 1.6 mm aluminum PCB | Schenktronics | Single-sided, so it can also be made in FR4. |
| 1 | | Eurorack power cable, 10-pin to 16-pin | | Red stripe marks -12 V. |

## Not included

| Qty | Part | Notes |
|----:|------|-------|
| 2 | M3 rack screws | Supplied with most Eurorack cases. |
