"""make_rubber_duck_r.py [--workshop <ATS workshop dir>] [--addon <Mack_R_addon_v1.1.scs>] [--conv C:\\ATSExtract\\conversion_tools]

Personal-use patch mod for the Mack R Series (mack.rhpl), Rubber Duck style:
- bull bar of the "Mack Pinnacle Rubber Duck" mod, scaled/moved onto the bounding box of the R bull bar;
- white grill and headlamps: the chrome R parts (WHITE) with their chrome materials turned into white gloss.
Models are converted with ConverterPIX and recompiled with the SCS conversion tools.
Load order (top = highest): rubber_duck_r.scs > Mack R add-on > Mack R Series > Pinnacle Rubber Duck.
The output contains assets of other authors - never publish it.
"""
import argparse, math, os, re, shutil, struct, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pim_tools
sys.path.insert(0, os.path.join(ROOT, "vnl_electric", "tools"))
import make_paintjob as mpj
from PIL import Image, ImageOps

TRUCK = "mack.rhpl"
OUT = "vehicle/truck/mack_rhpl_duck"
DUCK = "/vehicle/truck/mack_pinnacle/accessory"
# slot: (duck model, R model whose bounding box it is fitted to, source of the R model, name, icon)
PARTS = {
    "bumper": (DUCK + "/bumper/stockbduck", "/vehicle/truck/upgrade/bumper/mack.rhpl/bumper_bullbar", "r",
               "Rubber Duck Bullbar", "mack.rhpl/bump_bull"),
}
# slot: (source mod, chrome R model, chrome accessory defs (file name without .sii) copied as white versions)
WHITE = {
    "grill": ("a", "/sleeper/grill_700", ["grill700in"]),               # add-on "R700 Grill Chrome 1"
    "lamps": ("r", "/vehicle/truck/upgrade/headlights/mack.rhpl/headlights", ["single_chr", "double_chr"]),
    "mudflaps": ("r", "/vehicle/truck/upgrade/mudflaps/mack.rhpl/mudflaps", ["mackbw", "mackbwf"]),
    "rfilter": ("a", "/sleeper/filter_rd", ["rd600", "rd700"]),           # add-on "Double Pipe Filter"
    "tanks": ("a", "/sleeper/tanks_round_235", ["bigal235"]),             # add-on "Round" 260 gal tanks
}
# parts that keep their chrome (no whitening), shop names other than "Rubber Duck White"
NO_WHITEN = {"rfilter", "tanks"}
NAMES = {"rfilter": "Double Pipe Filter Black", "tanks": "Round Matte Black"}
# materials turned into matte black (chassis look): aluminium fuel tank
MATTE = {"tanks": [6]}
# material copies in the look (target index: source index): headlamp surround (ribbed chrome overlay + normal map)
# -> the plain white material
COPY = {"lamps": {2: 0}}
# base textures replaced by plain white (besides the chrome materials): black rubber of the mudflaps
WHITE_BASE = []
# textures replaced by an inverted (RGB) copy: black mudflap with white Mack logo -> white with black logo
INVERT = {"mudflaps": ["/vehicle/truck/mack.rhpl/textures/mudflap"]}
# materials (index in the look) turned into fixed gloss black: R700 grill surround (part pout, truck paint)
BLACK = {"grill": [1], "rfilter": [0, 4, 5, 6], "lamps": [3]}         # lamps 3: outer frame (truck paint -> paint job patches)                       # + filter canister / pipes
# black steel rims: copies of the SCS steel wheels with the rim material replaced (same path length in the .pmd)
# fifth wheel: hook_t z (m, + = rear) in /sleeper/truck_sleeper_700 and how far to move it (frame end leaves ~0.65 m)
HOOK_Z = struct.unpack(">f", bytes.fromhex("40495ada"))[0]
FIFTH_BACK = 0.6
# chrome bulldog on the cab sides (components of the chrome pieces, both sides): |x|, y, z ranges in the cab model
BULLDOG = ((0.89, 0.95), (1.02, 1.20), (-1.47, -1.30))
# baked cab AO: black silhouette of the bulldog is filled with the surrounding AO
CAB_AO = "/vehicle/truck/mack.rhpl/newtextures/700cab_ao"
# cab model: sleeper door frames (material 27, chrome) -> gloss black like the cab; chrome strip along the bottom of the
# sleeper sides, added to the chrome piece of the R700 cab: |x| from..to, y from..to, z from..to
DOOR_FRAME_MAT = 27
PAINTJOB = "/vehicle/truck/upgrade/paintjob/R.D TRUCKING INC/Mack R Series [Harven]/Cabin"
SLEEPER_STRIP = ((1.186, 1.200), (1.035, 1.075), (-0.303, 0.824))
CHROME_PIECE = 29
# battery boxes (both sides, chass model piece 2 = 6x4_235): bigger, higher, back to the fuel tank (front edge at chass
# x 2.31; chass x points forward, truck z = 1.172 - x), with two air tanks under each box
BAT_PIECE = 2
BAT_SEL = (2.9, 3.4)                       # chass x range of the box (+ hanger) components
BAT_SCALE = 1.35
BAT_UP = 0.204                             # box + air tanks span the fuel tank height (chass y -0.06..-0.72)
BAT_REAR_X = 2.675                         # new rear edge (1 ft before the tank)
BAT_IN = -0.06                             # moved towards the frame (width not scaled)
AIR_R = 0.11
AIR_PIECE = 1                              # chass piece (and material) of the frame rails: UVs + material template
AIR_PART = "6x4_235"
AIR_EFFECT = "eut2.dif.spec.add.env.nofresnel"
AIR_MAT = [None]                           # index of the added gloss black material
NIPPLE_R, NIPPLE_L = 0.025, 0.025
WHEEL_SRC = "/vehicle/truck/upgrade/wheel/disc"
# wheel discs (hub system, def/vehicle/f_disc + r_disc): slot: (unit suffix, model, its material, black material
# (same path length), extra lines)
WHEELS = {
    "f_disc": ("standard.fdisc", "front_disc_steel", "/automat/c7/c7933d3ee8957ac8.mat", "/automat/rd/rdblackdiscfrnt0.mat",
               "\ttire_shift: -0.0372446\n\tdefaults[]: \"/def/vehicle/f_tire/1.sii\"\n"),
    "r_disc": ("double.rdisc", "rear_disc_steel", "/automat/3a/3a4981523a3b5d8e.mat", "/automat/rd/rdblackdiscrear0.mat",
               "\tdefaults[]: \"/def/vehicle/r_tire/1.sii\"\n"),
}
WHITE_TEX = "/vehicle/share/textures/generic/white_0"
# SCS fuel tank trailer (owned): front mudflaps (incl. their hanger) removed, the front ladder (f_body) moved to the
# middle of the tank on the right side (rotated 90 deg), its top landing stretched onto the catwalk. One ladder model per
# chassis model (tank length differs); chassis model -> chassis units using it
FT = "/vehicle/trailer_owned/scs_fueltank"
FT_DEF = "def/vehicle/trailer_owned/scs.fueltank"
FT_CHASSIS = {"ch_53_4a": ["ch_53_4a", "ch_53_4s"], "ch_48_3a": ["ch_48_3a"], "ch_43_r": ["ch_43_r", "ch_43_hook"],
              "ch_32": ["ch_32"], "ch_32_bd": ["ch_32_bd"], "ch_28": ["ch_28", "ch_28_hook"], "ch_28_double": ["ch_28_d"]}
FT_MAIN = "ch_53_4a"                       # keeps the original ladder unit (owned trailers keep their ladder)
FT_LADDER_OUT = 0.13                       # ladder rails outside the widest point of the tank
FT_CATWALK = 0.45                          # |x| of the catwalk edge on top of the tank
FT_TOP_Y = 0.7                             # ladder model: above this the landing reaches over onto the tank
FT_DECK = (0.58, 1.32, 0.78, 1.35)         # fender deck: |x| from..to, y from..to (long components, > 1.5 m)
# bull bar: the centre section (rails 0.18 / 0.40 / 0.64 / 0.90, top loop) keeps the original duck shape like the
# real truck; only the side loops (y 0.42-0.58 in front of the R headlamps) are lifted unscaled by BULL_LIFT.
BULL_LIFT = 0.26
BULL_Y = [(0.22, 0.22), (0.40, 0.40 + BULL_LIFT), (0.62, 0.62 + BULL_LIFT), (1.2, 1.2)]
BULL_BASE = 0.3                            # bull bar: above this the loops are stretched to follow the hood outline
BULL_GAP = 0.03                            # centre loop top this far above the hood crown
BULL_TUBE = 0.04                           # tube diameter of the loops
BULL_SILVER = "0.620000  0.630000  0.650000"  # bull bar diffuse (silver, with reflections)
BULL_SLOPE_IN = 0.04                       # centre loop: the slopes start this far before the original corner bend
BULL_ROUND = 0.08                          # radius of the rounded corners at both ends of the slopes
BULL_SIDE_IN = 0.015                       # side loop tops reach this far into the centre posts
BULL_SIDE_RAIL = 0.68                      # side loop tops meet this centre rail (original height, rails 0.44/0.68/0.93)
BULL_SIDE_UP = 0.11                        # ... raised by this much (the rail moves with them)
BULL_CENTRE_W = 0.67                       # centre posts at |x| (original 0.59), side loops stretched to match
BULL_DEPTH = 0.5                           # cab points up to this far behind the bumper locator form the outline


