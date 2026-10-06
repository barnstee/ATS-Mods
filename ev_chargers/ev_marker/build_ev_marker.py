"""Builds ev_chargers.scs: plug world-map icon + spinning plug marker for the map editor."""
import math, os, shutil, struct, subprocess, sys, zipfile
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "project")
MOD = os.path.join(HERE, "mod")
CONV = r"C:\ATSExtract\conversion_tools"
GREEN = (34, 197, 94, 255)


def fh(v):
    return "&" + struct.pack(">f", v).hex()


def save_dds(img, path):
    w, h = img.size
    hdr = struct.pack("<4sIIIIIII44sIIIIIIIIIIIII", b"DDS ", 124, 0x100F, h, w, w * 4, 0, 1, b"\0" * 44,
                      32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, 0x1000, 0, 0, 0, 0)
    r, g, b, a = img.split()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(hdr + Image.merge("RGBA", (b, g, r, a)).tobytes())


def plug_art(size, glow):
    S = 1024
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = 90 if glow else 20
    if glow:
        d.ellipse((m - 60, m - 60, S - m + 60, S - m + 60), fill=(34, 197, 94, 110))
        im = im.filter(ImageFilter.GaussianBlur(40)); d = ImageDraw.Draw(im)
    d.ellipse((m, m, S - m, S - m), fill=GREEN, outline=(255, 255, 255, 255), width=int(S * 0.045))
    c = S // 2; W = (255, 255, 255, 255)
    d.rounded_rectangle((c - 190, c - 120, c + 190, c + 150), radius=70, fill=W)          # plug body
    d.rectangle((c - 120, c - 300, c - 60, c - 110), fill=W)                              # prongs
    d.rectangle((c + 60, c - 300, c + 120, c - 110), fill=W)
    d.rounded_rectangle((c - 45, c + 140, c + 45, c + 330), radius=30, fill=W)            # cable
    d.polygon([(c + 25, c - 80), (c - 70, c + 40), (c - 5, c + 40), (c - 35, c + 120), (c + 70, c - 10), (c + 5, c - 10)], fill=GREEN)   # bolt
    return im.resize((size, size), Image.LANCZOS)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8", newline="\n").write(text)


