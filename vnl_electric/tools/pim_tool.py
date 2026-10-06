#!/usr/bin/env python3
"""pim_tool.py - text-level PIM (ConverterPIX / SCS mid-format) helpers.

  analyze <model.pim>                      list connected mesh islands with bounds
  locators <model.pim>                     list locators (name, position)
  extract <src.pim> <out.pim> --box xmin ymin zmin xmax ymax zmax --offset dx dy dz
                                           keep islands lying completely inside the box,
                                           translate them, write a new PIM (+ PIT copy)
SCS axes: x = right, y = up, z = backwards.
"""
import argparse, os, re, struct, sys
from collections import defaultdict

HEX = re.compile(r'&([0-9a-fA-F]{8})')


def hf(h):
    return struct.unpack('>f', bytes.fromhex(h))[0]


def fh(v):
    return '&' + struct.pack('>f', v).hex()


def blocks(lines):
    """split top-level blocks: returns list of (kind, [lines])"""
    out, cur, depth, kind = [], None, 0, None
    for ln in lines:
        s = ln.strip()
        if depth == 0 and s.endswith('{'):
            kind, cur = s[:-1].strip(), [ln]
            depth = 1
            continue
        if cur is not None:
            cur.append(ln)
            depth += s.count('{') - s.count('}')
            if depth == 0:
                out.append((kind, cur)); cur = None
    return out