def remap_y(y, pts=BULL_Y):
    if y <= pts[0][0] or y >= pts[-1][0]:
        return y
    for (a, b), (c, d) in zip(pts, pts[1:]):
        if y <= c:
            return b + (y - a) * (d - b) / (c - a)


def whiten(pit):
    """Chrome materials (no paint/lamp/glass effect, env_factor >= 0.35) -> white gloss like the painted parts."""
    def mat(m):
        b = m.group(0)
        eff = re.search(r'Effect:\s*"([^"]+)"', b).group(1)
        env = re.search(r'Tag:\s*"env_factor"\s*Value:\s*\(\s*([-\d.]+)', b)
        if any(k in eff for k in ("paint", "lamp", "glass")) or not env or float(env.group(1)) < 0.35:
            return b
        for tag, val in (("diffuse", "1.000000  1.000000  1.000000"), ("env_factor", "0.200000  0.200000  0.200000"),
                         ("shininess", "250.000000")):
            b = re.sub(r'(Tag:\s*"%s"\s*Value:\s*\()[^)]*' % tag, lambda x: x.group(1) + " %s " % val, b)
        return re.sub(r'(Value:\s*)"[^"]*chrome(?!_nm)[^"]*"', r'\1"%s"' % WHITE_TEX, b)
    return re.sub(r"Material \{.*?\n    \}", mat, pit, flags=re.S)


def battery_boxes(ctext):
    m = re.search(r"Piece \{\s*Index: %d\s.*?\n\}" % BAT_PIECE, ctext, re.S)
    piece = m.group(0)
    is_box = lambda lo, hi: BAT_SEL[0] <= lo[0] and hi[0] <= BAT_SEL[1] and min(abs(lo[2]), abs(hi[2])) >= 0.4 and hi[1] <= 0.0
    boxes = {}                                                  # side -> [lo, hi] of the box body (below the hanger)
    uv = {}

    def scan(q, lo, hi):
        if is_box(lo, hi) and lo[1] < -0.2:
            s = 1 if q[2] > 0 else -1
            b = boxes.setdefault(s, [list(lo), list(hi)])
            for k in range(3):
                b[0][k] = min(b[0][k], lo[k]); b[1][k] = max(b[1][k], hi[k])
        return q
    pim_tools.transform_components(piece, scan)
    dx = BAT_REAR_X - min(b[0][0] for b in boxes.values())  # box rear edge -> BAT_REAR_X before scaling
    def move(q, lo, hi):
        if not is_box(lo, hi):
            return q
        s = 1 if q[2] > 0 else -1
        blo, bhi = boxes[s]
        top = bhi[1]
        zin = blo[2] if s > 0 else bhi[2]
        if lo[1] < -0.2:                                        # box body: scale around rear-top-inner corner
            ax, ay, az = blo[0], top, zin
            return (ax + dx + (q[0] - ax) * BAT_SCALE, ay + BAT_UP + (q[1] - ay) * BAT_SCALE, q[2] - s * BAT_IN)
        return tuple(lo)              # hanger (round plug + bracket): would sit on the cab side above the raised box
    piece = pim_tools.transform_components(piece, move)
    # air tanks: two cylinders across (chass z) under each box, UVs/colour from a box vertex
    def rows(tag):
        body = re.search(r'Tag:\s*"%s".*?\n     \}' % tag, m.group(0), re.S).group(0)
        return [tuple(pim_tools.f2(x) for x in r.split()) for r in re.findall(r"\n\s*\d+\s*\(([^)]*)\)", body)]
    ctext = ctext[:m.start()] + piece + ctext[m.end():]
    m = re.search(r"Piece \{\s*Index: %d\s.*?\n\}" % AIR_PIECE, ctext, re.S)
    piece = m.group(0)
    nrm = rows("_NORMAL")
    pos = rows("_POSITION")
    face = next(i for i, (q, n) in enumerate(zip(pos, nrm))             # outer web of a frame rail
                if abs(n[2]) > 0.9 and 0.38 < abs(q[2]) < 0.5 and -0.3 < q[1] < 0.0 and 0.0 < q[0] < 1.0)
    uv0, uv1 = rows("_UV0")[face], rows("_UV1")[face]
    verts, tris = [], []
    for s, (blo, bhi) in boxes.items():
        x0 = blo[0] + dx
        length = (bhi[0] - blo[0]) * BAT_SCALE
        width = bhi[2] - blo[2]
        bottom = bhi[1] + BAT_UP - (bhi[1] - blo[1]) * BAT_SCALE
        zc = (blo[2] + bhi[2]) / 2 - s * BAT_IN
        for xc in (x0 + length * 0.27, x0 + length * 0.73):
            yc = bottom - AIR_R - 0.01
            for (cc, rad), (vv, tt) in (((xc, yc, zc), AIR_R), pim_tools.tank((xc, yc, zc), 2, AIR_R, width * 0.95)), \
                                     (((xc, yc, zc), NIPPLE_R), pim_tools.cylinder((xc, yc, zc + s * (width * 0.95 + NIPPLE_L) / 2), 2, NIPPLE_R, NIPPLE_L, 16)):
                base = len(verts)
                # one frame texel for all vertices: the frame texture is an atlas, wrapping it around the tanks runs
                # into other (darker) parts of it; the frame's UV1 (AO)
                verts += [{"_POSITION": q, "_NORMAL": n, "_UV0": uv0[:2], "_UV1": uv1[:2],
                           "_RGBA": (1.0, 1.0, 1.0, 1.0)} for q, n in vv]
                tris += [(a + base, b + base, c + base) for a, b, c in tt]
    # own piece in the frame material (chassis texture), part of the 235 chassis variant
    npiece = int(re.search(r"PieceCount: (\d+)", ctext).group(1))
    nmat = int(re.search(r"MaterialCount: (\d+)", ctext).group(1))
    skel = re.sub(r"\n\s*\d+\s*\([^)]*\)", "", piece)
    skel = re.sub(r"Index: \d+", "Index: %d" % npiece, skel, count=1)
    skel = re.sub(r"VertexCount: \d+", "VertexCount: 0", skel, count=1)
    skel = re.sub(r"TriangleCount: \d+", "TriangleCount: 0", skel, count=1)
    piece = pim_tools.append_geometry(skel, verts, tris)
    first_part = ctext.index("\nPart {")
    ctext = ctext[:first_part] + "\n" + piece + ctext[first_part:]
    last_mat = [mm.end() for mm in re.finditer(r"\nMaterial \{.*?\n\}", ctext, re.S)][-1]
    ctext = ctext[:last_mat] + '\nMaterial {\n     Alias: "mat_rd_gloss_black"\n     Effect: "%s"\n}' % AIR_EFFECT + ctext[last_mat:]
    ctext = re.sub(r"PieceCount: %d" % npiece, "PieceCount: %d" % (npiece + 1), ctext, count=1)
    ctext = re.sub(r"MaterialCount: %d" % nmat, "MaterialCount: %d" % (nmat + 1), ctext, count=1)
    pm = re.search(r'(Part \{\s*Name: "%s"\s*PieceCount: )(\d+)(\s*LocatorCount: \d+\s*Pieces: )([\d ]*)' % AIR_PART, ctext)
    ctext = ctext[:pm.start()] + pm.group(1) + str(int(pm.group(2)) + 1) + pm.group(3) + pm.group(4).rstrip() + " %d " % npiece + ctext[pm.end():]
    AIR_MAT[0] = nmat
    g = re.search(r"Global \{\s*VertexCount: (\d+)\s*TriangleCount: (\d+)", ctext)
    ctext = ctext.replace(g.group(0), g.group(0).replace("VertexCount: " + g.group(1), "VertexCount: %d" % (int(g.group(1)) + len(verts)))
                          .replace("TriangleCount: " + g.group(2), "TriangleCount: %d" % (int(g.group(2)) + len(tris))), 1)
    print("battery boxes", {s: [[round(c, 2) for c in b[0]], [round(c, 2) for c in b[1]]] for s, b in boxes.items()},
          "moved %.2f m back, %d air tank vertices" % (-dx, len(verts)))
    return ctext


def run(*a):
    r = subprocess.run([str(x) for x in a], capture_output=True, text=True)
    if r.returncode:
        sys.exit("failed: %s\n%s%s" % (" ".join(map(str, a)), r.stdout, r.stderr))


def wr(rel, text):
    p = os.path.join(MOD, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)


def fit(src_box, dst_box):
    (slo, shi), (dlo, dhi) = src_box, dst_box
    s = (dhi[0] - dlo[0]) / (shi[0] - slo[0])                    # uniform scale to the R part's width
    c = [(slo[k] + shi[k]) / 2 for k in range(3)]
    d = [(dlo[k] + dhi[k]) / 2 for k in range(3)]
    return lambda p: tuple(d[k] + (p[k] - c[k]) * s for k in range(3))


