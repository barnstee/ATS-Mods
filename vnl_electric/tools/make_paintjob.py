"""make_paintjob.py <project_dir> [--game <extract dir>] [--logo <logo.jpg>]
                   [--truck <model dir> --cabs <cab:slot:sleeper_m,...> --out <dir under project>]
Airbrush paint mask with the logo on both sleeper sides and the sleeper back, per sleeper cab.
The logo is projected through the cab paint UVs (UV0) triangle by triangle; black logo background = transparent."""
import argparse, os, re, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pim_tool import load, Piece
from PIL import Image

CABS = {"s74h": "0x0", "s74m": "0x2048", "s42m": "0x4096"}   # paint atlas slot of each sleeper cab
SIZE = 2048
GLASS = []
BACK_Y = 0.6          # back logo centre: fraction of the back wall height (0 = bottom, 1 = top)
UV_STREAM = os.environ.get("PJ_UV", "_UV1")   # paint mask UV set of the VNL 2025 cabs
OUT_DIR = ("vehicle", "truck", "upgrade", "paintjob", "volvo_vnl_e", "vnl_electric")


def save_dds(img, path):
    w, h = img.size
    hdr = struct.pack("<4sIIIIIII44sIIIIIIIIIIIII", b"DDS ", 124, 0x100F, h, w, w * 4, 0, 1, b"\0" * 44,
                      32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, 0x1000, 0, 0, 0, 0)
    r, g, b, a = img.split()
    open(path, "wb").write(hdr + Image.merge("RGBA", (b, g, r, a)).tobytes())


def logo_rgba(path):
    im = Image.open(path).convert("RGB")
    a = im.convert("L").point(lambda v: 0 if v < 20 else 255 if v > 60 else int((v - 20) * 255 / 40))
    out = im.copy(); out.putalpha(a)
    return out


def part_pieces(bl, parts):
    """piece indices of the named model parts (None = all pieces)"""
    if not parts:
        return None
    keep = set()
    for k, b in bl:
        if k == "Part":
            txt = "\n".join(b)
            name = re.search(r'Name:\s*"([^"]+)"', txt).group(1)
            if name in parts:
                keep |= {int(x) for x in re.search(r"Pieces:([^\n]*)", txt).group(1).split()}
    return keep


def surfaces(pim, effect="truckpaint", parts=None):
    _, bl = load(pim)
    keep = part_pieces(bl, parts)
    pi = -1
    mats = [b for k, b in bl if k == "Material"]
    paint = {i for i, b in enumerate(mats) if effect in "\n".join(b)}
    tris = []
    for k, b in bl:
        if k != "Piece":
            continue
        pi += 1
        if keep is not None and pi not in keep:
            continue
        p = Piece(b)
        if p.material not in paint:
            continue
        uv = [[float.fromhex("0") for _ in range(2)] for _ in p.pos]
        for f, tg, rows, ex in p.streams:
            if tg == "\"%s\"" % UV_STREAM:
                from pim_tool import hf
                uv = [[hf(t[1:]) for t in r] for r in rows]
        for a, b2, c in p.tris:
            tris.append(([p.pos[a], p.pos[b2], p.pos[c]], [uv[a], uv[b2], uv[c]]))
    return tris


def normal(P):
    ax, ay, az = [P[1][i] - P[0][i] for i in range(3)]
    bx, by, bz = [P[2][i] - P[0][i] for i in range(3)]
    n = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
    l = sum(v * v for v in n) ** 0.5 or 1
    return [-v / l for v in n]          # SCS triangle winding is clockwise


