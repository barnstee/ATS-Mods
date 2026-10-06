"""Replace the cloned VNL diesel tank accessories with the VNR Electric battery packs + e-motor unit.

Models are built by build_battery_models.ps1 into <out>/vehicle/truck/volvo_vnl_e/accessory/tank/
(materials in <out>/automat/). XR frames get 20% longer packs.
"""
import os, re, shutil

BATTERY_DIR = ("vehicle", "truck", "volvo_vnl_e", "accessory", "tank")


def _unit(token, target, label, model, suit, icon):
    body = ["accessory_addon_tank_data : %s.%s.tank" % (token, target), "{",
            "\tname: \"VNR Electric battery packs (%s)\"" % label, "\tprice: 0", "\tunlock: 0"]
    if icon:
        body.append("\ticon: \"%s\"" % icon)
    body += ["\tpart_type: factory", "", "\texterior_model: \"/%s/%s.pmd\"" % ("/".join(BATTERY_DIR), model), ""]
    body += ["\tsuitable_for[]: \"%s.%s.chassis\"" % (s, target) for s in suit]
    return "SiiNunit\n{\n" + "\n".join(body) + "\n}\n}\n"


def batteries(tgt, out, target, rd, wr, log):
    if not os.path.isfile(os.path.join(out, *BATTERY_DIR, "vnr_battery_std.pmd")):
        log("[BAT]  WARNING battery models missing - run tools\\build_battery_models.ps1; diesel tanks kept")
        return
    tdir = os.path.join(tgt, "accessory", "tank")
    cdir = os.path.join(tgt, "chassis")
    n = 0
    for f in sorted(x for x in os.listdir(tdir) if x.endswith(".sii") and not x.startswith("xr_")):
        p = os.path.join(tdir, f)
        t = rd(p)
        unit = re.search(r"accessory_addon_tank_data\s*:\s*([a-z0-9_]+)\." + re.escape(target) + r"\.tank", t)
        if not unit:
            continue
        size = "long" if "long" in f else "std"
        label = "long" if size == "long" else "standard"
        toks = re.findall(r"suitable_for\[\]\s*:\s*\"([a-z0-9_]+)\." + re.escape(target) + r"\.chassis\"", t)
        std = [v for tok in toks for v in (tok, ("er" + tok)[:12])]
        xr = [("xr" + tok)[:12] for tok in toks]
        icon = re.search(r"icon\s*:\s*\"([^\"]+)\"", t)
        icon = icon.group(1) if icon else None
        wr(p, _unit(unit.group(1), target, label, "vnr_battery_" + size, std, icon))
        if os.path.isfile(os.path.join(out, *BATTERY_DIR, "vnr_battery_%s_xr.pmd" % size)):
            wr(os.path.join(tdir, "xr_" + f), _unit(("x" + unit.group(1))[:12], target, label + " XR", "vnr_battery_%s_xr" % size, xr, icon))
            for c in (x for x in os.listdir(cdir) if x.startswith("xr_")):
                cp = os.path.join(cdir, c)
                ct = rd(cp)
                ct2 = ct.replace("/accessory/tank/" + f + "\"", "/accessory/tank/xr_" + f + "\"")
                if ct2 != ct:
                    wr(cp, ct2)
        n += 1
    log("[BAT]  replaced %d diesel tank accessories with VNR battery packs + e-motor unit (+ XR long packs)" % n)


def pack_models(z, out):
    for top, exts in (("vehicle", (".pmd", ".pmg", ".pmc", ".tobj", ".dds")), ("automat", (".mat",)), ("def", (".soundref",))):
        for dp, _, fns in os.walk(os.path.join(out, top)):
            for fn in fns:
                if fn.endswith(exts):
                    f = os.path.join(dp, fn)
                    z.write(f, os.path.relpath(f, out).replace(os.sep, "/"))


def install(scs):
    home = os.path.expanduser("~")
    for mod in (os.path.join(home, "OneDrive - Microsoft", "Documents", "American Truck Simulator", "mod"),
                os.path.join(home, "Documents", "American Truck Simulator", "mod")):
        if os.path.isdir(mod):
            try:
                shutil.copy2(scs, mod)
            except PermissionError:
                print("WARNING: mod file is locked - close ATS and copy %s to %s" % (scs, mod))
                return None
            return mod