def bull(f):
    """fn(p, lo, hi) for pim_tools.transform_components: the flat centre rails (separate components, |x| <= 0.6,
    thinner than 0.1 m, above the full-width bar) keep their height, everything else is remapped."""
    def g(p, lo, hi):
        x, y, z = f(p)
        lo, hi = f(lo), f(hi)
        if max(abs(lo[0]), abs(hi[0])) <= 0.6 and hi[1] - lo[1] < 0.1 and lo[1] > 0.3:
            return x, y, z
        if abs(x) < 0.6 and y > 0.66:                           # centre posts / top loop above the side loop joint
            return x, y, z
        return x, remap_y(y), z
    return g


ap = argparse.ArgumentParser()
ap.add_argument("--workshop", default=r"D:\SteamLibrary\steamapps\workshop\content\270880")
ap.add_argument("--addon", default=None, help="Mack_R_addon_v1.1.scs (default: from the ATS mod folder)")
ap.add_argument("--conv", default=r"C:\ATSExtract\conversion_tools")
ap.add_argument("--game", default=r"C:\ATSExtract", help="extracted game data (steel wheels)")
ap.add_argument("--scs-dir", default=r"D:\SteamLibrary\steamapps\common\American Truck Simulator")
ap.add_argument("--extractor", default=os.path.join(ROOT, "vnl_electric", "tools", "bin", "extractor", "extractor.exe"))
o = ap.parse_args()

home = os.path.expanduser("~")
MODDIRS = [os.path.join(home, "OneDrive - Microsoft", "Documents", "American Truck Simulator", "mod"),
           os.path.join(home, "Documents", "American Truck Simulator", "mod")]
moddir = next((d for d in MODDIRS if os.path.isdir(d)), None)
sources = {"r": os.path.join(o.workshop, "1463066263", "159.zip"),                       # Mack R Series 1.8
           "d": os.path.join(o.workshop, "3593043044", "universal.zip"),                 # Pinnacle Rubber Duck
           "a": o.addon or os.path.join(moddir or "", "Mack_R_addon_v1.1.scs"),         # Mack R add-on
           "k": os.path.join(o.workshop, "2709808527", "universal.zip")}                # R.D. Trucking paint job
for k, p in sources.items():
    if not os.path.isfile(p):
        sys.exit("source mod not found: %s" % p)

MOD = os.path.join(HERE, "mod")
SRC = os.path.join(HERE, "src")
PROJ = os.path.join(HERE, "project")
for d in (MOD, SRC, PROJ):
    shutil.rmtree(d, ignore_errors=True)

# 1. extract the source mods, convert the models to text
for k, p in sources.items():
    zipfile.ZipFile(p).extractall(os.path.join(SRC, k))
cpx = os.path.join(ROOT, "vnl_electric", "tools", "bin", "converter_pix.exe")
pix = os.path.join(SRC, "pix")
for slot, (duck, rmodel, rsrc, _, _) in PARTS.items():
    run(cpx, "-b", os.path.join(SRC, "d"), "-m", duck, "-e", pix)
    run(cpx, "-b", os.path.join(SRC, rsrc), "-m", rmodel, "-e", pix)
for slot, (src, model, _) in WHITE.items():
    run(cpx, "-b", os.path.join(SRC, src), "-m", model, "-e", pix)

# 2. fit every duck mesh onto the R part, write it to the project
for slot, (duck, rmodel, _, _, _) in PARTS.items():
    dpath = os.path.join(pix, *duck.strip("/").split("/"))
    rbox = pim_tools.bbox(open(os.path.join(pix, *rmodel.strip("/").split("/")) + ".pim", encoding="utf-8").read())
    text = open(dpath + ".pim", encoding="utf-8").read()
    dbox = pim_tools.bbox(text)
    out = os.path.join(PROJ, *OUT.split("/"), slot)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out + ".pim", "w", encoding="utf-8").write((pim_tools.transform_components(text, bull(fit(dbox, rbox))) if slot == "bumper"
                                                    else pim_tools.transform(text, fit(dbox, rbox))))
    pit = open(dpath + ".pit", encoding="utf-8").read()
    pit = pit.replace('"/vehicle/truck/mack_pinnacle/paint"', '"%s"' % WHITE_TEX)      # grey paint base -> white
    pit = pit.replace('"/vehicle/truck/mack_pinnacle/accessory/bumper/duckbumao"', '"%s"' % WHITE_TEX)  # AO: old joints
    if slot == "bumper":                                      # silver bull bar: polished aluminium look
        def silver(mm):
            a = lambda fmt, tag, val: ("\n        Attribute {\n            Format: %s\n            Tag: \"%s\"\n"
                                       "            Value: ( %s )\n        }" % (fmt, tag, val))
            t = lambda i, tag, val: "\n        Texture {\n            Tag: \"texture[%d]:%s\"\n            Value: \"%s\"\n        }" % (i, tag, val)
            return ('    Material {\n        Alias: "mat_0000_paint"\n        Effect: "%s"\n        Flags: 0\n'
                    '        AttributeCount: 6\n        TextureCount: 2' % AIR_EFFECT
                    + a("FLOAT", "add_ambient", "0.000000") + a("FLOAT3", "diffuse", BULL_SILVER)
                    + a("FLOAT3", "env_factor", "0.550000  0.550000  0.550000") + a("FLOAT", "reflection", "0.000000")
                    + a("FLOAT", "shininess", "120.000000") + a("FLOAT3", "specular", "1.000000  1.000000  1.000000")
                    + t(0, "texture_base", WHITE_TEX) + t(1, "texture_reflection", "/material/environment/vehicle_reflection")
                    + "\n    }")
        pit = re.sub(r'    Material \{\s*Alias: "mat_0000_paint".*?\n    \}', silver, pit, count=1, flags=re.S)
    open(out + ".pit", "w", encoding="utf-8").write(pit.replace(os.path.basename(dpath) + ".pim", slot + ".pim"))
    print("%-7s duck %s -> R %s" % (slot, ["%.2f" % v for v in dbox[0] + dbox[1]], ["%.2f" % v for v in rbox[0] + rbox[1]]))
# white grill / headlamps: same mesh, chrome materials whitened
for slot, (_, model, _) in WHITE.items():
    spath = os.path.join(pix, *model.strip("/").split("/"))
    out = os.path.join(PROJ, *OUT.split("/"), slot)
    shutil.copy2(spath + ".pim", out + ".pim")
    pit = open(spath + ".pit", encoding="utf-8").read()
    wpit = pit.replace(os.path.basename(spath) + ".pim", slot + ".pim")
    if slot not in NO_WHITEN:
        wpit = whiten(wpit)
    for dst, src in COPY.get(slot, {}).items():
        blocks = list(re.finditer(r"Material \{.*?\n    \}", wpit, re.S))
        blk = re.sub(r'Alias: "[^"]*"', 'Alias: "mat_copy_%d"' % dst, blocks[src].group(0))
        wpit = wpit[:blocks[dst].start()] + blk + wpit[blocks[dst].end():]
    for tex in WHITE_BASE:
        wpit = wpit.replace('"%s"' % tex, '"%s"' % WHITE_TEX)
    for tex in INVERT.get(slot, []):
        name = os.path.basename(tex) + "_inv"
        img = Image.open(os.path.join(pix, *tex.strip("/").split("/")) + ".dds").convert("RGBA")
        r, g, b_, a = img.split()
        img = Image.merge("RGBA", [ImageOps.invert(c) for c in (r, g, b_)] + [a])
        dst = os.path.join(PROJ, *OUT.split("/"), name)
        mpj.save_dds(img, dst + ".dds")
        open(dst + ".tobj", "w").write("map 2d %s.dds\naddr clamp_to_edge clamp_to_edge\n" % name)
        wpit = wpit.replace('"%s"' % tex, '"/%s/%s"' % (OUT, name))
    if slot in MATTE:
        blocks = list(re.finditer(r"Material \{.*?\n    \}", wpit, re.S))
        for i in sorted(MATTE[slot], reverse=True):
            blk = blocks[i].group(0)
            for tag, val in (("diffuse", "0.030000  0.030000  0.030000"), ("specular", "0.050000  0.050000  0.050000"),
                             ("env_factor", "0.020000  0.020000  0.020000"), ("shininess", "8.000000")):
                blk = re.sub(r'(Tag:\s*"%s"\s*Value:\s*\()[^)]*' % tag, lambda m, v=val: m.group(1) + " %s " % v, blk)
            wpit = wpit[:blocks[i].start()] + blk + wpit[blocks[i].end():]
    if slot in BLACK:
        blocks = list(re.finditer(r"Material \{.*?\n    \}", wpit, re.S))
        tmpl = next(b.group(0) for b in blocks if "nofresnel" in b.group(0))
        for i in sorted(BLACK[slot], reverse=True):
            blk = re.sub(r'Alias: "[^"]*"', 'Alias: "mat_black_%d"' % i, tmpl)
            blk = re.sub(r'(Tag:\s*"diffuse"\s*Value:\s*\()[^)]*', r'\1 0.020000  0.020000  0.020000 ', blk)
            blk = re.sub(r'(Tag:\s*"env_factor"\s*Value:\s*\()[^)]*', r'\1 0.200000  0.200000  0.200000 ', blk)
            base = re.search(r'texture_base"\s*Value:\s*("[^"]*")', blocks[i].group(0))   # keep the part's own AO
            if base:
                blk = re.sub(r'(texture_base"\s*Value:\s*)"[^"]*"', lambda m: m.group(1) + base.group(1), blk)
            wpit = wpit[:blocks[i].start()] + blk + wpit[blocks[i].end():]
    open(out + ".pit", "w", encoding="utf-8").write(wpit)
    print("%-7s white from %s (%d chrome materials)" % (slot, model, wpit.count(WHITE_TEX) - pit.count(WHITE_TEX)))
