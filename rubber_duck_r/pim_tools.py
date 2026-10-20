"""Read / transform ConverterPIX .pim text models.

python pim_bbox.py a.pim [b.pim ...]   prints the bounding box of every model
"""
import re
import struct
import sys

NUM = r"(&[0-9a-fA-F]{8}|[-+\d.eE]+)"
POS_STREAM = re.compile(r'(Tag:\s*"_POSITION"\s*\n)(.*?)(\n\s*\})', re.S)
VEC = re.compile(r"\(\s*%s\s+%s\s+%s\s*\)" % (NUM, NUM, NUM))


def f2(s):
	return struct.unpack(">f", bytes.fromhex(s[1:]))[0] if s.startswith("&") else float(s)


def h(v):
	return "&" + struct.pack(">f", v).hex()


def positions(text):
	for m in POS_STREAM.finditer(text):
		for v in VEC.finditer(m.group(2)):
			yield tuple(f2(x) for x in v.groups())


def bbox(text):
	pts = list(positions(text))
	return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


def transform(text, fn):
	"""Apply fn((x, y, z)) -> (x, y, z) to every _POSITION vertex and locator position."""
	def vec(v):
		return "( %s  %s  %s )" % tuple(h(c) for c in fn(tuple(f2(x) for x in v.groups())))

	def stream(m):
		return m.group(1) + VEC.sub(vec, m.group(2)) + m.group(3)
	text = POS_STREAM.sub(stream, text)
	return re.sub(r"(Locator\s*\{[^}]*?Position:\s*)(\([^)]*\))", lambda m: m.group(1) + VEC.sub(vec, m.group(2)), text)

TRI = re.compile(r"\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)")


