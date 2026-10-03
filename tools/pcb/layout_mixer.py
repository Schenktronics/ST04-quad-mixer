"""Placement for the 4ch mixer, 6HP (30 x 100 mm), same origin as the Attenuverter.

Input jacks J1-J4 form a column on the left, each on the same row as its
pot RV1-RV4. Pots sit in a column to the right of the jacks, 26 mm apart,
using the full board length. Output jacks J5/J6 are on the right, near the
bottom. Everything else is packed into the free space.
"""

OUTLINE = (100.0, 50.0, 130.0, 150.0)

POT_X = 124.9
POT_ROWS = [63.5, 89.5, 115.5, 141.5]
JACK_X = 101.9

PLACE = {}
for k, y in enumerate(POT_ROWS, start=1):
    PLACE["RV%d" % k] = (POT_X, y, 90)
    PLACE["J%d" % k] = (JACK_X, y, 90)   # pads point in toward the pot

PLACE["J5"] = (126.0, 122.0, 270)   # output, right side
PLACE["J6"] = (126.0, 146.0, 270)   # output, right side near bottom
PLACE["P1"] = (110.0, 147.0, 90)   # 10-pin power header along the bottom edge