def no_exhaust(tgt, out, target, rd, wr, log):
    """EVs have no exhaust: drop the exhaust accessories and every reference to them."""
    shutil.rmtree(os.path.join(tgt, "accessory", "exhaust"), ignore_errors=True)
    ref = re.compile(r"^[ \t]*defaults\[\][ \t]*:[ \t]*\"/def/vehicle/truck/" + re.escape(target) + r"/accessory/exhaust/[^\"]*\"[ \t]*\r?\n", re.M)
    n = 0
    for dp, _, fns in os.walk(os.path.join(out, "def")):
        for fn in fns:
            if not fn.endswith((".sii", ".sui")):
                continue
            p = os.path.join(dp, fn)
            t = rd(p)
            t2 = ref.sub("", t)
            # dealer showcase: accessories[]: .exhaust + its vehicle_addon_accessory block
            t2 = re.sub(r"^[ \t]*accessories\[\][ \t]*:[ \t]*\.exhaust[ \t]*\r?\n", "", t2, flags=re.M)
            t2 = re.sub(r"^[ \t]*vehicle_addon_accessory[ \t]*:[ \t]*\.exhaust[ \t]*\{[^}]*\}[ \t]*\r?\n", "", t2, flags=re.M)
            if t2 != t:
                wr(p, t2); n += 1
    log("[EV]   removed exhaust accessories (%d files cleaned)" % n)


def extend_suitable(tgt, target, rd, wr, log):
    """Parts limited to a frame must also fit that frame's ER/XR versions (tank slot handled by batteries())."""
    rx = re.compile(r"^([ \t]*suitable_for\[\][ \t]*:[ \t]*\")([a-z0-9_]+)(\." + re.escape(target) + r"\.chassis\"[ \t]*)$", re.M)
    n = 0
    for dp, _, fns in os.walk(tgt):
        if os.path.basename(dp) == "tank" or os.path.basename(dp) == "chassis":
            continue
        for fn in fns:
            if not fn.endswith(".sii"):
                continue
            p = os.path.join(dp, fn)
            t = rd(p)
            if not rx.search(t):
                continue
            have = set(m.group(2) for m in rx.finditer(t))
            def add(m):
                extra = [v for v in (("er" + m.group(2))[:12], ("xr" + m.group(2))[:12]) if v not in have]
                have.update(extra)
                return m.group(0) + "".join("\n" + m.group(1) + v + m.group(3) for v in extra)
            wr(p, rx.sub(add, t)); n += 1
    log("[RNG]  %d frame-limited parts now also fit ER/XR frames" % n)


TIER_NAME = {"std": "Standard", "er": "ER", "xr": "XR"}
STD_KWH = {}                               # 74" sleeper 6x4: Standard pack
NAME_FIX = {"s74_220_6x4": (("@@chassis_6x4_220in@@", "6x4 246in"),)}
KWH_PER_M = 126.0   # real VNR Electric: 565 kWh in 2 x 2.24 m packs; applied to the 2 side packs + centre pack


def _kg_per_kwh():
    import __main__
    return getattr(__main__, "KG_PER_KWH", 5.5)


def _add_mass(t, kg_front, kg_rear):
    it = iter((kg_front, kg_rear))
    def sub(m):
        try:
            v = float(m.group(2)) + next(it)
        except StopIteration:
            return m.group(0)
        return "%s%.0f\t# %.0flb" % (m.group(1), v, v * 2.20462)
    return re.sub(r"^(\s*kerb_weight\s*(?:\[\d*\])?\s*:\s*)([0-9.]+).*$", sub, t, flags=re.M)


