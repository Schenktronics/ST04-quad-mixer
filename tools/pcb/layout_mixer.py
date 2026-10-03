"""Placement for the 4ch mixer, 6HP (30 x 100 mm), same origin as the Attenuverter.

Pots RV1-RV4 are a column on the right, 24 mm apart, using the full board
length. Each input jack J1-J4 sits on the same row as its pot, on the left
side. Output jacks J5 and J6 are on the right near the bottom. The power
header P1 is on the back side of the board, along the bottom edge, left of
the outputs. Everything else is packed into the remaining space, SMD parts
on the back.
"""

OUTLINE = (100.0, 50.0, 130.0, 150.0)

POT_X = 124.9
POT_ROWS = [64.5, 88.5, 112.5, 136.5]
JACK_X = 101.9

PLACE = {}
for k, y in enumerate(POT_ROWS, start=1):
    PLACE["RV%d" % k] = (POT_X, y, 90)
    PLACE["J%d" % k] = (JACK_X, y, 90)   # pads point in toward the pot

PLACE["J5"] = (128.0, 118.8, 270)   # output, gap between pots 3 and 4
PLACE["J6"] = (128.0, 145.0, 270)   # output, bottom right
PLACE["P1"] = (112.0, 56.0, 270)    # 10-pin power header, back side, top-left edge

SIDE = {"P1": "B.Cu"}               # through-hole header mounted from the back