# materials/textures of the duck models
# models; copy them so the conversion tools can resolve them
for dp, _, fns in os.walk(pix):
    for fn in fns:
        if fn.endswith((".mat", ".tobj", ".dds")):
            rel = os.path.relpath(os.path.join(dp, fn), pix)
            os.makedirs(os.path.join(PROJ, os.path.dirname(rel)), exist_ok=True)
            shutil.copy2(os.path.join(dp, fn), os.path.join(PROJ, rel))

# chass model with the fifth wheel (piece 0, chs_base) moved back; accessory x points forward
run(cpx, "-b", os.path.join(SRC, "a"), "-m", "/sleeper/chassislong", "-e", pix)
ctext = open(os.path.join(pix, "sleeper", "chassislong.pim"), encoding="utf-8").read()
m = re.search(r"Piece \{\s*Index: 0\s.*?\n\}", ctext, re.S)
ctext = ctext[:m.start()] + pim_tools.transform(m.group(0), lambda q: (q[0] - FIFTH_BACK, q[1], q[2])) + ctext[m.end():]
ctext = battery_boxes(ctext)
out = os.path.join(PROJ, *OUT.split("/"), "chassislong")
open(out + ".pim", "w", encoding="utf-8").write(ctext)
cpit = open(os.path.join(pix, "sleeper", "chassislong.pit"), encoding="utf-8").read()
blocks = list(re.finditer(r"\n    Material \{.*?\n    \}", cpit, re.S))
def attr(fmt, tag, val):
    return "\n        Attribute {\n            Format: %s\n            Tag: \"%s\"\n            Value: ( %s )\n        }" % (fmt, tag, val)
def tex(i, tag, val):
    return "\n        Texture {\n            Tag: \"texture[%d]:%s\"\n            Value: \"%s\"\n        }" % (i, tag, val)
src = ('\n    Material {\n        Alias: "mat_rd_gloss_black"\n        Effect: "%s"\n        Flags: 0\n        AttributeCount: 6\n'
       '        TextureCount: 2' % AIR_EFFECT
       + attr("FLOAT", "add_ambient", "0.000000") + attr("FLOAT3", "diffuse", "0.015000  0.015000  0.015000")
       + attr("FLOAT3", "env_factor", "0.350000  0.350000  0.350000") + attr("FLOAT", "reflection", "0.000000")
       + attr("FLOAT", "shininess", "120.000000") + attr("FLOAT3", "specular", "1.000000  1.000000  1.000000")
       + tex(0, "texture_base", WHITE_TEX) + tex(1, "texture_reflection", "/material/environment/vehicle_reflection")
       + "\n    }")
cpit = cpit[:blocks[-1].end()] + src + cpit[blocks[-1].end():]
cpit = re.sub(r"MaterialCount: (\d+)", lambda mm: "MaterialCount: %d" % (int(mm.group(1)) + 1), cpit, count=1)
assert AIR_MAT[0] == int(re.search(r"MaterialCount: (\d+)", cpit).group(1)) - 1
open(out + ".pit", "w", encoding="utf-8").write(cpit)

# truck/cab model copy: hook_t (fifth wheel coupling) moved back, chrome bulldog on the cab sides removed (collapsed)
run(cpx, "-b", os.path.join(SRC, "a"), "-m", "/sleeper/truck_sleeper_700", "-e", pix)
tsrc = os.path.join(pix, "sleeper", "truck_sleeper_700")
ttext = open(tsrc + ".pim", encoding="utf-8").read()
lm = re.search(r'(Locator \{\s*Name: "hook_t".*?Position:\s*)(\([^)]*\))', ttext, re.S)
ttext = ttext[:lm.start(2)] + pim_tools.VEC.sub(lambda v: "( %s  %s  %s )" % (
    v.group(1), v.group(2), pim_tools.h(pim_tools.f2(v.group(3)) + FIFTH_BACK)), lm.group(2)) + ttext[lm.end(2):]
in_box = lambda B, lo, hi: (B[0][0] <= min(abs(lo[0]), abs(hi[0])) and max(abs(lo[0]), abs(hi[0])) <= B[0][1]
                            and B[1][0] <= lo[1] and hi[1] <= B[1][1] and B[2][0] <= lo[2] and hi[2] <= B[2][1])
in_dog = lambda lo, hi: in_box(BULLDOG, lo, hi)
dogs = [0]
def collapse(q, lo, hi):
    if in_dog(lo, hi):
        dogs[0] += 1
        return tuple(lo)
    return q
ttext = pim_tools.transform_components(ttext, collapse)
print("bulldog: %d vertices removed" % dogs[0])
# its shadow caster (shadow-only pieces): vertices in the area pushed into the cab body
tpit = open(tsrc + ".pit", encoding="utf-8").read()
tmats = re.findall(r"Material \{(.*?)\n    \}", tpit, re.S)
near = lambda q, pad: (BULLDOG[0][0] - pad <= abs(q[0]) <= BULLDOG[0][1] + pad and BULLDOG[1][0] - pad <= q[1] <= BULLDOG[1][1] + pad
                       and BULLDOG[2][0] - pad <= q[2] <= BULLDOG[2][1] + pad)
uvs = []
def piece_fix(pm):
    body = pm.group(0)
    eff = re.search(r'Effect: "([^"]*)"', tmats[int(pm.group(2))]).group(1)
    if "shadowonly" in eff:
        return pim_tools.transform(body, lambda q: ((BULLDOG[0][0] - 0.05) * (1 if q[0] > 0 else -1), q[1], q[2]) if near(q, 0.0) else q)
    if "700cab_ao" in tmats[int(pm.group(2))]:                     # baked AO under the emblem: UV rect per side
        ps = list(pim_tools.positions(body))
        uv = re.search(r'Tag:\s*"_UV0".*?\n     \}', body, re.S).group(0)
        uvl = [tuple(pim_tools.f2(x) for x in r.split()) for r in re.findall(r"\n\s*\d+\s*\(([^)]*)\)", uv)]
        tri = [tuple(map(int, x)) for x in pim_tools.TRI.findall(body[body.find("Triangles"):])]
        for side in (1, -1):
            corners = []
            for y in BULLDOG[1]:
                for z in BULLDOG[2]:
                    for i0, i1, i2 in tri:                          # triangle on this side containing (y, z)
                        P = [ps[i0], ps[i1], ps[i2]]
                        if any(q[0] * side < BULLDOG[0][0] - 0.1 for q in P):
                            continue
                        (y0, z0), (y1, z1), (y2, z2) = [(q[1], q[2]) for q in P]
                        d = (y1 - y0) * (z2 - z0) - (y2 - y0) * (z1 - z0)
                        if abs(d) < 1e-9:
                            continue
                        l1 = ((y - y0) * (z2 - z0) - (y2 - y0) * (z - z0)) / d
                        l2 = ((y1 - y0) * (z - z0) - (y - y0) * (z1 - z0)) / d
                        if l1 >= -1e-4 and l2 >= -1e-4 and l1 + l2 <= 1 + 1e-4:
                            U = [uvl[i0], uvl[i1], uvl[i2]]
                            corners.append(tuple(U[0][k] + l1 * (U[1][k] - U[0][k]) + l2 * (U[2][k] - U[0][k]) for k in range(2)))
                            break
            if len(corners) == 4:
                uvs.append(corners)
    return body
ttext = re.sub(r"Piece \{\s*Index: (\d+)\s*Material: (\d+).*?\n\}", piece_fix, ttext, flags=re.S)