def ev_frames(tgt, out, target, rd, wr, log):
    """Per-frame battery packs (from build_models.py) + ladder-free frame models."""
    import json
    fj = os.path.join(out, "vehicle", "frames.json")
    if not os.path.isfile(fj):
        log("[BAT]  WARNING vehicle/frames.json missing - run tools\\build_models.py; diesel tanks kept")
        return
    info = json.load(open(fj))
    tdir = os.path.join(tgt, "accessory", "tank")
    cdir = os.path.join(tgt, "chassis")
    shutil.rmtree(tdir, ignore_errors=True)
    os.makedirs(tdir)
    tank_ref = re.compile(r"^[ \t]*defaults\[\][ \t]*:[ \t]*\"/def/vehicle/truck/" + re.escape(target) + r"/accessory/tank/[^\"]*\"[ \t]*\r?\n", re.M)
    for dp, _, fns in os.walk(os.path.join(out, "def")):
        for fn in fns:
            if fn.endswith(".sii"):
                p = os.path.join(dp, fn); t = rd(p); t2 = tank_ref.sub("", t)
                if t2 != t:
                    wr(p, t2)
    tank_of = {}
    n = 0
    for f in sorted(x for x in os.listdir(cdir) if x.endswith(".sii")):
        p = os.path.join(cdir, f)
        t = rd(p)
        m = re.search(r"model:\s*\"/vehicle/truck/[a-z0-9_]+/chassis/([a-z0-9_]+)\.pmd\"", t)
        u = re.search(r"accessory_chassis_data\s*:\s*([a-z0-9_]+)\." + re.escape(target) + r"\.chassis", t)
        if not m or not u or m.group(1) not in info:
            continue
        frame = m.group(1)
        tier = "er" if f.startswith("er_") else "xr" if f.startswith("xr_") else "std"
        kwh = re.search(r"^\s*tank_size\s*:\s*([0-9.]+)", t, re.M)
        old_kwh = float(kwh.group(1)) if kwh else 0
        side, center = info[frame]["pack_length_m"][tier], info[frame].get("center_length_m", {}).get(tier, 0)
        kwh = round(KWH_PER_M * (2 * side + center))
        if frame in STD_KWH:   # fixed Standard capacity, ER/XR keep their size ratio
            pl, cl = info[frame]["pack_length_m"], info[frame].get("center_length_m", {})
            kwh = round(kwh * STD_KWH[frame] / (KWH_PER_M * (2 * pl["std"] + cl.get("std", 0))))
        t = re.sub(r"^(\s*tank_size\s*:\s*)[0-9.]+", lambda q: q.group(1) + str(kwh), t, count=1, flags=re.M)
        t = _add_mass(t, (kwh - old_kwh) * _kg_per_kwh() * 0.4, (kwh - old_kwh) * _kg_per_kwh() * 0.6)
        if info[frame]["ladder_removed"]:
            t = t.replace("/vehicle/truck/volvo_vnl2025/chassis/%s.pmd" % frame, "/vehicle/truck/volvo_vnl_e/chassis/%s.pmd" % frame)
            t = t.replace("/vehicle/truck/volvo_vnl2025/chassis/%s.pmc" % frame, "/vehicle/truck/volvo_vnl_e/chassis/%s.pmc" % frame)
        t = re.sub(r"(^\s*name\s*:\s*\"[^\"]*?)(?: (?:ER|XR|Standard))? (\d+(?:\.\d+)? kWh\")", lambda q: "%s %s %d kWh\"" % (q.group(1), TIER_NAME[tier], kwh), t, count=1, flags=re.M)
        for a, b in NAME_FIX.get(frame, ()):
            t = t.replace(a, b)
        tf = "bat_%s_%s.sii" % (frame, tier)
        token = ({"std": "b", "er": "e", "xr": "x"}[tier] + frame.lstrip("s"))[:12]
        wr(os.path.join(tdir, tf), "SiiNunit\n{\naccessory_addon_tank_data : %s.%s.tank\n{\n" % (token, target)
           + "\tname: \"VNR Electric battery packs - %s %.0f kWh\"\n\tprice: 0\n\tunlock: 0\n" % (TIER_NAME[tier], kwh)
           + "\ticon: \"truck/volvo_vnl2025/accessory/tank/long_275_aluminum_sideskirt\"\n\tpart_type: factory\n\n"
           + "\texterior_model: \"/vehicle/truck/volvo_vnl_e/accessory/tank/bat_%s_%s.pmd\"\n\n" % (frame, tier)
           + "\tfuel_tank_size: %d\t# battery kWh (must match the frame)\n\tadblue_tank_size: 0\n\n" % kwh
           + "\tsuitable_for[]: \"%s.%s.chassis\"\n}\n}\n" % (u.group(1), target))
        ref = "\tdefaults[]: \"/def/vehicle/truck/%s/accessory/tank/%s\"\n" % (target, tf)
        t = re.sub(r"^([ \t]*defaults\[\])", lambda q: ref + q.group(1), t, count=1, flags=re.M) if re.search(r"^[ \t]*defaults\[\]", t, re.M) else t
        wr(p, t)
        tank_of["/def/vehicle/truck/%s/chassis/%s" % (target, f)] = "/def/vehicle/truck/%s/accessory/tank/%s" % (target, tf)
        n += 1
    ddir = os.path.join(out, "def", "vehicle", "truck_dealer")
    for dp, _, fns in os.walk(ddir):
        for fn in fns:
            p = os.path.join(dp, fn); t = rd(p)
            c = re.search(r"\.chassis\s*\{\s*data_path:\s*\"([^\"]+)\"", t)
            if c and c.group(1) in tank_of:
                t2 = re.sub(r"(\.tank\s*\{\s*data_path:\s*\")[^\"]+(\")", lambda q: q.group(1) + tank_of[c.group(1)] + q.group(2), t)
                if t2 != t:
                    wr(p, t2)
    log("[BAT]  %d frames: own VNR battery packs (Standard/ER/XR sized to the frame), step ladder removed" % n)


