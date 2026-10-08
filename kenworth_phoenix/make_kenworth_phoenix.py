"""make_kenworth_phoenix.py [--game C:\\ATSExtract] [--logo <logo.jpg>]

Small mod: the "Phoenix Trucking" paint job (white metallic + logo on the sleeper sides/back, as on the VNL Electric)
for the Kenworth T680 (2014). Logo masks are projected through the cab paint UVs by vnl_electric/tools/make_paintjob.py.
Output: kenworth_phoenix.scs in the repo root, copied to Documents\\American Truck Simulator\\mod.
Needs: Kenworth T680 DLC extracted to the game dir (dlc_kenworth_t680.scs), ConverterPIX, Pillow, numpy, conversion tools.
"""
import argparse, io, os, re, shutil, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "vnl_electric", "tools")
TRUCK = "kenworth.t680"                           # def id
MODEL = "kenworth_t680"                           # model folder (one truck.pmd for all cabs)
# cab: (atlas slot of the cab paint mask, model parts of its variant); slots from the SCS paint jobs (academy),
# parts from the cab variants of truck.pit (exclusive = cab_c hi-rise sleeper, standard = cab_b mid-roof sleeper)
# + sleeper length in m: 76" hi-rise, 52" mid-roof (the sleeper parts also contain the rear cab roof, so not measured)
CABS = {"exclusive": ("0x2048", 1.93, "cab_base+sleeper_c+gls_c"), "standard": ("0x4096", 1.32, "cab_base+sleeper_b+gls_b")}
DAY_CAB = "duty"
MASKS = "vehicle/truck/upgrade/paintjob/%s/phoenix" % MODEL
# "Phoenix Blast": SCS Winter Blast (xmmxx, colour mask in the alternate UV set) baked in WB_COLORS into an
# airbrush texture with the Phoenix logo on top (same spots). The colours are fixed in this variant.
WB_SRC = "vehicle/truck/upgrade/paintjob/%s/xmmxx" % MODEL
WB_MASKS = "vehicle/truck/upgrade/paintjob/%s/phoenix_wb" % MODEL
WB_SLOTS = {"exclusive": "0x2048", "standard": "0x4096", "duty": "0x6144"}
# colours (sRGB 0-255) of the three Winter Blast areas: yellow cab front, orange leaves, black sleeper
WB_COLORS = {"front": (240, 190, 20), "pattern": (230, 115, 10), "sleeper": (12, 12, 12)}
SETTINGS = [
    '\tname: "Phoenix Trucking"', "\tprice: 4500", "\tunlock: 0",
    "\tbase_color: (0.880000, 0.880000, 0.870000)", "\tbase_color_locked: false",
    "\tflake_clearcoat_rolloff: 4.000000", "\tflake_color: (1.000000, 1.000000, 1.000000)", "\tflake_color_locked: false",
    "\tflake_density: 0.700000", "\tflake_shininess: 40.000000", "\tflake_uvscale: 20.000000",
    "\tflip_color: (0.700000, 0.720000, 0.750000)", "\tflip_color_locked: false", "\tflip_strength: 0.600000", "\tflipflake: true",
    '\ticon: "paintjob/academy_truck"', '\tpart_type: "factory"', ""]


def wr(rel, text):
    p = os.path.join(MOD, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)


ap = argparse.ArgumentParser()
ap.add_argument("--game", default=r"C:\ATSExtract")
ap.add_argument("--logo", default=os.path.join(ROOT, "vnl_electric", "assets", "logo.jpg"))
ap.add_argument("--conv", default=r"C:\ATSExtract\conversion_tools")
ap.add_argument("--scs-dir", default=r"D:\SteamLibrary\steamapps\common\American Truck Simulator", help="ATS install dir (icon source)")
ap.add_argument("--extractor", default=os.path.join(os.environ.get("TEMP", ""), "skzk", "extractor.exe"))
o = ap.parse_args()
MOD = os.path.join(HERE, "mod")
PROJ = os.path.join(HERE, "project")
shutil.rmtree(MOD, ignore_errors=True); shutil.rmtree(PROJ, ignore_errors=True)

# 1. logo masks (source .dds + text .tobj) -> compiled with the SCS conversion tools (raw files show pink in game)
cabs = ",".join("%s:%s:%s:%s" % (c, s, m, parts) for c, (s, m, parts) in CABS.items())
subprocess.run([sys.executable, os.path.join(TOOLS, "make_paintjob.py"), PROJ, "--game", o.game, "--logo", o.logo,
                "--truck", MODEL, "--model", "truck", "--cabs", cabs, "--out", MASKS, "--back-y", "0.72"], check=True)