def marker_sources(mdir):
    w, y0, y1 = 0.8, 3.2, 4.8
    quads = [((1, 0, 0), (0, 0, 1)), ((0, 0, 1), (-1, 0, 0))]     # (right axis, normal) of the two crossed planes
    P, N, UV = [], [], []
    tris = []
    for right, nrm in quads:
        for side in (1, -1):
            base = len(P)
            n = tuple(c * side for c in nrm)
            for (u, v, sx, yy) in ((0, 1, -1, y0), (1, 1, 1, y0), (1, 0, 1, y1), (0, 0, -1, y1)):
                uu = u if side > 0 else 1 - u
                P.append((right[0] * sx * w * side, yy, right[2] * sx * w * side)); N.append(n); UV.append((uu, v))
            tris += [(base, base + 2, base + 1), (base, base + 3, base + 2)]
    nv = len(P)
    L = ["Header {", "     FormatVersion: 5", "     Source: \"build_ev_marker\"", "     Type: \"Model\"", "     Name: \"plug_marker\"", "}",
         "Global {", "     VertexCount: %d" % nv, "     TriangleCount: %d" % len(tris), "     MaterialCount: 1", "     PieceCount: 1",
         "     PartCount: 1", "     BoneCount: 1", "     LocatorCount: 0", "     Skeleton: \"plug_marker.pis\"", "}",
         "Material {", "     Alias: \"plug\"", "     Effect: \"eut2.dif.spec.a\"", "}",
         "Piece {", "     Index: 0", "     Material: 0", "     VertexCount: %d" % nv, "     TriangleCount: %d" % len(tris), "     StreamCount: 4"]
    def stream(fmt, tag, rows, extra=()):
        out = ["     Stream {", "          Format: " + fmt, "          Tag: \"%s\"" % tag] + list(extra)
        out += ["          %-5d( %s )" % (i, "  ".join(fh(x) for x in r)) for i, r in enumerate(rows)]
        return out + ["     }"]
    L += stream("FLOAT3", "_POSITION", P) + stream("FLOAT3", "_NORMAL", N)
    L += stream("FLOAT2", "_UV0", UV, ["          AliasCount: 1", "          Aliases: \"_TEXCOORD0\" "])
    L += stream("FLOAT4", "_RGBA", [(1, 1, 1, 1)] * nv)
    L += ["     Triangles {"] + ["          %-5d( %d     %d     %d )" % ((i,) + t) for i, t in enumerate(tris)] + ["     }", "}"]
    L += ["Part {", "     Name: \"vis\"", "     PieceCount: 1", "     LocatorCount: 0", "     Pieces: 0 ", "     Locators: ", "}",
          "Bones {", "     0    ( \"spin\" )", "}",
          "Skin {", "     StreamCount: 1", "     SkinStream {", "          Format: FLOAT3", "          Tag: \"_POSITION\"",
          "          ItemCount: %d" % nv, "          TotalWeightCount: %d" % nv, "          TotalCloneCount: %d" % nv]
    for i, p in enumerate(P):
        L += ["          %-5d ( ( %s )" % (i, "  ".join(fh(x) for x in p)), "                    Weights: 1      0    &3f800000 ",
              "                    Clones: 1      0    %d     " % i, "                )"]
    L += ["     }", "}"]
    write(os.path.join(mdir, "plug_marker.pim"), "\n".join(L) + "\n")
    ident = ["&3f800000  &00000000  &00000000  &00000000", "&00000000  &3f800000  &00000000  &00000000",
             "&00000000  &00000000  &3f800000  &00000000", "&00000000  &00000000  &00000000  &3f800000"]
    write(os.path.join(mdir, "plug_marker.pis"), "\n".join(["Header {", "     FormatVersion: 1", "     Source: \"build_ev_marker\"", "     Type: \"Skeleton\"",
          "     Name: \"plug_marker\"", "}", "Global {", "     BoneCount: 1", "}", "Bones {", "     0     ( Name:  \"spin\"", "             Parent: \"\"",
          "             Matrix: ( " + ident[0], "                       " + ident[1], "                       " + ident[2], "                       " + ident[3] + " )", "       )", "}"]) + "\n")
    T, K = 3.0, 61
    A = ["Header {", "    FormatVersion: 3", "    Source: \"build_ev_marker\"", "    Type: \"Animation\"", "    Name: \"plug_marker_spin\"", "}",
         "Global {", "    Skeleton: \"plug_marker.pis\"", "    TotalTime: %f" % T, "    BoneChannelCount: 1", "    CustomChannelCount: 0", "}",
         "BoneChannel {", "    Name: \"spin\"", "    StreamCount: 2", "    KeyframeCount: %d" % K,
         "    Stream {", "        Format: FLOAT", "        Tag: \"_TIME\""]
    A += ["        %-4d ( %s )" % (i, fh(T / (K - 1))) for i in range(K)]
    A += ["    }", "    Stream {", "        Format: FLOAT4x4", "        Tag: \"_MATRIX\""]
    for i in range(K):
        a = 2 * math.pi * i / (K - 1); c, s = math.cos(a), math.sin(a)
        rows = [(c, 0, -s, 0), (0, 1, 0, 0), (s, 0, c, 0), (0, 0, 0, 1)]
        A.append("        %-4d ( %s" % (i, "  ".join(fh(x) for x in rows[0])))
        A += ["               " + "  ".join(fh(x) for x in r) for r in rows[1:3]]
        A.append("               " + "  ".join(fh(x) for x in rows[3]) + " )")
    A += ["    }", "}"]
    write(os.path.join(mdir, "plug_marker_spin.pia"), "\n".join(A) + "\n")
    attrs = [("FLOAT", "add_ambient", "1.000000"), ("FLOAT3", "diffuse", "1.000000  1.000000  1.000000"), ("FLOAT", "reflection", "0.000000"),
             ("FLOAT", "shininess", "4.000000"), ("FLOAT3", "specular", "0.000000  0.000000  0.000000")]
    M = ["Header {", "    FormatVersion: 1", "    Source: \"build_ev_marker\"", "    Type: \"Trait\"", "    Name: \"plug_marker\"", "}",
         "Global {", "    LookCount: 1", "    VariantCount: 1", "    PartCount: 1", "    MaterialCount: 1", "}",
         "Look {", "    Name: \"default\"", "    Material {", "        Alias: \"plug\"", "        Effect: \"eut2.dif.spec.a\"", "        Flags: 0",
         "        AttributeCount: %d" % len(attrs), "        TextureCount: 1"]
    for f, tg, v in attrs:
        M += ["        Attribute {", "            Format: " + f, "            Tag: \"%s\"" % tg, "            Value: ( %s )" % v, "        }"]
    M += ["        Texture {", "            Tag: \"texture[0]:texture_base\"", "            Value: \"/model/ev_chargers/plug_marker\"", "        }", "    }", "}",
          "Variant {", "    Name: \"default\"", "    Part {", "        Name: \"vis\"", "        AttributeCount: 1", "        Attribute {", "            Format: INT",
          "            Tag: \"visible\"", "            Value: ( 1 )", "        }", "    }", "}"]
    write(os.path.join(mdir, "plug_marker.pit"), "\n".join(M) + "\n")


def main():
    shutil.rmtree(PROJ, ignore_errors=True); shutil.rmtree(MOD, ignore_errors=True)
    mdir = os.path.join(PROJ, "model", "ev_chargers")
    save_dds(plug_art(256, True), os.path.join(mdir, "plug_marker.dds"))
    write(os.path.join(mdir, "plug_marker.tobj"), "map 2d plug_marker.dds\naddr clamp_to_edge clamp_to_edge\n")
    udir = os.path.join(PROJ, "material", "ui", "map", "road")
    save_dds(plug_art(64, False), os.path.join(udir, "road_ev_plug.dds"))
    write(os.path.join(udir, "road_ev_plug.tobj"), "map 2d road_ev_plug.dds\naddr clamp_to_edge clamp_to_edge\n")
    plug_art(256, True).save(os.path.join(HERE, "plug_preview.png"))
    marker_sources(mdir)
    link = os.path.join(CONV, "rsrc", "ev_chargers")
    if not os.path.exists(link):
        subprocess.run(["cmd", "/c", "mklink", "/J", link, PROJ], check=True, capture_output=True)
    tools = os.path.join(CONV, "bin", "win_x64", "tools")
    shutil.rmtree(os.path.join(CONV, "rsrc", "rsrc", "ev_chargers"), ignore_errors=True)
    subprocess.run([os.path.join(tools, "resconvert.exe"), "-update", "-root", "rsrc/ev_chargers"], cwd=tools, capture_output=True)
    log = open(os.path.join(tools, "mass_convert.log"), encoding="utf-8", errors="replace").read()
    errs = [l for l in log.splitlines() if "ERROR" in l]
    if errs:
        sys.exit("conversion failed:\n" + "\n".join(errs))
    cache = os.path.join(CONV, "rsrc", "rsrc", "ev_chargers", "@cache")
    shutil.copytree(cache, MOD)
    for dp, _, fns in os.walk(MOD):
        for fn in fns:
            print("  built", os.path.relpath(os.path.join(dp, fn), MOD))


if __name__ == "__main__":
    main()
