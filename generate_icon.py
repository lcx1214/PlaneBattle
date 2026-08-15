# -*- coding: utf-8 -*-
"""Generate app icons for the "飞机大战" (Plane War) game.

Produces:
  - app_icon.png  512x512 RGBA (rounded-rect gradient + pixel "士" plane)
  - app_icon.ico  multi-size ICO (16/32/48/64/128/256)
"""
from PIL import Image, ImageDraw

SIZE = 512

# ---------- background: rounded rect with vertical gradient ----------
MARGIN = 16
RADIUS = 80
BOX = (MARGIN, MARGIN, SIZE - MARGIN, SIZE - MARGIN)

TOP = (0x1F, 0x3A, 0x52)      # #1f3a52
BOTTOM = (0x2E, 0x6D, 0xA4)   # #2e6da4


def _lerp(a, b, t):
    return round(a + (b - a) * t)


# Build a full-canvas gradient, then mask it to a rounded rectangle.
grad = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(BOX[1], BOX[3] + 1):
    t = (y - BOX[1]) / (BOX[3] - BOX[1])
    color = (
        _lerp(TOP[0], BOTTOM[0], t),
        _lerp(TOP[1], BOTTOM[1], t),
        _lerp(TOP[2], BOTTOM[2], t),
        255,
    )
    gd.line([(BOX[0], y), (BOX[2], y)], fill=color)

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle(BOX, radius=RADIUS, fill=255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)
draw = ImageDraw.Draw(img)

# ---------- "士"-shaped pixel plane ----------
CELL = 56        # cell size (pixels)
GAP = 12         # gap between cells
RED = (232, 70, 70, 255)
WHITE = (255, 255, 255, 255)

# rows: (number of cells, color)  -> nose / main wings / fuselage / tail
ROWS = [
    (1, RED),    # 机头 (nose)
    (5, WHITE),  # 主翼 (main wings)
    (1, WHITE),  # 机身 (fuselage)
    (3, WHITE),  # 尾翼 (tail)
]

PLANE_TOP = 120
PLANE_CX = SIZE // 2

y = PLANE_TOP
for n, color in ROWS:
    row_w = n * CELL + (n - 1) * GAP
    x = PLANE_CX - row_w // 2
    for i in range(n):
        cx = x + i * (CELL + GAP)
        draw.rectangle([cx, y, cx + CELL, y + CELL], fill=color)
    y += CELL + GAP

plane_bottom = y - GAP  # last row bottom edge

# ---------- motion trail (dashed, light) below the plane ----------
TRAIL_TOP = plane_bottom + 16
TRAIL_BOTTOM = BOX[3] - 26
TRAIL_COLOR = (190, 214, 240, 200)
DASH = 18
DGAP = 12
TW = 3  # half width

ty = TRAIL_TOP
while ty < TRAIL_BOTTOM:
    draw.rectangle(
        [PLANE_CX - TW, ty, PLANE_CX + TW, min(ty + DASH, TRAIL_BOTTOM)],
        fill=TRAIL_COLOR,
    )
    ty += DASH + DGAP

# ---------- save ----------
img.save("app_icon.png", format="PNG")
img.save(
    "app_icon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("done: app_icon.png + app_icon.ico")