def transform_components(text, fn):
    """Like transform, but fn(p, lo, hi) also gets the bounding box of the connected mesh component of the vertex
    (triangles of the piece, vertices with the same position welded)."""
    def piece(m):
        body = m.group(0)
        ps = POS_STREAM.search(body)
        if not ps:
            return body
        pts = [tuple(f2(x) for x in v.groups()) for v in VEC.finditer(ps.group(2))]
        parent = list(range(len(pts)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parent[a] = b
        seen = {}
        for i, q in enumerate(pts):
            k = tuple(round(c, 4) for c in q)
            if k in seen:
                union(i, seen[k])
            else:
                seen[k] = i
        tri = body[body.find("Triangles"):]
        for a, b, c in TRI.findall(tri):
            union(int(a), int(b)); union(int(b), int(c))
        box = {}
        for i, q in enumerate(pts):
            r = find(i)
            lo, hi = box.setdefault(r, ([9e9] * 3, [-9e9] * 3))
            for k in range(3):
                lo[k] = min(lo[k], q[k]); hi[k] = max(hi[k], q[k])
        it = iter(range(len(pts)))

        def vec(v):
            i = next(it)
            lo, hi = box[find(i)]
            return "( %s  %s  %s )" % tuple(h(c) for c in fn(pts[i], lo, hi))
        new = ps.group(1) + VEC.sub(vec, ps.group(2)) + ps.group(3)
        return body[:ps.start()] + new + body[ps.end():]
    return re.sub(r"Piece \{.*?\n\}", piece, text, flags=re.S)

def append_geometry(piece, verts, tris):
    """Append vertices (dicts with the stream tags as keys, e.g. _POSITION, _NORMAL, _UV0, _UV1, _RGBA -> tuple) and
    triangles (local index triples) to a .pim Piece block; updates its VertexCount/TriangleCount."""
    n0 = int(re.search(r"VertexCount: (\d+)", piece).group(1))
    t0 = int(re.search(r"TriangleCount: (\d+)", piece).group(1))

    def stream(m):
        tag = m.group(2)
        rows = "".join("\n          %d    ( %s )" % (n0 + i, "  ".join(h(c) for c in v[tag])) for i, v in enumerate(verts))
        return m.group(1) + rows + m.group(3)
    piece = re.sub(r'(Tag:\s*"(\w+)".*?)(\n     \})', stream, piece, flags=re.S)
    rows = "".join("\n          %d    ( %d     %d     %d     )" % (t0 + i, a + n0, b + n0, c + n0) for i, (a, b, c) in enumerate(tris))
    piece = re.sub(r"(Triangles \{.*?)(\n     \})", lambda m: m.group(1) + rows + m.group(2), piece, flags=re.S)
    piece = piece.replace("VertexCount: %d" % n0, "VertexCount: %d" % (n0 + len(verts)), 1)
    return piece.replace("TriangleCount: %d" % t0, "TriangleCount: %d" % (t0 + len(tris)), 1)


def cylinder(center, axis, radius, length, seg=20):
    """Closed cylinder along axis 0/1/2: (positions, normals, triangles), both faces of every triangle."""
    import math
    a, b = [k for k in range(3) if k != axis]
    verts, tris = [], []

    def v(pos, nrm):
        verts.append((tuple(pos), tuple(nrm)))
        return len(verts) - 1
    rings = []
    for s in (-0.5, 0.5):
        ring = []
        for i in range(seg):
            ang = 2 * math.pi * i / seg
            d = [0.0, 0.0, 0.0]; d[a] = math.cos(ang); d[b] = math.sin(ang)
            pos = [center[k] + d[k] * radius for k in range(3)]; pos[axis] += s * length
            ring.append(v(pos, d))
        rings.append(ring)
    for i in range(seg):
        j = (i + 1) % seg
        q = (rings[0][i], rings[0][j], rings[1][j], rings[1][i])
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    for s, side in ((-0.5, 0), (0.5, 1)):
        nrm = [0.0, 0.0, 0.0]; nrm[axis] = 1.0 if s > 0 else -1.0
        cpos = list(center); cpos[axis] += s * length
        c = v(cpos, nrm)
        cap = [v(verts[r][0], nrm) for r in rings[side]]
        for i in range(seg):
            tris.append((c, cap[i], cap[(i + 1) % seg]))
    tris += [(x, z, y) for x, y, z in tris]
    return verts, tris

def box(lo, hi):
    """Axis-aligned box: (positions+normals list, triangles), 4 vertices per face."""
    verts, tris = [], []
    for axis in range(3):
        a, b = [k for k in range(3) if k != axis]
        for side, val in ((-1, lo[axis]), (1, hi[axis])):
            n = [0.0, 0.0, 0.0]; n[axis] = float(side)
            base = len(verts)
            for ca, cb in ((0, 0), (1, 0), (1, 1), (0, 1)):
                q = [0.0, 0.0, 0.0]; q[axis] = val
                q[a] = (lo[a], hi[a])[ca]; q[b] = (lo[b], hi[b])[cb]
                verts.append((tuple(q), tuple(n)))
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    tris += [(x, z, y) for x, y, z in tris]
    return verts, tris


def tank(center, axis, radius, length, seg=32, dome=0.45, dome_rings=6):
    """Closed tank along axis 0/1/2 with elliptical (domed) ends of depth dome*radius, smooth normals, both faces of
    every triangle: (positions+normals list, triangles)."""
    import math
    a, b = [k for k in range(3) if k != axis]
    half, dd = length / 2, dome * radius
    prof = [(-half + dd - dd * math.cos(t), radius * math.sin(t), -math.cos(t) / dd, math.sin(t) / radius)
            for t in (math.pi / 2 * i / dome_rings for i in range(1, dome_rings + 1))]
    prof = [(-half, 0.0, -1.0, 0.0)] + prof + [(-p[0], p[1], -p[2], p[3]) for p in reversed(prof)] + [(half, 0.0, 1.0, 0.0)]
    verts, tris, rings = [], [], []
    for ax_, rr, na, nr in prof:
        ln = math.hypot(na, nr)
        ring = []
        for i in range(seg if rr > 0 else 1):
            ang = 2 * math.pi * i / seg
            q, n = list(center), [0.0, 0.0, 0.0]
            q[axis] += ax_; q[a] += math.cos(ang) * rr; q[b] += math.sin(ang) * rr
            n[axis] = na / ln; n[a] = math.cos(ang) * nr / ln; n[b] = math.sin(ang) * nr / ln
            ring.append(len(verts)); verts.append((tuple(q), tuple(n)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if len(r0) == 1:
                tris.append((r0[0], r1[j], r1[i]))
            elif len(r1) == 1:
                tris.append((r0[i], r0[j], r1[0]))
            else:
                tris += [(r0[i], r0[j], r1[j]), (r0[i], r1[j], r1[i])]
    tris += [(x, z, y) for x, y, z in tris]
    return verts, tris


if __name__ == "__main__":
	for f in sys.argv[1:]:
		lo, hi = bbox(open(f, encoding="utf-8").read())
		print("%-45s min %s max %s" % (f[-45:], " ".join("%7.3f" % v for v in lo), " ".join("%7.3f" % v for v in hi)))