def _covered(sel2d, z, y):
    for (a, b, c) in sel2d:
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        w1 = ((b[1] - c[1]) * (z - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
        w2 = ((c[1] - a[1]) * (z - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
        if w1 >= 0 and w2 >= 0 and w1 + w2 <= 1:
            return True
    return False


def tri_area(P):
    ax, ay, az = [P[1][i] - P[0][i] for i in range(3)]
    bx, by, bz = [P[2][i] - P[0][i] for i in range(3)]
    return 0.5 * ((ay * bz - az * by) ** 2 + (az * bx - ax * bz) ** 2 + (ax * by - ay * bx) ** 2) ** 0.5


def back_plane(tris):
    """z of the sleeper back wall = the back-facing plane with the largest paint area (trim strips can stick out further)"""
    area, zs = {}, {}
    for P, _ in tris:
        if normal(P)[2] > 0.85:
            z = sum(p[2] for p in P) / 3; b = round(z, 1)
            area[b] = area.get(b, 0) + tri_area(P); zs.setdefault(b, []).append(z)
    if not area:
        return None
    b = max(area, key=area.get)
    return sum(zs[b]) / len(zs[b])


def windows(glass):
    """merge glass triangles into window boxes (z0, z1, y0, y1)"""
    boxes = []
    for P, _ in glass:
        b = [min(p[2] for p in P), max(p[2] for p in P), min(p[1] for p in P), max(p[1] for p in P)]
        for g in boxes:
            if b[0] <= g[1] + 0.05 and b[1] >= g[0] - 0.05 and b[2] <= g[3] + 0.05 and b[3] >= g[2] - 0.05:
                g[0], g[1], g[2], g[3] = min(g[0], b[0]), max(g[1], b[1]), min(g[2], b[2]), max(g[3], b[3]); break
        else:
            boxes.append(b)
    return boxes


def place(tris, axis, sign, sleeper, zback=None):
    """returns (selector, h-function, centre h, centre y, size) for one surface.
    SCS cab models: +x = truck right side, -z = forward. zback = sleeper back wall (back_plane)."""
    sel = [t for t in tris if abs(normal(t[0])[axis]) > 0.85 and normal(t[0])[axis] * sign > 0]
    pts = [p for t in sel for p in t[0]]
    if not pts:
        return None
    zmax = zback if zback is not None else max(p[2] for p in pts)
    if axis == 0:
        h = (lambda P: -P[2]) if sign > 0 else (lambda P: P[2])        # viewer sees the truck front on the right (+x side) / left (-x side)
        front = zmax - sleeper + 0.10
        band = [t for t in sel if max(p[2] for p in t[0]) > front - 0.3]
        ys = sorted(p[1] for t in band for p in t[0])
        y_lo, y_hi = ys[len(ys) // 20], ys[-1 - len(ys) // 20]
        side = [t for t in GLASS if abs(normal(t[0])[0]) > 0.6 and normal(t[0])[0] * sign > 0]
        door = [p for t in side if max(q[2] for q in t[0]) < front + 0.1 and min(q[2] for q in t[0]) > front - 1.5 for p in t[0]]
        wins = windows([t for t in side if min(q[2] for q in t[0]) > front - 0.05])   # sleeper windows
        if door:                                     # logo at door window height, never on the door glass
            front = max(front, max(p[2] for p in door) + 0.05)
            yc = (min(p[1] for p in door) + max(p[1] for p in door)) / 2
        elif wins:                                   # else at the height of the largest sleeper window
            w = max(wins, key=lambda g: (g[1] - g[0]) * (g[3] - g[2]))
            yc = (w[2] + w[3]) / 2
        else:
            yc = (y_lo + y_hi) / 2
        size = 0.9
        for _ in range(3):                           # only windows at the logo height limit its width
            block = [g for g in wins if g[2] < yc + size / 2 and g[3] > yc - size / 2]
            if block:
                avail = min(g[0] for g in block) - 0.06 - front
                size = max(0.35, min(0.9, avail, (max(g[3] for g in block) - min(g[2] for g in block)) * 1.6))
                zc = front + avail / 2
            else:
                size = min(0.9, sleeper * 0.5); zc = max(zmax - sleeper / 2, front + size / 2)
        hc = -zc if sign > 0 else zc
        return sel, h, hc, yc, size
    band = [p for t in sel if abs(sum(q[2] for q in t[0]) / 3 - zmax) < 0.15 for p in t[0]] if zback is not None else []
    band = band or [p for p in pts if p[2] > zmax - 0.15]
    width = max(p[0] for p in band) - min(p[0] for p in band)
    ys = sorted(p[1] for p in band)
    y_lo, y_hi = ys[len(ys) // 20], ys[-1 - len(ys) // 20]
    size = min(1.2, width * 0.55, (y_hi - y_lo) * 0.5)
    yc = y_lo + (y_hi - y_lo) * BACK_Y
    return sel, (lambda P: P[0]), 0.0, yc, size


def fit(sel, axis, sign, h, hc, yc, size, sleeper, zback=None):
    """Move/shrink the logo square until it lies completely on the painted surface of this side and keeps
    5 cm away from any glass (side, door and rear windows). Raster of the side in (h, y), 2 cm cells."""
    import numpy as np
    R = 0.02
    hv = (lambda P: P[0]) if axis == 2 else h
    glass = [t for t in GLASS if abs(normal(t[0])[axis]) > 0.6 and normal(t[0])[axis] * sign > 0]
    if axis == 2 and zback is not None:                    # only windows in the back wall, not glass hidden inside the cab
        glass = [t for t in glass if sum(p[2] for p in t[0]) / 3 > zback - 0.3]
    pts = [(hv(p), p[1]) for t in sel for p in t[0]]
    h0, h1 = min(p[0] for p in pts), max(p[0] for p in pts); y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    W, H = int((h1 - h0) / R) + 2, int((y1 - y0) / R) + 2
    def raster(tris):
        g = np.zeros((H, W), bool)
        for P, _ in tris:
            q = [((hv(v) - h0) / R, (v[1] - y0) / R) for v in P]
            xa, xb = max(0, int(min(a for a, _ in q))), min(W - 1, int(max(a for a, _ in q)) + 1)
            ya, yb = max(0, int(min(b for _, b in q))), min(H - 1, int(max(b for _, b in q)) + 1)
            if xa > xb or ya > yb:
                continue
            X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
            (ax, ay), (bx, by), (cx, cy) = q
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            w1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
            w2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
            g[ya:yb + 1, xa:xb + 1] |= (w1 >= -0.05) & (w2 >= -0.05) & (1 - w1 - w2 >= -0.05)
        return g
    paintg, glassg = raster(sel), raster(glass) if glass else np.zeros((H, W), bool)
    m = int(0.05 / R) + 1                                   # 5 cm clearance to glass
    gl = np.zeros_like(glassg)
    for dy in range(-m, m + 1):
        for dx in range(-m, m + 1):
            gl |= np.roll(np.roll(glassg, dy, 0), dx, 1)
    def ok(hc_, yc_, s):
        xa, xb = int((hc_ - s / 2 - h0) / R), int((hc_ + s / 2 - h0) / R)
        ya, yb = int((yc_ - s / 2 - y0) / R), int((yc_ + s / 2 - y0) / R)
        if xa < 0 or ya < 0 or xb >= W or yb >= H:
            return False
        return paintg[ya:yb + 1, xa:xb + 1].mean() > 0.93 and not gl[ya:yb + 1, xa:xb + 1].any()   # small cut-outs (lamp/mount holes) are ok
    if ok(hc, yc, size):
        return hc, yc, size
    if axis == 0:                                           # stay on the sleeper part of the side
        zmax = zback if zback is not None else max(p[2] for t in sel for p in t[0])
        lo, hi = sorted((hv((0, 0, zmax)), hv((0, 0, zmax - sleeper))))
    else:
        lo, hi = h0, h1
    s = max(size, 0.9)
    while s >= 0.3:
        best = None
        for hh in np.arange(lo + s / 2, hi - s / 2 + 1e-6, 0.04):
            for yy in np.arange(y0 + s / 2, y1 - s / 2 + 1e-6, 0.04):
                if ok(hh, yy, s):
                    dd = (hh - hc) ** 2 + (yy - yc) ** 2
                    if best is None or dd < best[0]:
                        best = (dd, float(hh), float(yy))
        if best:
            return best[1], best[2], s
        s = round(s - 0.05, 2)
    return None


def paint(img, logo, tris, h, hc, yc, size):
    px_per_m = SIZE * 0.13
    lw = max(64, int(size * px_per_m * 3))
    lg = logo.resize((lw, lw), Image.LANCZOS)
    L = lg.load(); I = img.load()
    offs = [(-1 / 3, -1 / 3), (0, -1 / 3), (1 / 3, -1 / 3), (-1 / 3, 0), (0, 0), (1 / 3, 0), (-1 / 3, 1 / 3), (0, 1 / 3), (1 / 3, 1 / 3)]
    painted = 0
    for P, U in tris:
        hs = [h(p) for p in P]; ys = [p[1] for p in P]
        if max(hs) < hc - size / 2 or min(hs) > hc + size / 2 or max(ys) < yc - size / 2 or min(ys) > yc + size / 2:
            continue
        px = [(u * SIZE, v * SIZE) for u, v in U]
        x0, x1 = int(max(0, min(p[0] for p in px))), min(SIZE - 1, int(max(p[0] for p in px)) + 1)
        y0, y1 = int(max(0, min(p[1] for p in px))), min(SIZE - 1, int(max(p[1] for p in px)) + 1)
        (ax, ay), (bx, by), (cx, cy) = px
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                acc = [0, 0, 0, 0]; inside = False
                for ox, oy in offs:
                    X, Y = xx + 0.5 + ox, yy + 0.5 + oy
                    w1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
                    w2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
                    w3 = 1 - w1 - w2
                    if w1 < -0.02 or w2 < -0.02 or w3 < -0.02:
                        continue
                    inside = True
                    H = w1 * hs[0] + w2 * hs[1] + w3 * hs[2]; Yw = w1 * ys[0] + w2 * ys[1] + w3 * ys[2]
                    lu = (H - hc) / size + 0.5; lv = 0.5 - (Yw - yc) / size
                    if 0 <= lu < 1 and 0 <= lv < 1:
                        c = L[int(lu * lw), int(lv * lw)]
                        acc[0] += c[0] * c[3]; acc[1] += c[1] * c[3]; acc[2] += c[2] * c[3]; acc[3] += c[3]
                if not inside or acc[3] == 0:
                    continue
                a = acc[3] / len(offs)
                if a > I[xx, yy][3]:
                    I[xx, yy] = (int(acc[0] / acc[3]), int(acc[1] / acc[3]), int(acc[2] / acc[3]), int(a))
                    painted += 1
    return painted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--game", default=r"C:\ATSExtract"); ap.add_argument("--logo", default=os.path.join(os.path.dirname(HERE), "assets", "logo.jpg"))
    ap.add_argument("--truck", default="volvo_vnl2025", help="model folder under /vehicle/truck")
    ap.add_argument("--cabs", default="s74h:0x0:1.88,s74m:0x2048:1.88,s42m:0x4096:1.07",
                    help="cab:atlas slot:sleeper length m or auto[:part+part...],... (parts: only these model parts)")
    ap.add_argument("--model", help="one model for all cabs, e.g. truck (default: cabin/<cab>)")
    ap.add_argument("--back-y", type=float, default=0.6, help="back logo height, fraction of the back wall")
    ap.add_argument("--out", default="/".join(OUT_DIR), help="mask folder under the project")
    a = ap.parse_args()
    global BACK_Y
    BACK_Y = a.back_y
    cabs = [(f[0], f[1], f[2], set(f[3].split("+")) if len(f) > 3 else None) for f in (x.split(":") for x in a.cabs.split(","))]
    root = os.path.dirname(HERE)
    src = os.path.join(root, "blender", "src")
    logo = logo_rgba(a.logo)
    od = os.path.join(a.project, *a.out.split("/")); os.makedirs(od, exist_ok=True)
    for cab, slot, sleeper, parts in cabs:
        rel = a.model if a.model else "cabin/" + cab
        subprocess.run([os.path.join(HERE, "bin", "converter_pix.exe"), "-b", a.game, "-e", src, "-m", "/vehicle/truck/%s/%s" % (a.truck, rel)], capture_output=True)
        pim = os.path.join(src, "vehicle", "truck", a.truck, *(rel + ".pim").split("/"))
        tris = surfaces(pim, parts=parts)
        global GLASS
        GLASS = surfaces(pim, "glass", parts)
        if sleeper == "auto":                               # length of the sleeper parts along z
            zs = [p[2] for P, _ in surfaces(pim, parts={x for x in parts if x.startswith("sleeper")}) for p in P]
            sleeper = round(max(zs) - min(zs), 2)
        sleeper = float(sleeper)
        zback = back_plane(tris)
        img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
        for axis, sign in ((0, 1), (0, -1), (2, 1)):
            r = place(tris, axis, sign, sleeper, zback)
            if r:
                sel, h, hc, yc, size = r
                f = fit(sel, axis, sign, h, hc, yc, size, sleeper, zback)
                if not f:
                    print("%s: surface axis %d sign %+d: no window-free spot for the logo - skipped" % (cab, axis, sign))
                    continue
                if (round(hc, 2), round(yc, 2), size) != (round(f[0], 2), round(f[1], 2), f[2]):
                    print("%s: surface axis %d sign %+d: logo moved off windows/edges (was %.2f m at h %.2f y %.2f)" % (cab, axis, sign, size, hc, yc))
                hc, yc, size = f
                n = paint(img, logo, sel, h, hc, yc, size)
                print("%s: surface axis %d sign %+d logo %.2f m at h %.2f y %.2f -> %d px" % (cab, axis, sign, size, hc, yc, n))
        name = "pjm_at_%s_size_%dx%d" % (slot, SIZE, SIZE)
        save_dds(img, os.path.join(od, name + ".dds"))
        img.save(os.path.join(root, "blender", "%s_%s_preview.png" % (a.truck, name)))
        open(os.path.join(od, name + ".tobj"), "w").write("map 2d %s.dds\naddr clamp_to_edge clamp_to_edge\n" % name)


if __name__ == "__main__":
    main()