# 1b. Phoenix Blast: logo masks in the alternate UV set (_UV2), composited over the baked Winter Blast pattern
sys.path.insert(0, TOOLS)
import make_paintjob as mpj
from PIL import Image
subprocess.run([sys.executable, os.path.join(TOOLS, "make_paintjob.py"), PROJ, "--game", o.game, "--logo", o.logo,
                "--truck", MODEL, "--model", "truck", "--cabs", cabs, "--out", WB_MASKS, "--back-y", "0.72"],
               check=True, env=dict(os.environ, PJ_UV="_UV2"))
for cab, slot in WB_SLOTS.items():
    raw = bytearray(open(os.path.join(o.game, *WB_SRC.split("/"), "pjm_at_%s_size_2048x2048.dds" % slot), "rb").read())
    if raw[84:88] == b"DX10" and int.from_bytes(raw[128:132], "little") == 78:
        raw[128:132] = (77).to_bytes(4, "little")             # BC3 sRGB -> BC3 (same data, Pillow only reads 77)
    m = Image.open(io.BytesIO(bytes(raw))).convert("RGB")
    import numpy as np
    a = np.asarray(m, dtype=np.float32) / 255.0
    # Winter Blast areas: background = sleeper, B = leaf pattern, G (inside B) = cab front; R is unused
    G, B = a[..., 1:2], a[..., 2:3]
    rgb = np.array(WB_COLORS["sleeper"]) * (1 - B) + B * (np.array(WB_COLORS["pattern"]) * (1 - G) + np.array(WB_COLORS["front"]) * G)
    img = Image.fromarray(np.dstack([rgb, np.full(rgb.shape[:2], 255.0)]).astype(np.uint8), "RGBA")
    name = "pjm_at_%s_size_2048x2048" % slot
    od = os.path.join(PROJ, *WB_MASKS.split("/")); os.makedirs(od, exist_ok=True)
    lp = os.path.join(od, name + ".dds")
    if os.path.isfile(lp):                                    # logo layer from make_paintjob (sleeper cabs)
        hdr = open(lp, "rb").read()
        w_, h_ = int.from_bytes(hdr[16:20], "little"), int.from_bytes(hdr[12:16], "little")
        b_, g_, r_, al = Image.frombytes("RGBA", (w_, h_), hdr[128:128 + w_ * h_ * 4]).split()
        img.alpha_composite(Image.merge("RGBA", (r_, g_, b_, al)))
    mpj.save_dds(img, lp)
    open(os.path.join(od, name + ".tobj"), "w").write("map 2d %s.dds\naddr clamp_to_edge clamp_to_edge\n" % name)
    print("Phoenix Blast %s: Winter Blast pattern + %s" % (cab, "logo" if cab in CABS else "no logo (day cab)"))

# 1c. shop icon: the Winter Blast icon (base_vehicle.scs material/ui/accessory/xmmxxi) recoloured by brightness:
#     dark -> sleeper black, mid -> pattern orange, bright -> front yellow
src_icon = os.path.join(o.game, "material", "ui", "accessory", "xmmxxi.dds")
if not os.path.isfile(src_icon):
    subprocess.run([o.extractor, os.path.join(o.scs_dir, "base_vehicle.scs"), "-f", "/material/ui/accessory/xmmxxi.*", "-d", o.game],
                   check=True, capture_output=True)
ib = open(src_icon, "rb").read()
iw, ih = int.from_bytes(ib[16:20], "little"), int.from_bytes(ib[12:16], "little")
off = 148 if ib[84:88] == b"DX10" else 128
ia = np.frombuffer(ib[off:off + iw * ih * 4], np.uint8).reshape(ih, iw, 4)[..., [2, 1, 0, 3]].astype(np.float32)
lum = (ia[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32) / 255)[..., None]
k = np.clip(lum / 0.45, 0, 1); k2 = np.clip((lum - 0.45) / 0.4, 0, 1)
rgb = np.array(WB_COLORS["sleeper"]) * (1 - k) + np.array(WB_COLORS["pattern"]) * k
rgb = rgb * (1 - k2) + np.array(WB_COLORS["front"]) * k2
icon_img = Image.fromarray(np.dstack([rgb, ia[..., 3]]).clip(0, 255).astype(np.uint8), "RGBA")
idir = os.path.join(PROJ, "material", "ui", "accessory"); os.makedirs(idir, exist_ok=True)
mpj.save_dds(icon_img, os.path.join(idir, "phoenix_blast.dds"))
open(os.path.join(idir, "phoenix_blast.tobj"), "w").write("map 2d phoenix_blast.dds\naddr clamp_to_edge clamp_to_edge\nnomips\n")
icon_img.save(os.path.join(HERE, "phoenix_blast_icon_preview.png"))

link = os.path.join(o.conv, "rsrc", "kw_phx")
if not os.path.exists(link):
    subprocess.run(["cmd", "/c", "mklink", "/J", link, PROJ], check=True, capture_output=True)
