"""make_paintjob.py <project_dir> [--game <extract dir>] [--logo <logo.jpg>]
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


def surfaces(pim, effect="truckpaint"):
    _, bl = load(pim)
    mats = [b for k, b in bl if k == "Material"]
    paint = {i for i, b in enumerate(mats) if effect in "\n".join(b)}
    tris = []
    for k, b in bl:
        if k != "Piece":
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


def place(tris, axis, sign, sleeper):
    """returns (selector, h-function, centre h, centre y, size) for one surface.
    SCS cab models: +x = truck right side, -z = forward."""
    sel = [t for t in tris if abs(normal(t[0])[axis]) > 0.85 and normal(t[0])[axis] * sign > 0]
    pts = [p for t in sel for p in t[0]]
    if not pts:
        return None
    zmax = max(p[2] for p in pts)
    if axis == 0:
        h = (lambda P: -P[2]) if sign > 0 else (lambda P: P[2])        # viewer sees the truck front on the right (+x side) / left (-x side)
        front = zmax - sleeper + 0.10
        band = [t for t in sel if max(p[2] for p in t[0]) > front - 0.3]
        ys = sorted(p[1] for t in band for p in t[0])
        y_lo, y_hi = ys[len(ys) // 20], ys[-1 - len(ys) // 20]
        holes = [(p[2], p[1]) for t in GLASS if abs(normal(t[0])[0]) > 0.6 and normal(t[0])[0] * sign > 0
                 and min(q[2] for q in t[0]) > front - 0.05 for p in t[0]]
        door = [p for t in GLASS if abs(normal(t[0])[0]) > 0.6 and normal(t[0])[0] * sign > 0
                and max(q[2] for q in t[0]) < front + 0.1 for p in t[0]]
        if door:                                     # logo at door window height, never on the door glass
            front = max(front, max(p[2] for p in door) + 0.05)
        if holes:
            win_front = min(z for z, y in holes)
            win_ys = [y for z, y in holes]
            yc = (min(win_ys) + max(win_ys)) / 2
            if door:
                yc = (min(p[1] for p in door) + max(p[1] for p in door)) / 2
            avail = win_front - 0.06 - front
            size = max(0.35, min(0.9, avail, (max(win_ys) - min(win_ys)) * 1.6))
            zc = front + avail / 2
        else:
            size = min(0.9, sleeper * 0.5); zc = zmax - sleeper / 2; yc = (y_lo + y_hi) / 2
            if door:
                yc = (min(p[1] for p in door) + max(p[1] for p in door)) / 2
                zc = max(zc, front + size / 2)
        hc = -zc if sign > 0 else zc
        return sel, h, hc, yc, size
    band = [p for p in pts if p[2] > zmax - 0.15]
    width = max(p[0] for p in band) - min(p[0] for p in band)
    ys = sorted(p[1] for p in band)
    y_lo, y_hi = ys[len(ys) // 20], ys[-1 - len(ys) // 20]
    size = min(1.2, width * 0.55, (y_hi - y_lo) * 0.5)
    yc = y_lo + (y_hi - y_lo) * 0.6
    return sel, (lambda P: P[0]), 0.0, yc, size


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
    a = ap.parse_args()
    root = os.path.dirname(HERE)
    src = os.path.join(root, "blender", "src")
    logo = logo_rgba(a.logo)
    od = os.path.join(a.project, *OUT_DIR); os.makedirs(od, exist_ok=True)
    for cab, slot in CABS.items():
        subprocess.run([os.path.join(HERE, "bin", "converter_pix.exe"), "-b", a.game, "-e", src, "-m", "/vehicle/truck/volvo_vnl2025/cabin/" + cab], capture_output=True)
        tris = surfaces(os.path.join(src, "vehicle", "truck", "volvo_vnl2025", "cabin", cab + ".pim"))
        global GLASS
        GLASS = surfaces(os.path.join(src, "vehicle", "truck", "volvo_vnl2025", "cabin", cab + ".pim"), "glass")
        sleeper = 1.88 if cab.startswith("s74") else 1.07
        img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
        for axis, sign in ((0, 1), (0, -1), (2, 1)):
            r = place(tris, axis, sign, sleeper)
            if r:
                sel, h, hc, yc, size = r
                n = paint(img, logo, sel, h, hc, yc, size)
                print("%s: surface axis %d sign %+d logo %.2f m at h %.2f y %.2f -> %d px" % (cab, axis, sign, size, hc, yc, n))
        name = "pjm_at_%s_size_%dx%d" % (slot, SIZE, SIZE)
        save_dds(img, os.path.join(od, name + ".dds"))
        img.save(os.path.join(root, "blender", name + "_preview.png"))
        open(os.path.join(od, name + ".tobj"), "w").write("map 2d %s.dds\naddr clamp_to_edge clamp_to_edge\n" % name)


if __name__ == "__main__":
    main()
