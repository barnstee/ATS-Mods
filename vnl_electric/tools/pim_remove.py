"""pim_remove.py <src.pim> <out.pim> --box x0 y0 z0 x1 y1 z1 [...]
Copy a model, dropping mesh islands lying completely inside any box; locators/parts/PIT/PIC kept."""
import argparse, os, re
from pim_tool import load, Piece, bounds

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out"); ap.add_argument("--box", type=float, nargs="+", required=True)
a = ap.parse_args()
boxes = [a.box[i:i + 6] for i in range(0, len(a.box), 6)]
lines, bl = load(a.src)
name = os.path.splitext(os.path.basename(a.out))[0]
out, tv, tt, dropped = [], 0, 0, 0
for k, b in bl:
    if k != "Piece":
        out += b
        continue
    p = Piece(b)
    keep = []
    for isl in p.islands():
        vs = {v for t in isl for v in p.tris[t]}
        lo, hi = bounds([p.pos[v] for v in vs])
        if any(all(bx[i] <= lo[i] and hi[i] <= bx[i + 3] for i in range(3)) for bx in boxes):
            dropped += len(isl)
        else:
            keep += isl
    if len(keep) == len(p.tris):
        out += b; tv += len(p.pos); tt += len(keep)
        continue
    keep = sorted(keep) or [0]
    verts = sorted({v for t in keep for v in p.tris[t]})
    remap = {v: i for i, v in enumerate(verts)}
    idx = re.search(r"Index:\s*(\d+)", "\n".join(b[:4])).group(1)
    o = ["Piece {", "     Index: " + idx, "     Material: %d" % p.material, "     VertexCount: %d" % len(verts),
         "     TriangleCount: %d" % len(keep), "     StreamCount: %d" % len(p.streams)]
    for fmt, tag, rows, extra in p.streams:
        o += ["     Stream {", "          Format: " + fmt, "          Tag: " + tag] + extra
        o += ["          %-5d( %s )" % (i, "  ".join(rows[v])) for i, v in enumerate(verts)]
        o.append("     }")
    o.append("     Triangles {")
    o += ["          %-5d( %s )" % (i, "     ".join(str(remap[v]) for v in p.tris[t])) for i, t in enumerate(keep)]
    o += ["     }", "}"]
    out += o; tv += len(verts); tt += len(keep)
txt = "\n".join(out) + "\n"
txt = re.sub(r"(Global \{[^}]*?VertexCount:\s*)\d+", lambda m: m.group(1) + str(tv), txt, count=1)
txt = re.sub(r"(Global \{[^}]*?TriangleCount:\s*)\d+", lambda m: m.group(1) + str(tt), txt, count=1)
txt = re.sub(r"(Global \{[^}]*?Skeleton:\s*)\"[^\"]*\"", lambda m: m.group(1) + "\"\"", txt, count=1)
txt = re.sub(r"(Header \{[^}]*?Name:\s*)\"[^\"]*\"", lambda m: m.group(1) + "\"" + name + "\"", txt, count=1)
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, "w", encoding="utf-8", newline="\n").write(txt)
for ext in (".pit", ".pic"):
    s_path = os.path.splitext(a.src)[0] + ext
    if os.path.isfile(s_path):
        s = open(s_path, encoding="utf-8").read()
        s = re.sub(r"(Header \{[^}]*?Name:\s*)\"[^\"]*\"", lambda m: m.group(1) + "\"" + name + "\"", s, count=1)
        open(os.path.splitext(a.out)[0] + ext, "w", encoding="utf-8", newline="\n").write(s)
print("wrote %s: dropped %d tris" % (a.out, dropped))