class Piece:
    def __init__(self, lines):
        self.lines = lines
        self.material = int(re.search(r'Material:\s*(\d+)', '\n'.join(lines[:6])).group(1))
        self.streams = []          # (format, tag, [row tuples as raw tokens])
        self.tris = []
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s == 'Stream {':
                fmt = lines[i + 1].split(':')[1].strip()
                tag = lines[i + 2].split(':')[1].strip()
                rows, extra, i = [], [], i + 3
                while lines[i].strip() != '}':
                    m = re.search(r'\((.*)\)', lines[i])
                    if m:
                        rows.append(m.group(1).split())
                    else:
                        extra.append(lines[i])
                    i += 1
                self.streams.append((fmt, tag, rows, extra))
            elif s == 'Triangles {':
                i += 1
                while lines[i].strip() != '}':
                    self.tris.append([int(x) for x in re.search(r'\((.*)\)', lines[i]).group(1).split()])
                    i += 1
            i += 1
        self.pos = [[hf(t[1:]) for t in r] for (f, tg, rr, ex) in self.streams if tg == '"_POSITION"' for r in rr]

    def islands(self):
        parent = list(range(len(self.pos)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        # weld by position too (UV seams split vertices)
        key = {}
        for i, p in enumerate(self.pos):
            k = tuple(round(c, 4) for c in p)
            if k in key:
                parent[find(i)] = find(key[k])
            else:
                key[k] = i
        for a, b, c in self.tris:
            parent[find(b)] = find(a); parent[find(c)] = find(a)
        groups = defaultdict(list)
        for t, (a, _, _) in enumerate(self.tris):
            groups[find(a)].append(t)
        return list(groups.values())


def load(path):
    lines = open(path, encoding='utf-8').read().splitlines()
    return lines, blocks(lines)


def bounds(pts):
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def cmd_analyze(a):
    lines, bl = load(a.pim)
    mats = [re.search(r'Alias:\s*"([^"]+)"', '\n'.join(b)).group(1) for k, b in bl if k == 'Material']
    for k, b in bl:
        if k != 'Piece':
            continue
        p = Piece(b)
        for isl in p.islands():
            vs = {v for t in isl for v in p.tris[t]}
            lo, hi = bounds([p.pos[v] for v in vs])
            if len(isl) < a.min_tris:
                continue
            print('mat=%-38s tris=%6d  x[%6.2f %6.2f] y[%5.2f %5.2f] z[%6.2f %6.2f]' %
                  (mats[p.material], len(isl), lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))


def cmd_locators(a):
    lines, bl = load(a.pim)
    for k, b in bl:
        if k == 'Locator':
            t = '\n'.join(b)
            n = re.search(r'Name:\s*"([^"]+)"', t).group(1)
            pos = [hf(h) for h in HEX.findall(re.search(r'Position:.*', t).group(0))]
            print('%-16s %7.3f %7.3f %7.3f' % (n, *pos))


def cmd_extract(a):
    lines, bl = load(a.src)
    box_lo, box_hi = a.box[:3], a.box[3:]
    dx, dy, dz = a.offset
    header = [b for k, b in bl if k == 'Header'][0]
    mats = [b for k, b in bl if k == 'Material']
    pieces_out, used_mats = [], []
    tot_v = tot_t = 0
    for k, b in bl:
        if k != 'Piece':
            continue
        p = Piece(b)
        keep = []
        for isl in p.islands():
            vs = {v for t in isl for v in p.tris[t]}
            lo, hi = bounds([p.pos[v] for v in vs])
            if all(box_lo[i] <= lo[i] and hi[i] <= box_hi[i] for i in range(3)):
                keep += isl
        if not keep:
            continue
        verts = sorted({v for t in keep for v in p.tris[t]})
        remap = {v: i for i, v in enumerate(verts)}
        if p.material not in used_mats:
            used_mats.append(p.material)
        mi = used_mats.index(p.material)
        out = ['Piece {', '     Index: %d' % len(pieces_out), '     Material: %d' % mi,
               '     VertexCount: %d' % len(verts), '     TriangleCount: %d' % len(keep),
               '     StreamCount: %d' % len(p.streams)]
        for fmt, tag, rows, extra in p.streams:
            out += ['     Stream {', '          Format: %s' % fmt, '          Tag: %s' % tag] + extra
            for i, v in enumerate(verts):
                r = rows[v]
                if tag == '"_POSITION"':
                    xyz = [hf(t[1:]) for t in r]
                    zc = (box_lo[2] + box_hi[2]) / 2
                    r = [fh(xyz[0] + dx), fh(xyz[1] + dy), fh(zc + (xyz[2] - zc) * a.scale_z + dz)]
                out.append('          %-5d( %s )' % (i, '  '.join(r)))
            out.append('     }')
        out.append('     Triangles {')
        for i, t in enumerate(keep):
            out.append('          %-5d( %s )' % (i, '     '.join(str(remap[v]) for v in p.tris[t])))
        out += ['     }', '}']
        pieces_out.append(out)
        tot_v += len(verts); tot_t += len(keep)
    if not pieces_out:
        sys.exit('nothing inside the box')
    name = os.path.splitext(os.path.basename(a.out))[0]
    res = ['Header {', '     FormatVersion: 5', '     Source: "pim_tool"', '     Type: "Model"', '     Name: "%s"' % name, '}',
           'Global {', '     VertexCount: %d' % tot_v, '     TriangleCount: %d' % tot_t,
           '     MaterialCount: %d' % len(used_mats), '     PieceCount: %d' % len(pieces_out),
           '     PartCount: 1', '     BoneCount: 0', '     LocatorCount: 0', '     Skeleton: ""', '}']
    for m in used_mats:
        res += mats[m]
    for po in pieces_out:
        res += po
    res += ['Part {', '     Name: "defaultpart"', '     PieceCount: %d' % len(pieces_out), '     LocatorCount: 0',
            '     Pieces: %s ' % ' '.join(str(i) for i in range(len(pieces_out))), '     Locators: ', '}']
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8', newline='\n').write('\n'.join(res) + '\n')

    # PIT: keep only used materials, in new order
    pit = open(os.path.splitext(a.src)[0] + '.pit', encoding='utf-8').read().splitlines()
    pbl = blocks(pit)
    out = []
    for k, b in pbl:
        if k == 'Header':
            out += [re.sub(r'Name:\s*".*"', 'Name: "%s"' % name, l) for l in b]
        elif k == 'Global':
            out += [re.sub(r'MaterialCount:\s*\d+', 'MaterialCount: %d' % len(used_mats), l) for l in b]
        elif k in ('Look', 'Variant'):
            inner = blocks(b[1:-1])
            head = [l for l in b[1:-1] if l.strip().startswith('Name:') and not l.startswith('        ')][:1]
            sub = [x for x in inner if x[0] == ('Material' if k == 'Look' else 'Part')]
            if k == 'Look':
                body = []
                for m in used_mats:
                    body += sub[m][1]
            else:
                body = [l for x in sub for l in x[1]]
            out += [b[0]] + head + body + [b[-1]]
        else:
            out += b
    open(os.path.splitext(a.out)[0] + '.pit', 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    print('wrote %s: %d pieces, %d verts, %d tris, %d materials' % (a.out, len(pieces_out), tot_v, tot_t, len(used_mats)))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('analyze'); s.add_argument('pim'); s.add_argument('--min-tris', type=int, default=200)
    s = sp.add_parser('locators'); s.add_argument('pim')
    s = sp.add_parser('extract'); s.add_argument('src'); s.add_argument('out')
    s.add_argument('--box', type=float, nargs=6, required=True); s.add_argument('--offset', type=float, nargs=3, default=[0, 0, 0]); s.add_argument('--scale-z', type=float, default=1.0)
    a = ap.parse_args()
    {'analyze': cmd_analyze, 'locators': cmd_locators, 'extract': cmd_extract}[a.cmd](a)


if __name__ == '__main__':
    main()

