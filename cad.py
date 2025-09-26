#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a DXF of the sheet metal development shown in the photo.
Edit the PARAMETERS section only; everything else auto-rebuilds.
"""

import math
from pathlib import Path
import ezdxf
from ezdxf.math import Vec2, fit_points_to_cad_cv
from ezdxf.enums import TextEntityAlignment

# --------------------------- PARAMETERS ---------------------------
UNITS = "mm"  # drawing units label (for your reference)

# Global baseline: Y grows downward (to match typical shop drawings).
# Set overall length from top=0 to bottom=overall_len.
overall_len = 1670.0

# Widths (approximate from the image—edit to your exact spec)
top_left_flange  = 35.0     # top left lip
top_right_flange = 16.0     # top right lip
bot_left_return  = 83.0     # bottom left return
bot_right_width  = 330.0    # bottom right width (overall right offset from left datum)

# Main body clear width near bottom (from photo: 345 @ bottom mark)
bottom_gauge_width = 345.0

# Left datum (x=0). We keep left edge straight; right edge has a gentle bow.
left_x = 0.0

# Bow profile for right edge (x at given stations); tweak to your real CAM values.
# Tuple of (y_from_top, x_from_left) control points.
right_edge_profile = [
    (0.0,          top_left_flange + 350.0),   # near top
    (235.0,        360.0),
    (435.0,        368.0),
    (635.0,        372.0),
    (835.0,        374.0),
    (1035.0,       372.0),
    (1235.0,       368.0),
    (1435.0,       360.0),
    (1635.0,       bottom_gauge_width),        # near bottom text shows 345; adjust here
]

# Hole stations (from the ticks you marked on both sides). Edit as needed.
# These are distances from TOP edge.
stations = [55, 285, 515, 835, 1155, 1385, 1615]
# Lateral offsets of holes from each edge:
hole_offset_from_left  = 20.0   # distance from LEFT edge to hole center (edit)
hole_offset_from_right = 20.0   # distance from RIGHT edge to hole center (edit)
# Hole diameter:
hole_dia = 14.0  # the “14” callout in the image

# Bending line (from the dashed note in the middle); set exact Y if you have it.
bending_line_y = 1385.0

# Text height
txt_h = 10.0

# ------------------------ HELPER FUNCTIONS ------------------------
def add_circle(msp, center: Vec2, d: float, layer: str):
    r = d / 2.0
    msp.add_circle(center, r, dxfattribs={"layer": layer})

def add_text(msp, text, insert, layer, height=10.0):
    msp.add_text(text, dxfattribs={"height": height, "layer": layer, "insert": insert})

def spline_from_points(msp, pts, layer="OUTLINE"):
    # Convert to CAD-compatible spline control structure
    # Using a fit-curve approach for a smooth edge
    msp.add_spline(fit_points=pts, dxfattribs={"layer": layer})

def dashed_line(msp, p1: Vec2, p2: Vec2, layer="CENTER"):
    # Simple dashed imitation: small segments
    segs = 80
    on = True
    for i in range(segs):
        t0 = i / segs
        t1 = (i + 1) / segs
        a = Vec2(p1.lerp(p2, t0))
        b = Vec2(p1.lerp(p2, t1))
        if on:
            msp.add_line(a, b, dxfattribs={"layer": layer})
        on = not on

# --------------------------- BUILD DXF ----------------------------
doc = ezdxf.new(setup=True)
msp = doc.modelspace()

# Layers
for name, color in [
    ("OUTLINE", 7), ("HOLES_L", 3), ("HOLES_R", 5),
    ("CENTER", 2), ("NOTES", 1)
]:
    if name not in doc.layers:
        doc.layers.add(name, color=color)

# Corner key points (top and bottom lips/returns)
top_y = 0.0
bot_y = overall_len

# Left edge polyline (straight)
left_top  = Vec2(left_x, top_y)
left_bot  = Vec2(left_x, bot_y)

# Top edge: tiny step showing left and right flanges (illustrative)
top_left_in  = Vec2(left_x + top_left_flange, top_y)
top_right    = Vec2(left_x + top_left_flange + 300.0 + top_right_flange, top_y)  # provisional span
# Replace the provisional span by tying to the right-edge profile first point:
if right_edge_profile:
    top_right = Vec2(right_edge_profile[0][1], right_edge_profile[0][0])

# Bottom edge: we’ll close between left-bottom return and the right-edge last point
bot_left_out  = Vec2(bot_left_return, bot_y)
bot_right_pt  = Vec2(right_edge_profile[-1][1], right_edge_profile[-1][0])

# Draw left edge
msp.add_line(left_top, left_bot, dxfattribs={"layer": "OUTLINE"})

# Draw top short lip and to first right-edge point
msp.add_line(left_top, top_left_in, dxfattribs={"layer": "OUTLINE"})
msp.add_line(top_left_in, top_right, dxfattribs={"layer": "OUTLINE"})

# Right bowed edge spline
right_pts = [Vec2(x, y) for (y, x) in right_edge_profile]
spline_from_points(msp, right_pts, layer="OUTLINE")

# Bottom edge: from right bottom to left bottom return, then to left bottom
msp.add_line(bot_right_pt, bot_left_out, dxfattribs={"layer": "OUTLINE"})
msp.add_line(bot_left_out, left_bot, dxfattribs={"layer": "OUTLINE"})

# --------------------------- HOLES -------------------------------
# Left holes at constant offset from left edge
for y in stations:
    cx = left_x + hole_offset_from_left
    cy = y
    add_circle(msp, Vec2(cx, cy), hole_dia, layer="HOLES_L")

# Right holes at constant offset from *right* bowed edge:
# To get the local right x at each Y, we linear-interpolate the profile.
def right_x_at(y_query: float) -> float:
    rp = sorted(right_edge_profile, key=lambda t: t[0])
    # clamp
    if y_query <= rp[0][0]:
        return rp[0][1]
    if y_query >= rp[-1][0]:
        return rp[-1][1]
    # find span
    for (y0, x0), (y1, x1) in zip(rp, rp[1:]):
        if y0 <= y_query <= y1:
            t = (y_query - y0) / (y1 - y0) if y1 != y0 else 0.0
            return x0 + t * (x1 - x0)
    return rp[-1][1]

for y in stations:
    edge_x = right_x_at(y)
    cx = edge_x - hole_offset_from_right
    cy = y
    add_circle(msp, Vec2(cx, cy), hole_dia, layer="HOLES_R")

# ------------------------ BENDING LINE ---------------------------
dashed_line(msp, Vec2(left_x, bending_line_y), Vec2(right_pts[-1].x, bending_line_y), layer="CENTER")
add_text(msp, "Bending line", Vec2(left_x + 10, bending_line_y + 12), "NOTES", height=txt_h)

# -------------------------- NOTES/TICKS --------------------------
# Station ticks & labels (optional)
for y in stations:
    msp.add_line((left_x - 8, y), (left_x, y), dxfattribs={"layer": "CENTER"})
    add_text(msp, f"{int(y)}", Vec2(left_x - 40, y - 3), "NOTES", height=8)

add_text(msp, f"Units: {UNITS}", Vec2(10, overall_len + 40), "NOTES", height=8)
add_text(msp, "Development View", Vec2(10, overall_len + 20), "NOTES", height=10)

# -------------------------- SAVE FILE ----------------------------
out = Path("panel_development.dxf")
doc.saveas(out)
print(f"DXF written: {out.resolve()}")
