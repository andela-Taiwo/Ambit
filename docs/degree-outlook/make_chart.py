#!/usr/bin/env python3
"""Generate the pay-range chart used in the degree outlook report."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "pay_ranges.png"

NAVY = (14, 36, 56)
TEAL = (31, 111, 120)
TEAL_LIGHT = (223, 236, 236)
GOLD = (192, 139, 62)
INK = (26, 26, 26)
GRAY = (95, 107, 115)
RULE = (213, 221, 226)

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
REG = str(FONT_DIR / "Arial.ttf")
BOLD = str(FONT_DIR / "Arial Bold.ttf")

W, H = 2100, 1180
LEFT, RIGHT, TOP, BOTTOM = 640, 210, 170, 130

rows = [
    ("Teaching (private secondary)", 80, 200),
    ("Journalism / editorial", 100, 300),
    ("Federal civil service (GL 08)", 123, 180),
    ("Admissions / visa consulting", 150, 300),
    ("Corporate communications", 150, 400),
    ("Bank graduate trainee", 200, 450),
    ("INGO programme officer", 250, 600),
    ("Tech / global remote", 300, 900),
    ("Oil & gas community relations", 400, 900),
]

x_max = 1000
plot_w = W - LEFT - RIGHT
plot_h = H - TOP - BOTTOM
bar_h = 52
gap = (plot_h - bar_h * len(rows)) / (len(rows) - 1)


def x_of(value: float) -> float:
    return LEFT + (value / x_max) * plot_w


img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

f_title = ImageFont.truetype(BOLD, 46)
f_sub = ImageFont.truetype(REG, 30)
f_label = ImageFont.truetype(REG, 31)
f_value = ImageFont.truetype(REG, 28)
f_axis = ImageFont.truetype(REG, 26)

d.text((90, 40), "Monthly gross pay at entry level (NGN, thousands)", font=f_title, fill=NAVY)
d.text((90, 102), "Bar spans the observed range  \u00b7  dot marks the midpoint", font=f_sub, fill=GRAY)

# gridlines
for tick in range(0, x_max + 1, 200):
    x = x_of(tick)
    d.line([(x, TOP - 18), (x, TOP + plot_h + 6)], fill=RULE, width=2)
    label = f"{tick:,}" if tick else "0"
    tw = d.textlength(label, font=f_axis)
    d.text((x - tw / 2, TOP + plot_h + 22), label, font=f_axis, fill=GRAY)

for i, (name, lo, hi) in enumerate(rows):
    y = TOP + i * (bar_h + gap)
    mid = (lo + hi) / 2
    d.text((LEFT - 34, y + bar_h / 2 - 20), name, font=f_label, fill=INK, anchor="ra")
    x0, x1 = x_of(lo), x_of(hi)
    d.rounded_rectangle([x0, y, x1, y + bar_h], radius=12, fill=TEAL_LIGHT, outline=TEAL, width=2)
    cx = x_of(mid)
    d.ellipse([cx - 11, y + bar_h / 2 - 11, cx + 11, y + bar_h / 2 + 11], fill=NAVY)
    label = f"{lo:,}\u2013{hi:,}" if lo != hi else f"{lo:,}"
    d.text((x1 + 22, y + bar_h / 2 - 18), label, font=f_value, fill=GRAY)

d.line([(LEFT, TOP + plot_h + 6), (W - RIGHT, TOP + plot_h + 6)], fill=NAVY, width=3)

img.save(OUT, "PNG", optimize=True)
print(f"wrote {OUT}")