def ao_rects():
    """Pixel rects (fractions) of BULLDOG / ROUND on the outer cab skin in the UV0 of the cab AO pieces."""
    rects = []
    for pm in re.finditer(r"Piece \{\s*Index: (\d+)\s*Material: (\d+).*?\n\}", ttext, re.S):
        if "700cab_ao" not in tmats[int(pm.group(2))]:
            continue
        body = pm.group(0)
        ps = list(pim_tools.positions(body))
        uv = re.search(r'Tag:\s*"_UV0".*?\n     \}', body, re.S).group(0)
        uvl = [tuple(pim_tools.f2(x) for x in r.split()) for r in re.findall(r"\n\s*\d+\s*\(([^)]*)\)", uv)]
        tri = [tuple(map(int, x)) for x in pim_tools.TRI.findall(body[body.find("Triangles"):])]
        for B in (BULLDOG,):
            for side in (1, -1):
                corners = []
                for y in [B[1][0] + (B[1][1] - B[1][0]) * i / 4 for i in range(5)]:
                    for z in [B[2][0] + (B[2][1] - B[2][0]) * i / 4 for i in range(5)]:
                        for i0, i1, i2 in tri:
                            P = [ps[i0], ps[i1], ps[i2]]
                            if any(q[0] * side < B[0][0] - 0.05 for q in P):       # outer skin only
                                continue
                            (y0, z0), (y1, z1), (y2, z2) = [(q[1], q[2]) for q in P]
                            d = (y1 - y0) * (z2 - z0) - (y2 - y0) * (z1 - z0)
                            if abs(d) < 1e-9:
                                continue
                            l1 = ((y - y0) * (z2 - z0) - (y2 - y0) * (z - z0)) / d
                            l2 = ((y1 - y0) * (z - z0) - (y - y0) * (z1 - z0)) / d
                            if l1 >= -1e-4 and l2 >= -1e-4 and l1 + l2 <= 1 + 1e-4:
                                U = [uvl[i0], uvl[i1], uvl[i2]]
                                corners.append(tuple(U[0][k] + l1 * (U[1][k] - U[0][k]) + l2 * (U[2][k] - U[0][k]) for k in range(2)))
                                break
                if len(corners) >= 4:
                    rects.append(corners)
    return rects


