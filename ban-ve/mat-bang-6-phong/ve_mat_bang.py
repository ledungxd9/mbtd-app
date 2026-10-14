#!/usr/bin/env python3
"""Mặt bằng bố trí 6 phòng 10,0 × 10,8 m, dựng lại từ bản phác tay.

Chạy:  python3 ve_mat_bang.py
Ra:    mat-bang.svg  bản vẽ vector (in A4 đúng tỷ lệ 1:100)
       mat-bang.dxf  mở bằng AutoCAD (đơn vị mm, có layer, dim thật)
       mat-bang.png, mat-bang.pdf  nếu máy có Chromium / Chrome
Cần:   pip install shapely ezdxf

Toạ độ mm, gốc ở góc ngoài dưới-trái, trục y hướng lên (như AutoCAD).
Phòng bên phải là ảnh gương của phòng bên trái qua tường giữa.
"""
import math
import os
import shutil
import subprocess
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import box
from shapely.ops import unary_union

OUT = Path(__file__).resolve().parent

# ---------- kích thước chính (mm) ----------
W, D = 10000, 10800                         # phủ bì
T_EXT = 200                                 # tường bao
T_MID = 200                                 # tường giữa: tựa lưng 2 dãy phòng, đi ống WC
T_PART = 100                                # tường ngăn phòng
T_WC = 100                                  # tường WC
ROOM_W = (W - 2 * T_EXT - T_MID) // 2       # 4700 lọt lòng
ROOM_D = (D - 2 * T_EXT - 2 * T_PART) // 3  # 3400 lọt lòng, 3 phòng bằng nhau
WC_W, WC_D = 1900, 1200                     # WC lọt lòng
XM = W // 2

XI = T_EXT                    # mặt trong tường bao bên trái
XC = XM - T_MID // 2          # mặt tường giữa phía phòng trái
XW = XC - WC_W - T_WC         # mặt ngoài tường WC
XS = XC - 700                 # mép khu tắm đứng (700 × 1200)


def row_y0(row):              # row 0 = dãy dưới
    return T_EXT + row * (ROOM_D + T_PART)