EAXLE_KW = 460


def ev_engines(tgt, target, rd, wr, log):
    """One motor option per layout: 1 Volvo e-axle (460 kW) or 2 on 6x4 frames (920 kW)."""
    edir = os.path.join(tgt, "engine"); cdir = os.path.join(tgt, "chassis")
    tpl_name = sorted(x for x in os.listdir(edir) if x.endswith(".sii") and not x.startswith(("vnr_dm_", "eaxle")))[0]
    tpl = rd(os.path.join(edir, tpl_name))
    groups = {1: [], 2: []}
    for f in sorted(x for x in os.listdir(cdir) if x.endswith(".sii")):
        u = re.search(r"accessory_chassis_data\s*:\s*([a-z0-9_]+)\." + re.escape(target) + r"\.chassis", rd(os.path.join(cdir, f)))
        if u:
            groups[2 if "6x4" in f else 1].append((f, u.group(1)))
    rpm_base = float(re.search(r"torque_curve\[\]\s*:\s*\(\s*([0-9.]+)\s*,\s*1(?:\.0*)?\s*\)\s*$", "\n".join(l for l in tpl.splitlines() if "torque_curve" in l and not l.strip().startswith("torque_curve[]: (0,")), re.M).group(1))
    for n, frames in groups.items():
        kw = EAXLE_KW * n
        nm = kw * 1000 / (rpm_base * 3.14159265 / 30)
        t = re.sub(r"accessory_engine_data\s*:\s*[a-z0-9_]+\.", "accessory_engine_data : eaxle%d." % n, tpl, count=1)
        t = re.sub(r"^(\s*name\s*:\s*)\"[^\"]*\"", lambda q: q.group(1) + "\"Volvo %se-axle %d kW\"" % ("dual " if n == 2 else "", kw), t, count=1, flags=re.M)
        rpm_info = re.findall(r"^\s*info\[\]\s*:\s*(\"[^\"]*@@rpm@@[^\"]*\")", t, flags=re.M)
        t = re.sub(r"^\s*info\[\]\s*:.*\n", "", t, flags=re.M)
        t = re.sub(r"^(\s*part_type\s*:)", "\tinfo[]: \"%d @@hp@@ (%d@@kw@@)\"\n\tinfo[]: \"%d @@lb_ft@@ (%d@@nm@@)\"\n\tinfo[]: %s\n\\1" % (round(kw * 1.341), kw, round(nm * 0.7376), round(nm), rpm_info[0] if rpm_info else "\"600 @@rpm@@\""), t, count=1, flags=re.M)
        t = re.sub(r"^(\s*torque\s*:\s*)[0-9.]+", lambda q: q.group(1) + "%d" % round(nm), t, count=1, flags=re.M)
        t = re.sub(r"^(\s*price\s*:\s*)[0-9]+", lambda q: q.group(1) + str(30000 * n), t, count=1, flags=re.M)
        t = re.sub(r"^\s*suitable_for\[\].*\n", "", t, flags=re.M)
        t = re.sub(r"^\s*overrides\[\]\s*:.*badge.*\n", "", t, flags=re.M)   # VNR electric badge sits crooked on the VNL fender
        t = re.sub(r"(\n\})(\s*\}\s*)$", "".join("\n\tsuitable_for[]: \"%s.%s.chassis\"" % (u, target) for _, u in frames) + r"\1\2", t)
        wr(os.path.join(edir, "eaxle_%d.sii" % n), t)
    for x in os.listdir(edir):
        if x.endswith(".sii") and not x.startswith("eaxle"):
            os.remove(os.path.join(edir, x))
    eng_ref = re.compile(r"/def/vehicle/truck/" + re.escape(target) + r"/engine/(?!eaxle)[a-z0-9_]+\.sii")
    for dp, _, fns in os.walk(os.path.dirname(os.path.dirname(os.path.dirname(tgt)))):
        for fn in fns:
            if fn.endswith(".sii"):
                p = os.path.join(dp, fn); t = rd(p); t2 = eng_ref.sub("/def/vehicle/truck/%s/engine/eaxle_1.sii" % target, t)
                if t2 != t:
                    wr(p, t2)
    for n, frames in groups.items():
      for f, _ in frames:
        p = os.path.join(cdir, f); t = rd(p)
        t = re.sub(r"^([ \t]*defaults\[\])", lambda q: "\tdefaults[]: \"/def/vehicle/truck/%s/engine/eaxle_%d.sii\"\n" % (target, n) + q.group(1), t, count=1, flags=re.M)
        wr(p, t)
    log("[MOT]  motors: e-axle %d kW on %d frames, dual e-axle %d kW on %d 6x4 frames" % (EAXLE_KW, len(groups[1]), 2 * EAXLE_KW, len(groups[2])))


