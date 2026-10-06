"""pim_compose.py <src.pim> <out.pim> <ops.json>
Build one model out of several copies of mesh islands from <src>.
ops.json: [{"box": [x0,y0,z0,x1,y1,z1], "offset": [dx,dy,dz], "scale_z": 1.0}, ...]
islands lying completely inside "box" are copied, z-scaled about the box centre, then offset."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pim_tool import load, blocks, Piece, bounds, hf, fh

src, out_path, ops = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3]))
lines, bl = load(src)
mats = [b for k, b in bl if k == "Material"]
pieces = [Piece(b) for k, b in bl if k == "Piece"]
isl = [(p, [(i, bounds([p.pos[v] for v in {v for t in i for v in p.tris[t]}])) for i in p.islands()]) for p in pieces]
used, out_pieces, tv, tt = [], [], 0, 0
for op in ops:
    bx, (dx, dy, dz), sz = op["box"], op["offset"], op.get("scale_z", 1.0)
    zc = (bx[2] + bx[5]) / 2
    for p, il in isl:
        keep = [t for i, (lo, hi) in il if all(bx[k] <= lo[k] and hi[k] <= bx[k + 3] for k in range(3)) for t in i]
        if not keep:
            continue
        verts = sorted({v for t in keep for v in p.tris[t]})
        remap = {v: i for i, v in enumerate(verts)}
        if p.material not in used:
            used.append(p.material)
        o = ["Piece {", "     Index: %d" % len(out_pieces), "     Material: %d" % used.index(p.material),
             "     VertexCount: %d" % len(verts), "     TriangleCount: %d" % len(keep), "     StreamCount: %d" % len(p.streams)]
        for fmt, tag, rows, extra in p.streams:
            o += ["     Stream {", "          Format: " + fmt, "          Tag: " + tag] + extra
            for i, v in enumerate(verts):
                r = rows[v]
                if tag == "\"_POSITION\"":
                    x, y, z = [hf(t[1:]) for t in r]
                    us = op.get("scale", 1.0); xc, yc = (bx[0] + bx[3]) / 2, (bx[1] + bx[4]) / 2
                    r = [fh(xc + (x - xc) * us + dx), fh(yc + (y - yc) * us + dy), fh(zc + (z - zc) * sz * us + dz)]
                o.append("          %-5d( %s )" % (i, "  ".join(r)))
            o.append("     }")
        o.append("     Triangles {")
        o += ["          %-5d( %s )" % (i, "     ".join(str(remap[v]) for v in p.tris[t])) for i, t in enumerate(keep)]
        o += ["     }", "}"]
        out_pieces.append(o); tv += len(verts); tt += len(keep)
name = os.path.splitext(os.path.basename(out_path))[0]
res = ["Header {", "     FormatVersion: 5", "     Source: \"pim_compose\"", "     Type: \"Model\"", "     Name: \"%s\"" % name, "}",
       "Global {", "     VertexCount: %d" % tv, "     TriangleCount: %d" % tt, "     MaterialCount: %d" % len(used),
       "     PieceCount: %d" % len(out_pieces), "     PartCount: 1", "     BoneCount: 0", "     LocatorCount: 0", "     Skeleton: \"\"", "}"]
for m in used:
    res += mats[m]
for po in out_pieces:
    res += po
res += ["Part {", "     Name: \"defaultpart\"", "     PieceCount: %d" % len(out_pieces), "     LocatorCount: 0",
        "     Pieces: %s " % " ".join(str(i) for i in range(len(out_pieces))), "     Locators: ", "}"]
os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
open(out_path, "w", encoding="utf-8", newline="\n").write("\n".join(res) + "\n")
pit = blocks(open(os.path.splitext(src)[0] + ".pit", encoding="utf-8").read().splitlines())
o = []
for k, b in pit:
    if k == "Header":
        o += [re.sub(r"Name:\s*\".*\"", "Name: \"%s\"" % name, l) for l in b]
    elif k == "Global":
        o += [re.sub(r"MaterialCount:\s*\d+", "MaterialCount: %d" % len(used), l) for l in b]
    elif k == "Look":
        inner = [x for x in blocks(b[1:-1]) if x[0] == "Material"]
        head = [l for l in b[1:-1] if l.strip().startswith("Name:")][:1]
        o += [b[0]] + head + [l for m in used for l in inner[m][1]] + [b[-1]]
    else:
        o += b
open(os.path.splitext(out_path)[0] + ".pit", "w", encoding="utf-8", newline="\n").write("\n".join(o) + "\n")
print("wrote %s: %d pieces, %d tris" % (out_path, len(out_pieces), tt))