ao = Image.open(os.path.join(SRC, "a", *CAB_AO.strip("/").split("/")) + ".dds").convert("RGBA")
aw, ah = ao.size
apx = ao.load()
for c in ao_rects():
    x0, x1 = int(min(u for u, v in c) * aw) - 4, int(max(u for u, v in c) * aw) + 5
    y0, y1 = int(min(v for u, v in c) * ah) - 4, int(max(v for u, v in c) * ah) + 5
    if x1 - x0 > 150 or y1 - y0 > 150:                                      # box across a UV seam
        print("cab AO: skipped", (x0, y0, x1, y1))
        continue
    area = sorted((sum(apx[x, y][:3]), apx[x, y]) for x in range(x0, x1) for y in range(y0, y1))
    med, bg = area[len(area) // 2]
    dark = [(x, y) for x in range(x0, x1) for y in range(y0, y1) if sum(apx[x, y][:3]) < med - 120]
    if any(x in (x0, x1 - 1) or y in (y0, y1 - 1) for x, y in dark):          # UV island edge, no enclosed silhouette
        print("cab AO: skipped (island edge)", (x0, y0, x1, y1))
        continue
    # mask incl. the soft edge (2 px around), filled row by row between the AO left and right of it
    mask = {(x + i, y + j) for x, y in dark for i in range(-2, 3) for j in range(-2, 3)}
    for y in range(y0 - 2, y1 + 2):
        xs = sorted(x for x, yy in mask if yy == y)
        for x in xs:
            a, b = x, x
            while (a, y) in mask:
                a -= 1
            while (b, y) in mask:
                b += 1
            ca, cb = apx[a, y], apx[b, y]
            f = (x - a) / (b - a)
            apx[x, y] = tuple(round(ca[k] + (cb[k] - ca[k]) * f) for k in range(4))
    print("cab AO: %d px filled in" % len(mask), (x0, y0, x1, y1))
pdir = os.path.join(PROJ, *OUT.split("/"))
mpj.save_dds(ao, os.path.join(pdir, "cab_ao.dds"))
open(os.path.join(pdir, "cab_ao.tobj"), "w").write("map 2d cab_ao.dds\n")
tpit = tpit.replace('"%s"' % CAB_AO, '"/%s/cab_ao"' % OUT)
if uvs:
    # the R.D. Trucking paint job has a bulldog silhouette on each door (its UV islands are offset from the chrome
    # emblem): scan a band around the emblem's V across the whole texture, fill every blob (cluster of pixels that
    # differ from the paint colour) with the paint colour
    pj = os.path.join(SRC, "k", *PAINTJOB.strip("/").split("/"))
    img = Image.open(pj + ".dds").convert("RGBA")
    w, hgt = img.size
    ipx = img.load()
    bands = {(max(0, int(min(v for u, v in c) * hgt) - 120), min(hgt, int(max(v for u, v in c) * hgt) + 120)) for c in uvs}
    for y0, y1 in sorted(bands):
        samp = sorted(sum(ipx[x, y][:3]) for x in range(0, w, 7) for y in range(y0, y1, 7))
        med = samp[len(samp) // 2]
        bg = next(ipx[x, y] for x in range(0, w, 7) for y in range(y0, y1, 7) if sum(ipx[x, y][:3]) == med)
        cols = sorted({x for x in range(0, w, 2) for y in range(y0, y1, 2) if abs(sum(ipx[x, y][:3]) - med) > 40})
        groups, cur = [], []
        for x in cols:
            if cur and x - cur[-1] > 40:
                groups.append(cur); cur = []
            cur.append(x)
        if cur:
            groups.append(cur)
        for g in groups:
            ys = [y for y in range(y0, y1, 2) for x in range(g[0], g[-1] + 1, 2) if abs(sum(ipx[x, y][:3]) - med) > 40]
            box = (g[0] - 6, min(ys) - 6, g[-1] + 7, max(ys) + 7)
            if box[2] - box[0] > 500 or box[3] - box[1] > 300:
                print("paint job: skipped large feature", box)
                continue
            img.paste(bg, box)
            print("paint job bulldog filled: px", box)
    pdir = os.path.join(PROJ, *OUT.split("/"))
    mpj.save_dds(img, os.path.join(pdir, "paintjob_cabin.dds"))
    open(os.path.join(pdir, "paintjob_cabin.tobj"), "w").write("map 2d paintjob_cabin.dds\naddr clamp_to_edge clamp_to_edge\n")
out = os.path.join(PROJ, *OUT.split("/"), "truck_sleeper_700")
open(out + ".pim", "w", encoding="utf-8").write(ttext)
blocks = list(re.finditer(r"Material \{.*?\n    \}", tpit, re.S))
blk = blocks[DOOR_FRAME_MAT].group(0)
blk = re.sub(r'(Tag:\s*"diffuse"\s*Value:\s*\()[^)]*', r'\1 0.020000  0.020000  0.020000 ', blk)
blk = re.sub(r'(Tag:\s*"env_factor"\s*Value:\s*\()[^)]*', r'\1 0.200000  0.200000  0.200000 ', blk)
tpit = tpit[:blocks[DOOR_FRAME_MAT].start()] + blk + tpit[blocks[DOOR_FRAME_MAT].end():]
sm = re.search(r"Piece \{\s*Index: %d\s.*?\n\}" % CHROME_PIECE, ttext, re.S)
spiece = sm.group(0)
tmpl = {tag: tuple(pim_tools.f2(x) for x in re.search(r'Tag:\s*"%s".*?\n\s*0\s+\(([^)]*)\)' % tag, spiece, re.S).group(1).split())
        for tag in re.findall(r'Tag:\s*"(\w+)"', spiece)}
sverts, stris = [], []
for side in (1, -1):
    xs = sorted(side * v for v in SLEEPER_STRIP[0])
    vv, tt = pim_tools.box((xs[0], SLEEPER_STRIP[1][0], SLEEPER_STRIP[2][0]), (xs[1], SLEEPER_STRIP[1][1], SLEEPER_STRIP[2][1]))
    base = len(sverts)
    sverts += [dict(tmpl, _POSITION=q, _NORMAL=n) for q, n in vv]
    stris += [(a + base, b + base, c + base) for a, b, c in tt]
spiece = pim_tools.append_geometry(spiece, sverts, stris)
ttext = ttext[:sm.start()] + spiece + ttext[sm.end():]
g = re.search(r"Global \{\s*VertexCount: (\d+)\s*TriangleCount: (\d+)", ttext)
ttext = ttext.replace(g.group(0), g.group(0).replace("VertexCount: " + g.group(1), "VertexCount: %d" % (int(g.group(1)) + len(sverts)))
                      .replace("TriangleCount: " + g.group(2), "TriangleCount: %d" % (int(g.group(2)) + len(stris))), 1)
open(out + ".pim", "w", encoding="utf-8").write(ttext)
open(out + ".pit", "w", encoding="utf-8").write(tpit)
if os.path.isfile(tsrc + ".pic"):
    shutil.copy2(tsrc + ".pic", out + ".pic")

# bull bar: tops of the loops follow the front outline of the hood / fenders (cab model, front view) at BULL_GAP above it
bl = re.search(r'Locator \{\s*Name: "bumper".*?Position:\s*(\([^)]*\))', ttext, re.S).group(1)
_, bly, blz = (pim_tools.f2(c) for c in pim_tools.VEC.match(bl).groups())
cpts = [q for q in pim_tools.positions(ttext) if q[2] < blz + BULL_DEPTH and q[1] > bly + 0.4]
sil = []
for i in range(0, 25):
    ys = [q[1] - bly for q in cpts if abs(abs(q[0]) - i * 0.05) < 0.03]
    sil.append(max(ys) if ys else None)
for i, v in enumerate(sil):                                    # gaps (hood / fender joint): interpolate
    if v is None:
        a = next(j for j in range(i, -1, -1) if sil[j] is not None)
        b = next((j for j in range(i, len(sil)) if sil[j] is not None), a)
        sil[i] = sil[a] + (sil[b] - sil[a]) * ((i - a) / (b - a) if b != a else 0)
sil = [sum(sil[max(0, i - 1):i + 2]) / len(sil[max(0, i - 1):i + 2]) for i in range(len(sil))]
sil = [min(sil[:i + 1]) if i * 0.05 > 0.6 else v for i, v in enumerate(sil)]  # outside the hood: only down (mirrors, lamps)
outline = lambda x: sil[min(len(sil) - 1, int(abs(x) / 0.05))] + BULL_GAP
bpath = os.path.join(PROJ, *OUT.split("/"), "bumper.pim")
btext = open(bpath, encoding="utf-8").read()
ctop = max(hi[1] for lo, hi in [pim_tools.bbox(btext)])
# like the real truck: side loops (over the headlamps) unchanged with their flat tops, the centre loop gets a flat top at
# the hood's crown + BULL_GAP and sloped corners from the end of the straight top bar down to the side loop tops
cw = 0.6
ctop_y = outline(0)                                            # hood crown in the middle
fr = (ctop_y - BULL_BASE) / (ctop - BULL_BASE)                 # centre rails + loop: uniform vertical scale
side_y = BULL_BASE + (BULL_SIDE_RAIL + BULL_TUBE - BULL_BASE) * fr + BULL_SIDE_UP  # side loop tops: top of that rail
lim = lambda v: max(0.0, min(1.0, v))
sx = BULL_CENTRE_W / 0.59
wide = lambda x: (x * sx if abs(x) <= 0.59 else
                  (0.59 * sx + (abs(x) - 0.59) * (1.2 - 0.59 * sx) / (1.2 - 0.59)) * (1 if x > 0 else -1))
r = BULL_TUBE / 2
def follow(q, n, lo, hi):
    """New position + normal of a bumper vertex (n: its normal)."""
    x, y, z = q
    if hi[0] - lo[0] > 1.5:                                   # full width plates / rails
        return q, n
    if hi[1] <= BULL_BASE + 0.05 or y <= BULL_BASE:
        return (wide(x), y, z), n
    if max(abs(lo[0]), abs(hi[0])) > cw:                       # side loop: top part moved rigidly, posts stretched
        w = lim((y - BULL_BASE) / (hi[1] - 0.12 - BULL_BASE))
        nx_ = wide(x)
        if abs(x) < 0.62:                                      # inner ends: into the centre posts (no gap)
            nx_ -= BULL_SIDE_IN * (1 if x > 0 else -1)
        return (nx_, y - (hi[1] - side_y) * w, z), n
    if hi[1] - lo[1] < 0.1:                                    # centre rails: equally spaced around the one that the
        k = round((lo[1] - BULL_SIDE_RAIL) / 0.245)            # side loop tops meet; the top one half way up the
        cy = side_y - r + k * rail_gap if k <= 0 else (q0[1] + q1[1]) / 2   # slopes, shortened to end at them
        xe = slope_x(cy)
        if xe < hi[0]:
            x = x * xe / hi[0]
        return (wide(x), y + cy - (lo[1] + BULL_TUBE / 2), z), n
    s = 1 if x >= 0 else -1
    ax, nx = abs(x), n[0] * s
    cx, cy = ax - nx * r, y - n[1] * r                         # centre line point of this tube vertex
    if cy > bend[1] and cx <= flat_end + 0.01:                 # straight top bar: flat, ends moved inward
        return (wide(s * (cx * ca[0] / flat_end + (ax - cx))), y - ty0 + q0[1], z), n
    if cy > bend[1]:                                           # corner bend -> rounded corner, slope, rounded corner
        a = math.atan2(cy - bend[1], cx - bend[0])
        a = max(0.0, min(math.pi / 2, a))
        (ncx, ncy), tau = corner_path(1 - a / (math.pi / 2))
        dl = tau - (a - math.pi / 2)                           # tangent rotation
        ox, oy = ax - cx, y - cy
        cs, sn = math.cos(dl), math.sin(dl)
        rx, ry = ox * cs - oy * sn, ox * sn + oy * cs
        nnx, nny = nx * cs - n[1] * sn, nx * sn + n[1] * cs
        return (wide(s * (ncx + rx)), ncy + ry, z), (s * nnx, nny, n[2])
    if y > BULL_BASE:                                          # posts: shortened to end at the lower rounded corner
        y = BULL_BASE + (y - BULL_BASE) * (cd[1] - BULL_BASE) / (bend[1] - BULL_BASE)
    return (wide(x), y, z), n


def corner_path(t):
    """Centre line of the new corner, t 0..1: arc (top bar -> slope), straight slope, arc (slope -> post).
    Returns the point and the tangent angle."""
    if t < 0.4:
        tau = -gam * t / 0.4
        o = o1
    elif t <= 0.6:
        f = (t - 0.4) / 0.2
        return (cb[0] + f * (cc[0] - cb[0]), cb[1] + f * (cc[1] - cb[1])), -gam
    else:
        tau = -gam - (math.pi / 2 - gam) * (t - 0.6) / 0.4
        o = o2
    return (o[0] - rf * math.sin(tau), o[1] + rf * math.cos(tau)), tau


def reshape(text):
    def piece(m):
        body = m.group(0)
        recs = []
        pim_tools.transform_components(body, lambda q, lo, hi: recs.append((lo, hi)) or q)
        ns = re.search(r'(Tag:\s*"_NORMAL"\s*\n)(.*?)(\n\s*\})', body, re.S)
        nrm = [tuple(pim_tools.f2(c) for c in v.groups()) for v in pim_tools.VEC.finditer(ns.group(2))] if ns else None
        res = [follow(q, nrm[i] if nrm else (0.0, 1.0, 0.0), *recs[i]) for i, q in enumerate(pim_tools.positions(body))]
        it = iter(res)
        body = pim_tools.POS_STREAM.sub(lambda s: s.group(1) + pim_tools.VEC.sub(
            lambda v: "( %s  %s  %s )" % tuple(pim_tools.h(c) for c in next(it)[0]), s.group(2)) + s.group(3), body)
        if ns:
            it = iter(res)
            body = re.sub(r'(Tag:\s*"_NORMAL"\s*\n)(.*?)(\n\s*\})', lambda s: s.group(1) + pim_tools.VEC.sub(
                lambda v: "( %s  %s  %s )" % tuple(pim_tools.h(c) for c in next(it)[1]), s.group(2)) + s.group(3),
                body, flags=re.S)
        return body
    return re.sub(r"Piece \{.*?\n\}", piece, text, flags=re.S)


ctop_prof = {}
post_x = [0.0]
def prof(q, lo, hi):
    if max(abs(lo[0]), abs(hi[0])) <= cw and hi[1] - lo[1] >= 0.1 and hi[1] > BULL_BASE + 0.05:
        k = round(q[0], 2)
        ctop_prof[k] = max(ctop_prof.get(k, -9), q[1])
        if 0.4 < q[1] < 0.8:
            post_x[0] = max(post_x[0], abs(q[0]))
    return q
pim_tools.transform_components(btext, prof)
# real tube radius of the top bar (x = 0): the corner rings are rebuilt around their centre line with this radius
top0 = [q[1] for q in pim_tools.positions(btext) if abs(q[0]) < 0.005 and q[1] > max(ctop_prof.values()) - 0.1]
r = (max(top0) - min(top0)) / 2
# original centre loop: straight top bar to flat_end, then a round bend (centre `bend`) into the posts (centre x px)
flat_end = min(k for k, v in ctop_prof.items() if k > 0.05 and v >= max(ctop_prof.values()) - r)
ty0 = max(ctop_prof.values()) - r
px = max(ctop_prof) - r
bend = (flat_end, ty0 - (px - flat_end))
# new: flat top bar (centre q0[1]) up to q0[0] = BULL_SLOPE_IN before the bend, straight slope to the post at the
# height of the side loop tops (q1)
q0 = (flat_end - BULL_SLOPE_IN, ctop_y - r)
q1 = (px, side_y - r)
slope_x = lambda yc: q1[0] if yc <= q1[1] else q0[0] + (q0[1] - yc) / (q0[1] - q1[1]) * (q1[0] - q0[0])
# rounded corners (radius BULL_ROUND) where the top bar turns into the slope and the slope into the post
slen = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
ux, uy = (q1[0] - q0[0]) / slen, (q1[1] - q0[1]) / slen
gam = -math.atan2(uy, ux)                                     # slope angle below horizontal
rf = min(BULL_ROUND, 0.45 * slen / max(math.tan(gam / 2), math.tan((math.pi / 2 - gam) / 2)))
d1, d2 = rf * math.tan(gam / 2), rf * math.tan((math.pi / 2 - gam) / 2)
ca = (q0[0] - d1, q0[1])                                      # top bar end
cb = (q0[0] + d1 * ux, q0[1] + d1 * uy)                       # slope start / end
cc = (q1[0] - d2 * ux, q1[1] - d2 * uy)
cd = (q1[0], q1[1] - d2)                                      # post top
o1 = (ca[0], ca[1] - rf)
o2 = (cc[0] + rf * uy, cc[1] - rf * ux)
rail_gap = 0.245 * fr
print("bull bar: centre top %.2f, side tops / middle rail %.2f, rails every %.2f" % (ctop_y, side_y, rail_gap))
open(bpath, "w", encoding="utf-8").write(reshape(btext))
print("bull bar outline (bumper frame, |x| 0..1.2 every 0.2 m):", ["%.2f" % outline(i * 0.2) for i in range(7)])

# fuel tank trailer: ladder copies for the middle of the tank
for need, flt in ((os.path.join(o.game, *FT.strip("/").split("/"), "accessory", "f_body", "ladder.pmd"), FT + "/*"),):
    if not os.path.isfile(need):
        subprocess.run([o.extractor, os.path.join(o.scs_dir, "base_vehicle.scs"), "-f", flt, "-d", o.game], capture_output=True)
lb = open(os.path.join(o.game, *FT.strip("/").split("/"), "accessory", "f_body", "ladder.pmd"), "rb").read().decode("latin-1")
for mat in set(re.findall(r"/automat/[0-9a-f]{2}/[0-9a-f]+\.mat", lb)):
    if not os.path.isfile(os.path.join(o.game, *mat.strip("/").split("/"))):
        for scs in ("base_vehicle.scs", "base.scs", "base_share.scs"):
            subprocess.run([o.extractor, os.path.join(o.scs_dir, scs), "-f", mat, "-d", o.game], capture_output=True)
run(cpx, "-b", o.game, "-m", FT + "/accessory/f_body/ladder", "-e", pix)
lsrc = os.path.join(pix, *FT.strip("/").split("/"), "accessory", "f_body", "ladder")
ltext = open(lsrc + ".pim", encoding="utf-8").read()
lpit = open(lsrc + ".pit", encoding="utf-8").read()
ltop = max(q[2] for q in pim_tools.positions(ltext) if q[1] > FT_TOP_Y)


def rot_streams(text):
    """Normals / tangents rotated like the ladder: (x, y, z) -> (-z, y, x)."""
    def stream(m):
        def vec(v):
            c = v.group(1).split()
            return "( %s )" % "  ".join([pim_tools.h(-pim_tools.f2(c[2])), c[1], c[0]] + c[3:])
        return m.group(1) + re.sub(r"\(([^)]*)\)", vec, m.group(2)) + m.group(3)
    return re.sub(r'(Tag:\s*"_(?:NORMAL|TANGENT)"\s*\n)(.*?)(\n\s*\})', stream, text, flags=re.S)


for chm in FT_CHASSIS:
    cb = open(os.path.join(o.game, *FT.strip("/").split("/"), "chassis", chm + ".pmd"), "rb").read().decode("latin-1")
    for mat in set(re.findall(r"/automat/[0-9a-f]{2}/[0-9a-f]+\.mat", cb)):
        if not os.path.isfile(os.path.join(o.game, *mat.strip("/").split("/"))):
            for scs in ("base_vehicle.scs", "base.scs", "base_share.scs"):
                subprocess.run([o.extractor, os.path.join(o.scs_dir, scs), "-f", mat, "-d", o.game], capture_output=True)
    run(cpx, "-b", o.game, "-m", FT + "/chassis/" + chm, "-e", pix)
    csrc = os.path.join(pix, *FT.strip("/").split("/"), "chassis", chm)
    ctx = open(csrc + ".pim", encoding="utf-8").read()
    loc = re.search(r'Locator \{\s*Name: "f_body".*?Position:\s*(\([^)]*\))', ctx, re.S).group(1)
    lx, ly, lz = (pim_tools.f2(c) for c in pim_tools.VEC.match(loc).groups())
    cp = list(pim_tools.positions(ctx))
    band = lambda y: [q for q in cp if abs(q[1] - y) < 0.05]
    yc = max((y / 100 for y in range(190, 261, 5)), key=lambda y: max((abs(q[0]) for q in band(y)), default=0))
    width = max(abs(q[0]) for q in band(yc))
    heads = [q[2] for q in band(yc) if abs(q[0]) < 0.3]
    zc = (min(heads) + max(heads)) / 2
    x0 = width + FT_LADDER_OUT
    k = (x0 - FT_CATWALK) / ltop
    move = lambda q: (x0 - q[2] * (k if q[1] > FT_TOP_Y else 1.0), q[1], zc + q[0] - lz)
    out = os.path.join(PROJ, *OUT.split("/"), "fueltank", "ladder_" + chm)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out + ".pim", "w", encoding="utf-8").write(rot_streams(pim_tools.transform(ltext, move)))
    open(out + ".pit", "w", encoding="utf-8").write(lpit.replace("ladder.pim", "ladder_%s.pim" % chm))
    print("fuel tank %-12s tank z %.2f..%.2f, |x| %.2f at y %.2f -> ladder x %.2f z %.2f" % (
        chm, min(heads), max(heads), width, yc, x0, zc))
    # chassis copy without the fender decks (front + rear mudguards incl. supports / mudflap hanger) and the rear ladder
    boxes = []
    def find(q, lo, hi):
        if (min(abs(lo[0]), abs(hi[0])) >= FT_DECK[0] and max(abs(lo[0]), abs(hi[0])) <= FT_DECK[1]
                and FT_DECK[2] <= lo[1] and hi[1] <= FT_DECK[3] and hi[2] - lo[2] > 1.5):
            b = (tuple(lo), tuple(hi))
            if b not in boxes:
                boxes.append(b)
        return q
    pim_tools.transform_components(ctx, find)
    zr = max(heads)
    gone = [0]
    def strip(q, lo, hi):
        ax = sorted((abs(lo[0]), abs(hi[0])))
        if lo[0] < 0 < hi[0]:
            ax[0] = 0.0
        deck = any(ax[0] >= 0.53 and ax[1] >= 0.75 and ax[1] <= FT_DECK[1] and lo[1] >= dl[1] - 0.05
                   and hi[1] <= dh[1] + 0.02 and lo[2] >= dl[2] - 0.12 and hi[2] <= dh[2] + 0.12 for dl, dh in boxes)
        ladder = (ax[1] <= 0.46 and lo[2] >= zr - 0.67 and hi[2] >= zr - 0.22 and lo[1] >= 0.85
                  and (hi[1] - lo[1] > 2.0 or (lo[1] >= 1.4 and (ax[0] < 0.3 or lo[1] >= 2.5))))
        ladder = ladder or (0.35 <= ax[0] and ax[1] <= 0.48 and 2.75 <= lo[1] and hi[1] <= 2.92
                            and lo[2] >= zr - 0.4)                  # stubs of the top handrails on the rear plate
        if deck or ladder:
            gone[0] += 1
            return tuple(lo)
        return q
    ctx = pim_tools.transform_components(ctx, strip)
    out = os.path.join(PROJ, *OUT.split("/"), "fueltank", chm)
    open(out + ".pim", "w", encoding="utf-8").write(ctx)
    shutil.copy2(csrc + ".pit", out + ".pit")
    for ext in (".pic", ".pip"):
        if os.path.isfile(csrc + ext):
            shutil.copy2(csrc + ext, out + ext)
    print("fuel tank %-12s %d fender deck(s), %d vertices removed" % (chm, len(boxes), gone[0]))

# 3. compile
link = os.path.join(o.conv, "rsrc", "rd_r")
if not os.path.exists(link):
    subprocess.run(["cmd", "/c", "mklink", "/J", link, PROJ], check=True, capture_output=True)
tools = os.path.join(o.conv, "bin", "win_x64", "tools")
shutil.rmtree(os.path.join(o.conv, "rsrc", "rsrc", "rd_r"), ignore_errors=True)
subprocess.run([os.path.join(tools, "resconvert.exe"), "-update", "-root", "rsrc/rd_r"], cwd=tools, capture_output=True)
log = open(os.path.join(tools, "mass_convert.log"), encoding="utf-8", errors="replace").read()
if "*** ERROR" in log:
    sys.exit("conversion failed:\n" + "\n".join(l for l in log.splitlines() if "ERROR" in l))
cache = os.path.join(o.conv, "rsrc", "rsrc", "rd_r", "@cache")
# only our models + their materials; textures stay with the source mods (no overrides of their files)
shutil.copytree(os.path.join(cache, *OUT.split("/")), os.path.join(MOD, *OUT.split("/")))
shutil.copytree(os.path.join(cache, "automat"), os.path.join(MOD, "automat"))

# black steel wheel discs (no recompile: binary copy, material path swapped, material = SCS one with black diffuse)
wsrc = os.path.join(o.game, *WHEEL_SRC.strip("/").split("/"))
for slot, (unit, model, mat, black, extra) in WHEELS.items():
    assert len(mat) == len(black)
    for need, flt in ((os.path.join(wsrc, model + ".pmd"), WHEEL_SRC + "/" + model + ".*"),
                      (os.path.join(o.game, *mat.strip("/").split("/")), mat)):
        if not os.path.isfile(need):
            for scs in ("base_vehicle.scs", "base.scs", "base_share.scs"):
                subprocess.run([o.extractor, os.path.join(o.scs_dir, scs), "-f", flt, "-d", o.game], capture_output=True)
    for ext in (".pmd", ".pmg"):
        b = open(os.path.join(wsrc, model + ext), "rb").read()
        if ext == ".pmd":
            assert mat.encode() in b
            b = b.replace(mat.encode(), black.encode())
        dst = os.path.join(MOD, "vehicle", "wheel", "rd_black", model + ext)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(b)
    m = open(os.path.join(o.game, *mat.strip("/").split("/")), encoding="utf-8").read()
    m = re.sub(r"diffuse : \{[^}]*\}", "diffuse : { 0.025000 , 0.025000 , 0.025000 }", m)
    wr(black.lstrip("/"), m)
    wr("def/vehicle/%s/rd_black.sii" % slot,
       "SiiNunit\n{\naccessory_rim_data : rdblack.%s\n{\n\tname: \"Steel Black\"\n\tprice: 600\n\tunlock: 0\n"
       "\tmodel: \"/vehicle/wheel/rd_black/%s.pmd\"\n\ticon: \"disc/%s\"\n\tpart_type: aftermarket\n%s}\n}\n"
       % (unit, model, model, extra))

# fifth wheel all the way back on the 235 chassis (6xxST 235 WB 260 gal): the coupling locator hook_t in a copy of
# the add-on truck model (binary patch of its .pmg) and the fifth wheel (piece 0 of the chass model) move by FIFTH_BACK
# m to the rear; the add-on's 235 chassis + chass definitions are overridden to use them
for cab in ("r700sleep", "r700sleepd"):
    c = open(os.path.join(SRC, "a", "def", "vehicle", "truck", TRUCK, "cabin", cab + ".sii"), encoding="utf-8").read()
    wr("def/vehicle/truck/%s/cabin/%s.sii" % (TRUCK, cab), c.replace('"/sleeper/truck_sleeper_700.pmd"', '"/%s/truck_sleeper_700.pmd"' % OUT))
cdef = os.path.join(SRC, "a", "def", "vehicle", "truck", TRUCK)
c = open(os.path.join(cdef, "chassis", "235st130.sii"), encoding="utf-8").read()
c = c.replace('"/sleeper/truck_sleeper_700.pmd"', '"/%s/truck_sleeper_700.pmd"' % OUT)
wr("def/vehicle/truck/%s/chassis/235st130.sii" % TRUCK, c)
c = open(os.path.join(cdef, "accessory", "chass", "6x4_235_st.sii"), encoding="utf-8").read()
c = c.replace('"/sleeper/chassislong.pmd"', '"/%s/chassislong.pmd"' % OUT)
wr("def/vehicle/truck/%s/accessory/chass/6x4_235_st.sii" % TRUCK, c)

# R.D. Trucking paint job: its cabin mask without the bulldog silhouette (overrides the workshop definition)
pj = open(os.path.join(SRC, "k", "def", "vehicle", "truck", TRUCK, "paint_job", "rubberkris.sii"), encoding="utf-8").read()
wr("def/vehicle/truck/%s/paint_job/rubberkris.sii" % TRUCK, pj.replace('"%s.tobj"' % PAINTJOB, '"/%s/paintjob_cabin.tobj"' % OUT))
wr("def/vehicle/truck/%s/paint_job/rubberkris_settings.sui" % TRUCK,      # @include is relative to the .sii
   open(os.path.join(SRC, "k", "def", "vehicle", "truck", TRUCK, "paint_job", "rubberkris_settings.sui"), encoding="utf-8").read())

# 4. definitions
for slot, (_, _, _, name, icon) in PARTS.items():
    wr("def/vehicle/truck/%s/accessory/%s/rubberduck.sii" % (TRUCK, slot),
       "SiiNunit\n{\naccessory_addon_data : rubberduck.%s.%s\n{\n\tname: \"%s\"\n\tprice: 1500\n\tunlock: 0\n"
       "\ticon: \"%s\"\n\tpart_type: factory\n\texterior_model: \"/%s/%s.pmd\"\n}\n}\n" % (TRUCK, slot, name, icon, OUT, slot))
for slot, (src, _, defs) in WHITE.items():
    for d in defs:
        # the add-on's definitions (more cabins, e.g. R700 / sleepers) win over the base mod's
        dp = [os.path.join(SRC, k, "def", "vehicle", "truck", TRUCK, "accessory", slot, d + ".sii") for k in ("a", src)]
        t = open(next(f for f in dp if os.path.isfile(f)), encoding="utf-8").read()
        t = re.sub(r"accessory_addon_data\s*:\s*\w+\.", "accessory_addon_data : rd_" + d[:9] + ".", t)
        t = re.sub(r'(\tname:\s*)"[^"]*"', r'\1"%s"' % NAMES.get(slot, "Rubber Duck White"), t)
        t = re.sub(r'((?:ex|in)terior_model:\s*)"[^"]*"', r'\1"/%s/%s.pmd"' % (OUT, slot), t)
        wr("def/vehicle/truck/%s/accessory/%s/rd_%s.sii" % (TRUCK, slot, d), t)
# fuel tank trailer: ladder per chassis model, front mudflaps (with their hanger) without a model
lad = open(os.path.join(o.game, *FT_DEF.split("/"), "accessory", "f_body", "ladder.sii"), encoding="utf-8").read()
for chm, units in FT_CHASSIS.items():
    t = re.sub(r"\n\tsuitable_for\[\]:[^\n]*", "", lad)
    t = re.sub(r'(exterior_model:\s*)"[^"]*"', r'\1"/%s/fueltank/ladder_%s.pmd"' % (OUT, chm), t)
    t = t.replace("\n}\n}", "\n" + "".join("\tsuitable_for[]: \"%s.scs.fueltank.chassis\"\n" % u for u in units) + "}\n}", 1)
    if chm == FT_MAIN:
        wr(FT_DEF + "/accessory/f_body/ladder.sii", t)
    else:                                                       # unit name parts: max 12 characters
        unit = "lad_" + chm[3:].replace("_", "")
        wr(FT_DEF + "/accessory/f_body/%s.sii" % unit, t.replace("ladder.scs.fueltank.f_body", unit + ".scs.fueltank.f_body"))
for fm in ("simple", "exclusive"):
    t = open(os.path.join(o.game, *FT_DEF.split("/"), "accessory", "f_mudflap", fm + ".sii"), encoding="utf-8").read()
    wr(FT_DEF + "/accessory/f_mudflap/%s.sii" % fm, re.sub(r"\n\texterior_model:[^\n]*\n", "\n", t))
t = open(os.path.join(o.game, *FT_DEF.split("/"), "accessory", "f_fender", "al.sii"), encoding="utf-8").read()
wr(FT_DEF + "/accessory/f_fender/al.sii", re.sub(r"\n\texterior_model:[^\n]*\n", "\n", t))
cdir = os.path.join(o.game, *FT_DEF.split("/"), "chassis")
for fn in os.listdir(cdir):
    t = open(os.path.join(cdir, fn), encoding="utf-8").read()
    m = re.search(r'model:\s*"%s/chassis/(\w+)\.pmd"' % FT, t)
    if m and m.group(1) in FT_CHASSIS:
        wr(FT_DEF + "/chassis/" + fn, t.replace(m.group(0), 'model: "/%s/fueltank/%s.pmd"' % (OUT, m.group(1))))

wr("manifest.sii",
   "\tdisplay_name: \"Rubber Duck parts - Mack R Series\"\n\tauthor: \"Erich Barnstedt (personal patch)\"\n"
   "\tcategory[]: \"truck\"\n\tdescription_file: \"description.txt\"\n\tcompatible_versions[]: \"1.61.*\"\n}\n}\n")
wr("description.txt", "Rubber Duck look for the Mack R Series: white grill and headlamps, Pinnacle Rubber Duck bull bar.\n"
   "Requires: Mack R Series, Mack R add-on, Pinnacle Rubber Duck. Load this mod above them.\nPersonal use only.\n")

# 5. pack + install
scs = os.path.join(HERE, "rubber_duck_r.scs")
with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fns in os.walk(MOD):
        for fn in fns:
            f = os.path.join(dp, fn)
            z.write(f, os.path.relpath(f, MOD).replace(os.sep, "/"))
if moddir:
    try:
        shutil.copy2(scs, moddir); print("Installed", scs, "->", moddir)
    except PermissionError:
        print("WARNING: mod file is locked - close ATS and run again")
