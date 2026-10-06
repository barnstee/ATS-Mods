"""Builds all custom models of the VNL Electric into <mod>/vehicle and <mod>/automat.

  * VNL frames without the small step ladder in front of the rear fenders
  * per-frame VNR battery packs + e-motor unit (Standard / ER / XR) for the tank slot:
    front edge just behind the driver door steps, XR filling the space up to the rear wheels,
    ER = 90 %, Standard = XR / 1.2
Needs tools/bin/converter_pix.exe and SCS conversion tools (--conv).
"""
import argparse, json, os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pim_tool import load, Piece, bounds, hf, HEX

FRAMES = ["s42_185_4x2", "s42_194_6x4", "s42_220_6x2m", "s74_211_4x2", "s74_220_6x4", "s74_246_6x2m",
          "dc_155_4x2", "dc_164_6x4", "dc_190_6x2m"]
BAT_FRONT = -1.25      # chassis z where the packs start (driver door steps end at -1.31)
WHEEL_GAP = 0.55       # clearance from first rear axle centre to the pack end
SRC_FRONT, SRC_BACK = -1.31, 0.93     # VNR pack span in the VNR frame
SRC_BOX = [-1.25, 0.2, -1.35, 1.25, 1.0, 0.97]
TIERS = {"std": 1 / 1.2, "er": 0.9, "xr": 1.0}
TIER_OVERRIDE = {"s74_220_6x4": {"std": 0.9, "er": 0.95, "xr": 1.0}}   # 6x4 Standard = same pack as the 6x2 ER (946 kWh)


def locs(pim):
    _, bl = load(pim)
    out = {}
    for k, b in bl:
        if k == "Locator":
            t = "\n".join(b)
            out[re.search(r"Name:\s*\"([^\"]+)\"", t).group(1)] = [hf(h) for h in HEX.findall(re.search(r"Position:.*", t).group(0))]
    return out


def steps(pim):
    _, bl = load(pim)
    mats = [re.search(r"Alias:\s*\"([^\"]+)\"", "\n".join(b)).group(1) for k, b in bl if k == "Material"]
    zs = []
    for k, b in bl:
        if k == "Piece":
            p = Piece(b)
            if "step_c" in mats[p.material]:
                zs += [v[2] for v in p.pos if v[0] < -0.4]
    return (min(zs), max(zs)) if zs else None


def run(*a):
    subprocess.run([str(x) for x in a], check=True, cwd=HERE)


LEFT_PACK_BOX = [-1.25, 0.2, -1.35, -0.34, 1.0, 0.97]   # left VNR pack -> copied between the rails as 3rd pack
MOTOR_BOX = [-0.35, 0.35, -0.45, 0.33, 0.95, 0.35]     # VNR motor/inverter unit -> e-axle drive unit
MOTOR_SCALE = 1.2                                      # e-axle drive unit almost fills the frame
MOTOR_C = (0.66, -0.045)                               # its centre (y, z) in the VNR frame
EAXLE_Y, EAXLE_AHEAD = 0.56, 0.45                       # drive unit centre height / distance ahead of axle
CENTER_REAR_GAP = 0.85                                 # 3rd pack ends this far ahead of the first rear axle


TWIN_MOTOR = ()               # e-axle unit on every rear axle


def powered_axles(game, frame, L):
    import glob
    if frame in TWIN_MOTOR:
        return sorted({round(v[2], 3) for n, v in L.items() if n.startswith("wheel_r")})
    for f in glob.glob(os.path.join(game, "def", "vehicle", "truck", "volvo.vnl2025", "chassis", "*.sii")):
        t = open(f, encoding="utf-8-sig").read()
        if "/chassis/%s.pmd" % frame in t:
            pw = [x == "true" for x in re.findall(r"powered_axle\[\]\s*:\s*(\w+)", t)]
            zs = sorted({round(v[2], 3) for n, v in L.items() if n.startswith("wheel_")})
            return [z for z, on in zip(zs, pw) if on]
    return [max(v[2] for n, v in L.items() if n.startswith("wheel_r"))]