# ---------- hình học chung cho SVG + DXF ----------
class Ve:
    def __init__(self):
        self.items, self.walls, self.cuts = [], [], []

    def add(self, kind, layer, **kw):
        self.items.append(dict(kind=kind, layer=layer, **kw))

    def line(self, a, b, layer, **kw): self.add("line", layer, pts=[a, b], closed=False, **kw)
    def pline(self, pts, layer, closed=True, **kw): self.add("pline", layer, pts=pts, closed=closed, **kw)
    def circle(self, c, r, layer, **kw): self.add("circle", layer, c=c, r=r, **kw)
    def ellipse(self, c, rx, ry, layer): self.add("ellipse", layer, c=c, rx=rx, ry=ry)
    def arc(self, c, a, b, layer): self.add("arc", layer, c=c, a=a, b=b)       # cung nhỏ từ a tới b quanh c

    def text(self, p, s, h, layer="chu", rot=0, anchor="mc", bold=False, color=None):
        self.add("text", layer, p=p, s=s, h=h, rot=rot, anchor=anchor, bold=bold, color=color)

    def wall(self, x1, y1, x2, y2): self.walls.append(box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    def cut(self, x1, y1, x2, y2): self.cuts.append(box(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def chain(self, vals, base, horiz, out):
        """Chuỗi kích thước. horiz: đo theo x, đường dim tại y = base; out = +1/-1 phía ra xa nhà."""
        for i in range(len(vals) - 1):
            self.add("dim", "kich-thuoc", a=vals[i], b=vals[i + 1], base=base, horiz=horiz, out=out,
                     first=i == 0, last=i == len(vals) - 2)


def bb(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def cua_di(ve, hinge, closed, opened, t=40):
    """Cánh cửa vẽ ở vị trí mở 90°, cung quét từ mép đóng tới mép mở."""
    ux, uy = opened[0] - hinge[0], opened[1] - hinge[1]
    L = math.hypot(ux, uy)
    nx, ny = -uy / L, ux / L
    if nx * (closed[0] - hinge[0]) + ny * (closed[1] - hinge[1]) < 0:
        nx, ny = -nx, -ny
    leaf = [hinge, opened, (opened[0] + nx * t, opened[1] + ny * t), (hinge[0] + nx * t, hinge[1] + ny * t)]
    ve.pline(leaf, "cua-di")
    ve.arc(hinge, closed, opened, "cua-cung")


def cua_so(ve, x1, y1, x2, y2):
    """Cửa sổ trong tường: 2 nét mặt tường + 2 nét kính."""
    if x2 - x1 < y2 - y1:     # tường đứng
        for k in (0, 1 / 3, 2 / 3, 1):
            x = x1 + (x2 - x1) * k
            ve.line((x, y1), (x, y2), "cua-so")
    else:
        for k in (0, 1 / 3, 2 / 3, 1):
            y = y1 + (y2 - y1) * k
            ve.line((x1, y), (x2, y), "cua-so")


def phong(ve, row, left):
    X = (lambda x: x) if left else (lambda x: W - x)
    P = lambda x, y: (X(x), y)
    R = lambda x1, y1, x2, y2: rect(min(X(x1), X(x2)), y1, max(X(x1), X(x2)), y2)
    y0 = row_y0(row)
    y1 = y0 + ROOM_D
    so = (2 - row) * 2 + (1 if left else 2)

    # nền
    ve.pline(R(XI, y0, XC, y1), "nen-phong")
    ve.pline(R(XW + T_WC, y1 - WC_D, XC, y1), "nen-wc")

    # tường WC
    ve.wall(*bb(R(XW, y1 - WC_D - T_WC, XW + T_WC, y1)))
    ve.wall(*bb(R(XW, y1 - WC_D - T_WC, XC, y1 - WC_D)))

    # D1: cửa đi chính trên tường hông ngoài, bản lề sát góc, mở vào phòng
    ve.cut(*bb(R(0, y0 + 150, T_EXT, y0 + 1050)))
    cua_di(ve, P(XI, y0 + 150), P(XI, y0 + 1050), P(XI + 900, y0 + 150))
    ve.text(P(650, y0 + 1200), "D1", 130, "tag")

    # S1: cửa sổ hông
    ve.cut(*bb(R(0, y0 + 1800, T_EXT, y0 + 3000)))
    cua_so(ve, *bb(R(0, y0 + 1800, T_EXT, y0 + 3000)))
    ve.text(P(420, y0 + 2400), "S1", 130, "tag")

    # D2: cửa WC trên tường WC, mở ra phòng
    ve.cut(*bb(R(XW, y1 - 1100, XW + T_WC, y1 - 400)))
    cua_di(ve, P(XW, y1 - 400), P(XW, y1 - 1100), P(XW - 700, y1 - 400))
    ve.text(P(2550, y1 - 1230), "D2", 130, "tag")

    if row == 0:              # cửa sổ mặt trước
        ve.cut(*bb(R(1850, 0, 3250, T_EXT)))
        cua_so(ve, *bb(R(1850, 0, 3250, T_EXT)))
        ve.text(P(2550, T_EXT + 260), "S2", 130, "tag")
    if row == 2:              # cửa sổ mặt sau + ô thoáng WC
        ve.cut(*bb(R(850, D - T_EXT, 2250, D)))
        cua_so(ve, *bb(R(850, D - T_EXT, 2250, D)))
        ve.text(P(1550, D - T_EXT - 260), "S2", 130, "tag")
        ve.cut(*bb(R(XS + 50, D - T_EXT, XS + 650, D)))
        cua_so(ve, *bb(R(XS + 50, D - T_EXT, XS + 650, D)))
        ve.text(P(XS + 350, y1 - 330), "S3", 120, "tag")
    else:                     # WC kẹp giữa: quạt hút âm trần (nét đứt)
        fx, fy = XW + T_WC + 230, y1 - 950
        ve.pline(R(fx - 110, fy - 110, fx + 110, fy + 110), "thiet-bi", dashed=True, fill=False)
        ve.line(P(fx - 110, fy - 110), P(fx + 110, fy + 110), "thiet-bi", dashed=True)
        ve.line(P(fx - 110, fy + 110), P(fx + 110, fy - 110), "thiet-bi", dashed=True)

    # thiết bị WC: lavabo – xí bệt – tắm đứng
    lx1, lx2 = XW + T_WC + 20, XW + T_WC + 470
    ve.pline(R(lx1, y1 - 380, lx2, y1), "thiet-bi")
    ve.ellipse(P((lx1 + lx2) / 2, y1 - 200), 170, 125, "thiet-bi")
    ve.circle(P((lx1 + lx2) / 2, y1 - 55), 22, "thiet-bi")
    cx = (lx2 + XS) / 2
    ve.pline(R(cx - 225, y1 - 200, cx + 225, y1), "thiet-bi")
    ve.ellipse(P(cx, y1 - 450), 185, 250, "thiet-bi")
    ve.ellipse(P(cx, y1 - 470), 115, 165, "thiet-bi")
    ve.pline(R(XS, y1 - WC_D, XC, y1), "thiet-bi", fill=False)
    ve.line(P(XS, y1 - WC_D), P(XC, y1), "thiet-bi", thin=True)
    ve.line(P(XS, y1), P(XC, y1 - WC_D), "thiet-bi", thin=True)
    ve.circle(P((XS + XC) / 2, y1 - WC_D / 2), 55, "thiet-bi")
    ve.circle(P((XS + XC) / 2, y1 - 90), 60, "thiet-bi")
    ve.text(P(XW + T_WC + 760, y1 - 950), "WC", 150, bold=True)

    # giường 1600 × 2000 tựa tường giữa, đầu giường sát tường WC
    gx = XC - 1600
    ve.pline(R(gx, y0 + 100, XC, y0 + 2100), "noi-that")
    ve.pline(R(gx + 70, y0 + 1660, gx + 770, y0 + 2030), "noi-that")
    ve.pline(R(gx + 830, y0 + 1660, gx + 1530, y0 + 2030), "noi-that")
    ve.line(P(gx, y0 + 1520), P(XC, y0 + 1520), "noi-that")
    ve.line(P(gx, y0 + 1400), P(XC, y0 + 1400), "noi-that")
    ve.text(P(gx + 800, y0 + 850), "GIƯỜNG", 120, color="#77746e")
    ve.text(P(gx + 800, y0 + 640), "1600×2000", 110, color="#77746e")

    # tên phòng
    ve.text(P(1550, y0 + 1950), f"PHÒNG {so:02d}", 220, bold=True)
    s = ROOM_W * ROOM_D / 1e6
    ve.text(P(1550, y0 + 1640), f"S = {s:.1f} m²".replace(".", ","), 160)


def dung():
    ve = Ve()
    # tường bao, tường giữa, tường ngăn
    ve.wall(0, 0, W, T_EXT)
    ve.wall(0, D - T_EXT, W, D)
    ve.wall(0, 0, T_EXT, D)
    ve.wall(W - T_EXT, 0, W, D)
    ve.wall(XM - T_MID // 2, 0, XM + T_MID // 2, D)
    for row in (1, 2):
        y = row_y0(row)
        ve.wall(0, y - T_PART, W, y)
    for row in range(3):
        for left in (True, False):
            phong(ve, row, left)

    # kích thước
    side = [0]
    for row in range(3):
        y0 = row_y0(row)
        side += [y0 + 150, y0 + 1050, y0 + 1800, y0 + 3000]
    side += [D]
    walls_y = [0, T_EXT]
    for row in range(3):
        walls_y += [row_y0(row) + ROOM_D, row_y0(row) + ROOM_D + (T_PART if row < 2 else T_EXT)]
    ve.chain(side, -700, False, -1)
    ve.chain(walls_y, -1250, False, -1)
    ve.chain([0, D], -1800, False, -1)
    ve.chain(side, W + 700, False, 1)
    ve.chain([0, D], W + 1250, False, 1)
    ve.chain([0, 1850, 3250, W - 3250, W - 1850, W], -700, True, -1)
    ve.chain([0, T_EXT, XC, XC + T_MID, W - T_EXT, W], -1250, True, -1)
    ve.chain([0, W], -1800, True, -1)
    top = [0, 850, 2250, XS + 50, XS + 650]
    ve.chain(top + [W - x for x in reversed(top)], D + 700, True, 1)
    ve.chain([0, W], D + 1250, True, 1)

    # tên bản vẽ + bảng
    ve.text((W / 2, -2650), "MẶT BẰNG BỐ TRÍ 6 PHÒNG", 380, bold=True)
    ve.text((W / 2, -3100), "TỶ LỆ 1:100  ·  Diện tích xây dựng 10,0 × 10,8 = 108,0 m²", 170)

    cols = [-2100, -1200, 2600, 4200, 4800]
    rows = [
        ("KÝ HIỆU", "LOẠI CỬA", "RỘNG × CAO", "SL"),
        ("D1", "Cửa đi chính, 1 cánh, mở vào", "900 × 2200", "6"),
        ("D2", "Cửa WC, 1 cánh, mở ra", "700 × 2100", "6"),
        ("S1", "Cửa sổ hông, bậu cao 900", "1200 × 1400", "6"),
        ("S2", "Cửa sổ trước / sau, bậu cao 900", "1400 × 1400", "4"),
        ("S3", "Ô thoáng WC, bậu cao 1800", "600 × 400", "2"),
    ]
    ty, rh = -3850, 360
    ve.text((cols[0], ty + 170), "BẢNG THỐNG KÊ CỬA", 170, anchor="bl", bold=True)
    for i in range(len(rows) + 1):
        ve.line((cols[0], ty - i * rh), (cols[-1], ty - i * rh), "khung")
    for x in cols:
        ve.line((x, ty), (x, ty - len(rows) * rh), "khung")
    for i, r in enumerate(rows):
        yc = ty - i * rh - rh / 2
        for j, cell in enumerate(r):
            if j == 1 and i > 0:
                ve.text((cols[1] + 100, yc), cell, 130, anchor="ml")
            else:
                ve.text(((cols[j] + cols[j + 1]) / 2, yc), cell, 130, bold=i == 0)

    nx = 5300
    ve.text((nx, ty + 170), "GHI CHÚ", 170, anchor="bl", bold=True)
    notes = [
        "1. Kích thước ghi bằng mm.",
        "2. Tường bao, tường giữa dày 200; tường ngăn phòng, WC dày 100.",
        "3. Mỗi phòng lọt lòng 4,70 × 3,40 m = 16,0 m² (gồm WC).",
        "4. WC lọt lòng 1,90 × 1,20 m: lavabo, xí bệt, tắm đứng.",
        "    Sàn WC thấp hơn sàn phòng 30 ÷ 50 mm.",
        "5. Ô vuông gạch chéo nét đứt: quạt hút âm trần + ống thoát khí",
        "    cho WC phòng 03 ÷ 06 (không giáp tường ngoài).",
    ]
    for i, s in enumerate(notes):
        indent = 250 if s.startswith(" ") else 0        # dòng nối tiếp lùi vào
        ve.text((nx + indent, ty - 230 - i * 300), s.strip(), 130, anchor="ml")
    return ve


# ---------- SVG ----------
SVG_STYLE = {
    "nen-phong": 'fill="#f6f3ec" stroke="none"',
    "nen-wc": 'fill="#e4eef3" stroke="none"',
    "noi-that": 'fill="#ffffff" stroke="#77746e" stroke-width="9"',
    "thiet-bi": 'fill="#ffffff" stroke="#2f6f8a" stroke-width="9"',
    "cua-di": 'fill="#ffffff" stroke="#1d1d1d" stroke-width="10"',
    "cua-cung": 'fill="none" stroke="#1d1d1d" stroke-width="6"',
    "cua-so": 'fill="none" stroke="#1d1d1d" stroke-width="9"',
    "kich-thuoc": 'fill="none" stroke="#3a3a3a" stroke-width="7"',
    "khung": 'fill="none" stroke="#333333" stroke-width="9"',
}
ORDER = ["nen-phong", "nen-wc", "noi-that", "thiet-bi", "tuong", "cua-so", "cua-di", "cua-cung",
         "kich-thuoc", "khung", "tag", "chu"]
DIM_H = 160


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def svg_text(it):
    x, y = it["p"]
    h = it["h"] * 1.38                      # chiều cao chữ hoa → cỡ chữ
    ta = "start" if it["anchor"][1] == "l" else "middle"
    base = ' dominant-baseline="central"' if it["anchor"][0] == "m" else ""
    rot = f' transform="rotate({-it["rot"]} {f(x)} {f(-y)})"' if it["rot"] else ""
    color = it.get("color") or ("#555555" if it["layer"] == "tag" else "#111111")
    weight = ' font-weight="700"' if it["bold"] else ""
    style = ' font-style="italic"' if it["layer"] == "tag" else ""
    s = it["s"].replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{f(x)}" y="{f(-y)}" font-size="{f(h)}" text-anchor="{ta}"{base}{weight}{style}'
            f' fill="{color}"{rot}>{s}</text>')


def svg_dim(it):
    a, b, base, out, horiz = it["a"], it["b"], it["base"], it["out"], it["horiz"]
    P = (lambda u, v: (u, v)) if horiz else (lambda u, v: (v, u))
    seg = []
    for u in (a, b):
        p1, p2 = P(u, base - out * 250), P(u, base + out * 80)
        seg.append(f"M{f(p1[0])} {f(-p1[1])}L{f(p2[0])} {f(-p2[1])}")
        t1, t2 = P(u - 55, base - 55), P(u + 55, base + 55)
        seg.append(f'M{f(t1[0])} {f(-t1[1])}L{f(t2[0])} {f(-t2[1])}')
    p1, p2 = P(a - 80, base), P(b + 80, base)
    seg.append(f"M{f(p1[0])} {f(-p1[1])}L{f(p2[0])} {f(-p2[1])}")
    out_svg = [f'<path d="{"".join(seg[:4:2])}{seg[4]}" {SVG_STYLE["kich-thuoc"]}/>',
               f'<path d="{seg[1]}{seg[3]}" fill="none" stroke="#1d1d1d" stroke-width="16"/>']
    s = str(abs(b - a))
    tw = len(s) * 0.62 * DIM_H * 1.38
    mid = (a + b) / 2
    if abs(b - a) < tw + 60:
        if it["first"]:
            mid = a - tw / 2 - 90
        elif it["last"]:
            mid = b + tw / 2 + 90
    if horiz:
        t = dict(p=(mid, base + 60), rot=0)
    else:
        t = dict(p=(base - 60, mid), rot=90)
    out_svg.append(svg_text(dict(t, s=s, h=DIM_H, anchor="bc", bold=False, layer="chu", color="#222222")))
    return "\n".join(out_svg)


def to_svg(ve, view, size):
    x0, y0, x1, y1 = view
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {-y1} {x1 - x0} {y1 - y0}" {size} '
         f'font-family="Arial, \'Liberation Sans\', \'DejaVu Sans\', sans-serif" stroke-linejoin="round">',
         f'<rect x="{x0}" y="{-y1}" width="{x1 - x0}" height="{y1 - y0}" fill="#ffffff"/>']
    walls = unary_union(ve.walls).difference(unary_union(ve.cuts))
    by = {k: [] for k in ORDER}
    for it in ve.items:
        by[it["layer"]].append(it)
    for layer in ORDER:
        if layer == "tuong":
            d = []
            for poly in getattr(walls, "geoms", [walls]):
                for ring in [poly.exterior, *poly.interiors]:
                    c = list(ring.coords)
                    d.append("M" + "L".join(f"{f(x)} {f(-y)}" for x, y in c) + "Z")
            o.append(f'<path d="{"".join(d)}" fill="#1d1d1d" fill-rule="evenodd"/>')
            continue
        for it in by[layer]:
            st = SVG_STYLE.get(layer, "")
            k = it["kind"]
            if k in ("line", "pline"):
                if k == "line" or it.get("fill") is False:
                    st = st.replace('fill="#ffffff"', 'fill="none"')
                if it.get("dashed"):
                    st += ' stroke-dasharray="45 35"'
                if it.get("thin"):
                    st = st.replace('stroke-width="9"', 'stroke-width="5"')
                pts = " ".join(f"{f(x)},{f(-y)}" for x, y in it["pts"])
                tag = "polygon" if it["closed"] else "polyline"
                o.append(f'<{tag} points="{pts}" {st}/>')
            elif k == "circle":
                o.append(f'<circle cx="{f(it["c"][0])}" cy="{f(-it["c"][1])}" r="{f(it["r"])}" {st}/>')
            elif k == "ellipse":
                o.append(f'<ellipse cx="{f(it["c"][0])}" cy="{f(-it["c"][1])}" rx="{f(it["rx"])}" '
                         f'ry="{f(it["ry"])}" {st}/>')
            elif k == "arc":
                (cx, cy), (ax, ay), (bx, by_) = it["c"], it["a"], it["b"]
                r = math.hypot(ax - cx, ay - cy)
                cr = (ax - cx) * (by_ - cy) - (ay - cy) * (bx - cx)
                o.append(f'<path d="M{f(ax)} {f(-ay)}A{f(r)} {f(r)} 0 0 {1 if cr > 0 else 0} {f(bx)} {f(-by_)}" {st}/>')
            elif k == "text":
                o.append(svg_text(it))
            elif k == "dim":
                o.append(svg_dim(it))
    o.append("</svg>")
    return "\n".join(o)


# ---------- DXF ----------
DXF_LAYERS = {   # layer: (tên, màu ACI, nét mm)
    "tuong": ("TUONG", 7, 0.50), "cua-di": ("CUA_DI", 2, 0.25), "cua-cung": ("CUA_DI", 2, 0.25),
    "cua-so": ("CUA_SO", 4, 0.25), "noi-that": ("NOI_THAT", 8, 0.18), "thiet-bi": ("THIET_BI_VS", 5, 0.18),
    "kich-thuoc": ("KICH_THUOC", 3, 0.13), "khung": ("KHUNG", 7, 0.25), "chu": ("CHU", 7, 0.18),
    "tag": ("CHU", 7, 0.18),
}
ALIGN = {"mc": TextEntityAlignment.MIDDLE_CENTER, "bc": TextEntityAlignment.BOTTOM_CENTER,
         "ml": TextEntityAlignment.MIDDLE_LEFT, "bl": TextEntityAlignment.LEFT}


def to_dxf(ve, path):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$LTSCALE"] = 10
    doc.styles.add("VN_ARIAL", font="arial.ttf")
    doc.styles.add("VN_ARIAL_B", font="arialbd.ttf")
    for name, color, lw in {v[0]: v for v in DXF_LAYERS.values()}.values():
        doc.layers.add(name, color=color, lineweight=int(lw * 100))
    ds = doc.dimstyles.new("TL100")
    ds.dxf.dimtxsty = "VN_ARIAL"
    ds.dxf.dimtxt = DIM_H
    ds.dxf.dimtsz = 60          # gạch xiên thay mũi tên
    ds.dxf.dimexe = 80
    ds.dxf.dimexo = 50
    ds.dxf.dimgap = 50
    ds.dxf.dimtad = 1
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    ds.dxf.dimdec = 0
    ds.dxf.dimdle = 80
    msp = doc.modelspace()

    walls = unary_union(ve.walls).difference(unary_union(ve.cuts))
    hatch = msp.add_hatch(color=8, dxfattribs={"layer": "TUONG"})
    for poly in getattr(walls, "geoms", [walls]):
        hatch.paths.add_polyline_path(list(poly.exterior.coords)[:-1], is_closed=True, flags=1)
        for ring in poly.interiors:
            hatch.paths.add_polyline_path(list(ring.coords)[:-1], is_closed=True)
        for ring in [poly.exterior, *poly.interiors]:
            msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": "TUONG"})

    for it in ve.items:
        if it["layer"].startswith("nen"):
            continue
        lay = DXF_LAYERS[it["layer"]][0]
        at = {"layer": lay}
        if it.get("dashed"):
            at["linetype"] = "DASHED"
        k = it["kind"]
        if k in ("line", "pline"):
            msp.add_lwpolyline(it["pts"], close=it["closed"], dxfattribs=at)
        elif k == "circle":
            msp.add_circle(it["c"], it["r"], dxfattribs=at)
        elif k == "ellipse":
            rx, ry = it["rx"], it["ry"]
            major = (rx, 0) if rx >= ry else (0, ry)
            msp.add_ellipse(it["c"], major_axis=major, ratio=min(rx, ry) / max(rx, ry), dxfattribs=at)
        elif k == "arc":
            (cx, cy), (ax, ay), (bx, by_) = it["c"], it["a"], it["b"]
            r = math.hypot(ax - cx, ay - cy)
            sa = math.degrees(math.atan2(ay - cy, ax - cx))
            ea = math.degrees(math.atan2(by_ - cy, bx - cx))
            if (ax - cx) * (by_ - cy) - (ay - cy) * (bx - cx) < 0:
                sa, ea = ea, sa
            msp.add_arc((cx, cy), r, sa, ea, dxfattribs=at)
        elif k == "text":
            at["style"] = "VN_ARIAL_B" if it["bold"] else "VN_ARIAL"
            at["height"] = it["h"]
            at["rotation"] = it["rot"]
            msp.add_text(it["s"], dxfattribs=at).set_placement(it["p"], align=ALIGN[it["anchor"]])
        elif k == "dim":
            a, b, base, out = it["a"], it["b"], it["base"], it["out"]
            if it["horiz"]:
                d = msp.add_linear_dim(base=((a + b) / 2, base), p1=(a, base - out * 300), p2=(b, base - out * 300),
                                       angle=0, dimstyle="TL100", dxfattribs={"layer": lay})
            else:
                d = msp.add_linear_dim(base=(base, (a + b) / 2), p1=(base - out * 300, a), p2=(base - out * 300, b),
                                       angle=90, dimstyle="TL100", dxfattribs={"layer": lay})
            d.render()
    doc.saveas(path)


def chrome():
    for c in (os.environ.get("CHROME"), shutil.which("chromium"), shutil.which("google-chrome"),
              "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        if c and Path(c).exists():
            return c
    return None


if __name__ == "__main__":
    ve = dung()
    view = (-2400, -6300, 12200, 12700)            # 146 × 190 mm khi in 1:100
    wmm, hmm = (view[2] - view[0]) / 100, (view[3] - view[1]) / 100
    svg = to_svg(ve, view, f'width="{f(wmm)}mm" height="{f(hmm)}mm"')
    (OUT / "mat-bang.svg").write_text(svg, encoding="utf-8")
    to_dxf(ve, OUT / "mat-bang.dxf")
    print("Đã ghi mat-bang.svg, mat-bang.dxf")

    exe = chrome()
    if exe:
        tmp = OUT / "_in.html"
        flags = [exe, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars"]
        px_w, px_h = round(wmm * 96 / 25.4), round(hmm * 96 / 25.4)
        tmp.write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0}}svg{{display:block;'
                       f'width:{px_w}px;height:{px_h}px}}</style>{svg}', encoding="utf-8")
        # cửa sổ headless thấp hơn --window-size một chút → chụp dư rồi cắt đúng khổ
        subprocess.run(flags + ["--force-device-scale-factor=4", f"--window-size={px_w},{px_h + 200}",
                                f"--screenshot={OUT / 'mat-bang.png'}", tmp.as_uri()],
                       check=True, capture_output=True)
        try:
            from PIL import Image
            with Image.open(OUT / "mat-bang.png") as im:
                im.crop((0, 0, px_w * 4, px_h * 4)).save(OUT / "mat-bang.png")
        except ImportError:
            pass
        tmp.write_text('<!doctype html><meta charset="utf-8"><style>@page{size:A4 portrait;margin:0}'
                       'html,body{margin:0}.s{width:210mm;height:297mm;display:flex;align-items:center;'
                       f'justify-content:center}}</style><div class="s">{svg}</div>', encoding="utf-8")
        subprocess.run(flags + ["--no-pdf-header-footer", f"--print-to-pdf={OUT / 'mat-bang.pdf'}", tmp.as_uri()],
                       check=True, capture_output=True)
        tmp.unlink()
        print("Đã ghi mat-bang.png, mat-bang.pdf")