PJ_CABS = {"74h": "0x0", "74m": "0x2048", "42m": "0x4096"}


def ev_paintjob(tgt, out, target, wr, log):
    """White metallic + logo on sleeper sides/back (airbrush masks from make_paintjob.py); plain white metallic on the day cab."""
    pdir = os.path.join(tgt, "paint_job")
    mdir = "/vehicle/truck/upgrade/paintjob/volvo_vnl_e/vnl_electric"
    wr(os.path.join(pdir, "vnl_electric_settings.sui"), "\n".join([
        "\tname: \"Phoenix Trucking\"", "\tprice: 4500", "\tunlock: 0",
        "\tbase_color: (0.880000, 0.880000, 0.870000)", "\tbase_color_locked: false",
        "\tflake_clearcoat_rolloff: 4.000000", "\tflake_color: (1.000000, 1.000000, 1.000000)", "\tflake_color_locked: false",
        "\tflake_density: 0.700000", "\tflake_shininess: 40.000000", "\tflake_uvscale: 20.000000",
        "\tflip_color: (0.700000, 0.720000, 0.750000)", "\tflip_color_locked: false", "\tflip_strength: 0.600000", "\tflipflake: true",
        "\ticon: \"paintjob/academy_truck\"", "\tpart_type: \"factory\"", ""]))
    n = 0
    for cab, slot in PJ_CABS.items():
        if not os.path.isfile(os.path.join(out, *(mdir.strip("/").split("/")), "pjm_at_%s_size_2048x2048.tobj" % slot)):
            continue
        wr(os.path.join(pdir, "vnl_electric_%s.sii" % cab), "SiiNunit\n{\naccessory_paint_job_data : vnle_%s.%s.paint_job\n{\n@include \"vnl_electric_settings.sui\"\n\tairbrush: true\n\tpaint_job_mask: \"%s/pjm_at_%s_size_2048x2048.tobj\"\n\tsuitable_for[]: \"%s.%s.cabin\"\n}\n}\n" % (cab, target, mdir, slot, cab, target))
        n += 1
    wr(os.path.join(pdir, "vnl_electric_dc.sii"), "SiiNunit\n{\naccessory_paint_job_data : vnle_dc.%s.paint_job\n{\n@include \"vnl_electric_settings.sui\"\n\tsuitable_for[]: \"dc.%s.cabin\"\n}\n}\n" % (target, target))
    log("[PNT]  VNL Electric paint job: white metallic + logo on %d sleeper cabs (plain on day cab)" % n)


def copy_soundrefs(game, donor, tgt, log):
    """Sound configs (.soundref: horn, air horn, interior sticks/warnings) are not .sii - copy them too."""
    src = os.path.join(game, "def", "vehicle", "truck", donor)
    n = 0
    for dp, _, fns in os.walk(src):
        for fn in fns:
            if fn.endswith(".soundref"):
                d = os.path.join(tgt, os.path.relpath(dp, src))
                os.makedirs(d, exist_ok=True)
                shutil.copy2(os.path.join(dp, fn), os.path.join(d, fn)); n += 1
    log("[SND]  copied %d sound configs (horns etc.)" % n)