def compose(vnr, out, L, length, rear, axles):
    tank_x, tank_y, tank_z = L["tank"]
    zc = (SRC_BOX[2] + SRC_BOX[5]) / 2
    def place(len_m):
        s = len_m / (SRC_BACK - SRC_FRONT)
        return s, (BAT_FRONT - tank_z) - (zc + (SRC_FRONT - zc) * s)
    s, dz = place(length)
    ops = [{"box": SRC_BOX, "offset": [0, -tank_y, dz], "scale_z": s}]
    cl = min(length, rear - CENTER_REAR_GAP - BAT_FRONT)
    cs, cdz = place(cl)
    ops.append({"box": LEFT_PACK_BOX, "offset": [0.75, -tank_y, cdz], "scale_z": cs})
    for az in axles:
        ops.append({"box": MOTOR_BOX, "offset": [0, EAXLE_Y - MOTOR_C[0] - tank_y, (az - EAXLE_AHEAD - MOTOR_C[1]) - tank_z], "scale_z": 1.0, "scale": MOTOR_SCALE})
    oj = os.path.join(os.path.dirname(HERE), "blender", "ops", os.path.basename(out)[:-4] + ".json")
    os.makedirs(os.path.dirname(oj), exist_ok=True)
    json.dump(ops, open(oj, "w"))
    run(sys.executable, os.path.join(HERE, "pim_compose.py"), vnr, out, oj)
    return cl

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"C:\ATSExtract"); ap.add_argument("--conv", default=r"C:\ATSExtract\conversion_tools")
    o = ap.parse_args()
    root = os.path.dirname(HERE)
    src = os.path.join(root, "blender", "src"); proj = os.path.join(root, "blender", "project")
    shutil.rmtree(proj, ignore_errors=True)
    cpx = os.path.join(HERE, "bin", "converter_pix.exe")
    run(cpx, "-b", o.game, "-e", src, "-m", "/vehicle/truck/volvo_vnr_e/chassis/chs_4x2")
    vnr = os.path.join(src, "vehicle", "truck", "volvo_vnr_e", "chassis", "chs_4x2.pim")
    info = {}
    for f in FRAMES:
        run(cpx, "-b", o.game, "-e", src, "-m", "/vehicle/truck/volvo_vnl2025/chassis/" + f)
        pim = os.path.join(src, "vehicle", "truck", "volvo_vnl2025", "chassis", f + ".pim")
        L = locs(pim)
        tank_z = L["tank"][2]
        rear = min(v[2] for n, v in L.items() if n.startswith("wheel_r"))
        space = rear - WHEEL_GAP - BAT_FRONT
        axles = powered_axles(o.game, f, L)
        st = steps(pim)
        if st:
            run(sys.executable, os.path.join(HERE, "pim_remove.py"), pim, os.path.join(proj, "vehicle", "truck", "volvo_vnl_e", "chassis", f + ".pim"),
                "--box", -1.0, 0.2, st[0] - 0.25, -0.425, 1.0, st[1] + 0.25)
        tiers, centers = {}, {}
        for tier, k in TIER_OVERRIDE.get(f, TIERS).items():
            length = space * k
            out = os.path.join(proj, "vehicle", "truck", "volvo_vnl_e", "accessory", "tank", "bat_%s_%s.pim" % (f, tier))
            cl = compose(vnr, out, L, length, rear, axles)
            tiers[tier] = round(length, 2)
            centers[tier] = round(cl, 2)
        info[f] = {"ladder_removed": bool(st), "pack_length_m": tiers, "center_length_m": centers, "driven_axles": len(axles)}
        print("%-14s space %.2f m  std %.2f  er %.2f  xr %.2f  ladder %s  e-axles at z %s" % (f, space, tiers["std"], tiers["er"], tiers["xr"], "removed" if st else "-", axles))
    run(sys.executable, os.path.join(HERE, "make_paintjob.py"), proj, "--game", o.game)
    link = os.path.join(o.conv, "rsrc", "vnl_e")
    if not os.path.exists(link):
        subprocess.run(["cmd", "/c", "mklink", "/J", link, proj], check=True, capture_output=True)
    tools = os.path.join(o.conv, "bin", "win_x64", "tools")
    cache = os.path.join(o.conv, "rsrc", "rsrc", "vnl_e", "@cache")
    shutil.rmtree(os.path.join(o.conv, "rsrc", "rsrc", "vnl_e"), ignore_errors=True)
    subprocess.run([os.path.join(tools, "resconvert.exe"), "-update", "-root", "rsrc/vnl_e"], cwd=tools, capture_output=True)
    log = open(os.path.join(tools, "mass_convert.log"), encoding="utf-8", errors="replace").read()
    if "*** ERROR" in log:
        sys.exit("conversion failed:\n" + "\n".join(l for l in log.splitlines() if "ERROR" in l))
    for d in ("vehicle", "automat"):
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
        shutil.copytree(os.path.join(cache, d), os.path.join(root, d))
    json.dump(info, open(os.path.join(root, "vehicle", "frames.json"), "w"), indent=1)
    print("models copied to", os.path.join(root, "vehicle"))


if __name__ == "__main__":
    main()