tools = os.path.join(o.conv, "bin", "win_x64", "tools")
shutil.rmtree(os.path.join(o.conv, "rsrc", "rsrc", "kw_phx"), ignore_errors=True)
subprocess.run([os.path.join(tools, "resconvert.exe"), "-update", "-root", "rsrc/kw_phx"], cwd=tools, capture_output=True)
log = open(os.path.join(tools, "mass_convert.log"), encoding="utf-8", errors="replace").read()
if "*** ERROR" in log:
    sys.exit("conversion failed:\n" + "\n".join(l for l in log.splitlines() if "ERROR" in l))
shutil.copytree(os.path.join(o.conv, "rsrc", "rsrc", "kw_phx", "@cache"), MOD)

# 2. definitions
pdir = "def/vehicle/truck/%s/paint_job" % TRUCK
wr(pdir + "/phoenix_settings.sui", "\n".join(SETTINGS))
for cab, (slot, _, _) in CABS.items():
    wr("%s/phoenix_%s.sii" % (pdir, cab),
       "SiiNunit\n{\naccessory_paint_job_data : phx_%s.%s.paint_job\n{\n@include \"phoenix_settings.sui\"\n\tairbrush: true\n"
       "\tpaint_job_mask: \"/%s/pjm_at_%s_size_2048x2048.tobj\"\n\tsuitable_for[]: \"%s.%s.cabin\"\n}\n}\n" % (cab[:8], TRUCK, MASKS, slot, cab, TRUCK))
wr(pdir + "/phoenix_day.sii",
   "SiiNunit\n{\naccessory_paint_job_data : phx_day.%s.paint_job\n{\n@include \"phoenix_settings.sui\"\n\tsuitable_for[]: \"%s.%s.cabin\"\n}\n}\n" % (TRUCK, DAY_CAB, TRUCK))
wbset = [l for l in SETTINGS if not l.strip().startswith(("name:", "base_color:", "icon:"))]
wbset += ['\tname: "Phoenix Blast"', "\tbase_color: (0.003, 0.003, 0.003)", '\ticon: "phoenix_blast"', "\talternate_uvset: true", ""]
wr(pdir + "/phoenix_wb_settings.sui", "\n".join(wbset))
wr("material/ui/accessory/phoenix_blast.mat", "effect : \"ui.rfx\" {\n\ttexture : \"texture\" {\n\t\tsource : \"phoenix_blast.tobj\"\n\t\tu_address : clamp\n\t\tv_address : clamp\n\t\tmip_filter : none\n\t}\n}\n")
for cab, slot in WB_SLOTS.items():
    wr("%s/phoenix_wb_%s.sii" % (pdir, cab),
       "SiiNunit\n{\naccessory_paint_job_data : pwb_%s.%s.paint_job\n{\n@include \"phoenix_wb_settings.sui\"\n\tairbrush: true\n"
       "\tpaint_job_mask: \"/%s/pjm_at_%s_size_2048x2048.tobj\"\n\tsuitable_for[]: \"%s.%s.cabin\"\n}\n}\n" % (cab[:8], TRUCK, WB_MASKS, slot, cab, TRUCK))

wr("manifest.sii", "SiiNunit\n{\nmod_package : .package_name\n{\n\tpackage_version: \"1.0\"\n\tdisplay_name: \"Phoenix Trucking - Kenworth T680 (2014)\"\n"
   "\tauthor: \"Erich Barnstedt\"\n\tcategory[]: \"paint_job\"\n\tdescription_file: \"description.txt\"\n\tcompatible_versions[]: \"1.61.*\"\n}\n}\n")
wr("description.txt", "\"Phoenix Trucking\" paint job for the Kenworth T680 (2014): white metallic with the Phoenix Trucking logo\n"
   "on the sleeper sides and back (hi-rise and mid-roof sleepers; plain white on the day cab). Requires the Kenworth T680 DLC.\n"
   "Also \"Phoenix Blast\": the Winter Blast pattern in yellow, orange and black with the same logo.\n\n"
   "Source: https://github.com/barnstee/ATS-Mods\n")

# 3. pack + install
scs = os.path.join(ROOT, "kenworth_phoenix.scs")
with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fns in os.walk(MOD):
        for fn in fns:
            f = os.path.join(dp, fn)
            z.write(f, os.path.relpath(f, MOD).replace(os.sep, "/"))
home = os.path.expanduser("~")
for d in (os.path.join(home, "OneDrive - Microsoft", "Documents", "American Truck Simulator", "mod"),
          os.path.join(home, "Documents", "American Truck Simulator", "mod")):
    if os.path.isdir(d):
        try:
            shutil.copy2(scs, d); print("Installed", scs, "->", d)
        except PermissionError:
            print("WARNING: mod file is locked - close ATS and run again")
        break
