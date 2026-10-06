#!/usr/bin/env python3
"""
make_vnl_electric.py - builds the fictional "Volvo VNL Electric (concept)" truck for ATS.

Recipe
  body / cabins / interiors / accessories / lights / sounds  <- base-game Volvo VNL (2024)
  frames (chassis)                                             <- base-game Volvo VNL, electrified
  e-motor, 2-speed I-Shift, e-sounds                           <- base-game Volvo VNR Electric
  + battery capacity scaled by wheelbase (longer frame = more packs)
  + extended-range battery packs (capacity scaled)  + fictional dual-motor 605 hp option
  + VNR Electric battery packs + e-motor unit in place of the fuel tanks (tools\batteries.py)
  + its own Volvo dealer showcase slot

Only .sii/.sui definitions are generated. All 3D models stay referenced from the game
archives, so no SCS assets are redistributed.

Usage
  python make_vnl_electric.py --game C:\\ats_extract --list
  python make_vnl_electric.py --game C:\\ats_extract --donor volvo.<vnl2024-id> --pack
Options
  --vnr volvo.vnr_e   id of the VNR Electric folder (default volvo.vnr_e)
  --range 1.75        capacity factor for the "ER" packs   --xr 2.5  factor for "XR" packs
  --vnr-interior      also offer the VNR electric dashboard/interior on all cabins
"""
import argparse, os, re, sys, shutil, zipfile
from batteries import copy_soundrefs, ev_frames, ev_engines, ev_paintjob, extend_suitable, no_exhaust, pack_models, install

TARGET = "volvo.vnl_e"
TRUCK_DIR = ("def", "vehicle", "truck")
FROM_VNR = ("engine", "transmission")                     # parts taken from the VNR
KWH_PER_INCH = 375 / 155.0      # VNR Electric pack (375 kWh) on the shortest VNL wheelbase (155")
KG_PER_KWH = 5.5                # pack mass incl. housings
KWH_OVERRIDE = {}   # 74" twin rear axle frames: big standard pack
DIESEL_FRONT_KG = 700           # diesel engine/cooling removed from front axle
CAP_RE = re.compile(r'^(\s*)(fuel_capacity|tank_size|battery_capacity|battery_size|[a-z_]*capacity)(\s*:\s*)([0-9.]+)(.*)$', re.I)
PRICE_RE = re.compile(r'^(\s*price\s*:\s*)([0-9]+)(.*)$', re.I | re.M)
UNIT_RE = re.compile(r'^(\s*)([a-z0-9_]+)(\s*:\s*)(\S+)\s*$', re.I)
LOG = []


def log(msg):
    LOG.append(msg); print(msg)


def rd(p):
    raw = open(p, "rb").read()
    if raw[:4] in (b"ScsC", b"BSII") or raw[:3] == b"3nK":
        sys.exit(f"ERROR: {p} is encrypted/binary - decode it (SII_Decrypt) first.")
    return raw.decode("utf-8-sig")


def wr(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(t)


def id_re(tid):
    return re.compile(r'(?<![a-z0-9_])' + re.escape(tid) + r'(?![a-z0-9_])', re.I)


def walk(d):
    for dp, _, fns in os.walk(d):
        for fn in fns:
            if fn.endswith((".sii", ".sui")):
                yield os.path.join(dp, fn)


# ---------------------------------------------------------------- list
def do_list(game):
    root = os.path.join(game, *TRUCK_DIR)
    for d in sorted(os.listdir(root)):
        if d.startswith("volvo."):
            sub = sorted(x for x in os.listdir(os.path.join(root, d)) if os.path.isdir(os.path.join(root, d, x)))
            cabs = []
            cd = os.path.join(root, d, "cabin")
            if os.path.isdir(cd):
                for f in walk(cd):
                    cabs += re.findall(r'name\s*:\s*"([^"]+)"', rd(f))[:1]
            print(f"{d:22s} cabins={cabs}  parts={sub}")


# ---------------------------------------------------------------- step 1: VNL body
def clone_vnl(game, donor, tgt):
    src = os.path.join(game, *TRUCK_DIR, donor)
    rx = id_re(donor)
    n = 0
    for f in walk(src):
        rel = os.path.relpath(f, src)
        if rel.split(os.sep)[0] in FROM_VNR:
            continue
        t = rx.sub(TARGET, rd(f))
        # interior cameras only exist for the donor - keep using them
        t = re.sub(r'(camera\.interior\.)' + re.escape(TARGET) + r'(?![a-z0-9_])', r'\g<1>' + donor, t)
        if rel == "data.sii":
            t = re.sub(r'(name\s*:\s*")[^"]*(")', r'\1VNL Electric\2', t, count=1)
            t = re.sub(r'(info\[\]\s*:\s*")@@series_[a-z0-9_]+@@(")', r'\1VNL Electric\2', t, count=1)
        wr(os.path.join(tgt, rel), t); n += 1
    log(f"[VNL]  cloned {n} body/accessory files from {donor}")


# ---------------------------------------------------------------- step 2: VNR e-drivetrain
def clone_vnr(game, vnr, tgt):
    vroot = os.path.join(game, *TRUCK_DIR, vnr)
    if not os.path.isdir(vroot):
        sys.exit(f"ERROR: {vroot} not found (use --vnr)")
    path_re = re.compile(r'/def/vehicle/truck/' + re.escape(vnr) + r'/([^"\s]+\.s[iu]i)', re.I)
    unit_re = re.compile(r'(?<![a-z0-9_])([a-z0-9_]{1,12})\.' + re.escape(vnr) + r'\.([a-z0-9_]+)', re.I)

    # tokens already used by the VNL clone, per accessory type
    used = set()
    for f in walk(tgt):
        for tok, typ in re.findall(r'([a-z0-9_]{1,12})\.' + re.escape(TARGET) + r'\.([a-z0-9_]+)', rd(f), re.I):
            used.add((tok.lower(), typ.lower()))

    queue = [os.path.relpath(f, vroot) for d in FROM_VNR if os.path.isdir(os.path.join(vroot, d))
             for f in walk(os.path.join(vroot, d))]
    done, texts, rename = set(), {}, {}

    def new_rel(rel):
        d, b = os.path.split(rel)
        return os.path.join(d, "vnr_" + b)

    while queue:                                  # dependency closure (sounds, sui includes ...)
        rel = os.path.normpath(queue.pop())
        if rel in done:
            continue
        done.add(rel)
        p = os.path.join(vroot, rel)
        if not os.path.isfile(p):
            log(f"[VNR]  WARNING referenced file missing: {rel}"); continue
        t = rd(p)
        for m in path_re.finditer(t):
            queue.append(m.group(1).replace("/", os.sep))
        for m in re.finditer(r'@include\s+"([^"/][^"]*)"', t):
            queue.append(os.path.join(os.path.dirname(rel), m.group(1)))
        for tok, typ in unit_re.findall(t):
            key = (tok.lower(), typ.lower())
            if key in rename:
                continue
            new, i = tok.lower(), 0
            while (new, typ.lower()) in used:
                i += 1; new = (("e%d" % i) + tok)[:12]
            used.add((new, typ.lower())); rename[key] = new
        texts[rel] = t

    for rel, t in texts.items():
        t = path_re.sub(lambda m: f"/def/vehicle/truck/{TARGET}/" + new_rel(m.group(1)).replace(os.sep, "/"), t)
        t = re.sub(r'(@include\s+")([^"/][^"]*)(")',
                   lambda m: m.group(1) + new_rel(m.group(2)).replace(os.sep, "/") + m.group(3), t)
        t = unit_re.sub(lambda m: f"{rename[(m.group(1).lower(), m.group(2).lower())]}.{TARGET}.{m.group(2)}", t)
        t = id_re(vnr).sub(TARGET, t)
        # VNR parts must not be limited to the VNR day cab
        t = re.sub(r'^\s*suitable_for\s*(\[\d*\])?\s*:\s*"[^"]*\.cabin"\s*$',
                   lambda m: "#" + m.group(0).strip() + "   # removed: fits all VNL cabins", t, flags=re.M)
        wr(os.path.join(tgt, new_rel(rel)), t)
    log(f"[VNR]  cloned {len(texts)} e-drivetrain files (engine/transmission/battery chassis + deps)")
    return vroot


# ---------------------------------------------------------------- step 2b: electrify VNL frames
def add_mass(t, kg_front, kg_rear):
    it = iter((kg_front, kg_rear))
    def sub(m):
        try:
            v = float(m.group(2)) + next(it)
        except StopIteration:
            return m.group(0)
        return f"{m.group(1)}{v:.0f}\t# {v * 2.20462:.0f}lb"
    return re.sub(r'^(\s*kerb_weight\s*(?:\[\d*\])?\s*:\s*)([0-9.]+).*$', sub, t, flags=re.M)


def electrify(tgt):
    cdir = os.path.join(tgt, "chassis")
    n = 0
    for f in sorted(x for x in os.listdir(cdir) if x.endswith(".sii")):
        p = os.path.join(cdir, f)
        t = rd(p)
        wb = re.search(r'_(\d{3})_', f)
        if not wb or not re.search(r'^\s*tank_size', t, re.M):
            continue
        kwh = KWH_OVERRIDE.get(f[:-4], int(wb.group(1)) * KWH_PER_INCH)
        t = re.sub(r'^(\s*tank_size\s*:\s*)[0-9.]+.*$', lambda m: f"{m.group(1)}{kwh:.0f}\t# battery kWh", t, flags=re.M)
        t = add_mass(t, kwh * KG_PER_KWH * 0.4 - DIESEL_FRONT_KG, kwh * KG_PER_KWH * 0.6)
        t = re.sub(r'(^\s*name\s*:\s*")([^"]*)(")', lambda m: f"{m.group(1)}{m.group(2)} {kwh:.0f} kWh{m.group(3)}", t, count=1, flags=re.M)
        wr(p, t); n += 1
    log(f"[EV]   electrified {n} VNL frames ({KWH_PER_INCH:.2f} kWh per inch of wheelbase)")


# ---------------------------------------------------------------- step 3: extended range + 605 hp
def variants(tgt, rng, xr):
    cdir = os.path.join(tgt, "chassis")
    scaled = 0
    pairs = []
    for f in sorted(x for x in os.listdir(cdir) if x.endswith(".sii") and not x.startswith(("er_", "xr_"))):
        base = rd(os.path.join(cdir, f))
        cap = re.search(r'^\s*tank_size\s*:\s*([0-9.]+)', base, re.M)
        if not cap:
            continue
        cap = float(cap.group(1))
        for tag, fac, pr in (("er", rng, 1.0), ("xr", xr, 1.0)):
            out, hit = [], False
            for line in base.splitlines():
                m = UNIT_RE.match(line)
                if m and ("." + TARGET + ".") in m.group(4) and m.group(4).endswith(".chassis"):
                    tok, rest = m.group(4).split(".", 1)
                    line = f"{m.group(1)}{m.group(2)}{m.group(3)}{(tag + tok)[:12]}.{rest}"
                    pairs.append((tok, (tag + tok)[:12]))
                c = CAP_RE.match(line)
                if c:
                    hit = True
                    v = float(c.group(4)) * fac
                    line = f"{c.group(1)}{c.group(2)}{c.group(3)}{v:.1f}{c.group(5)}"
                p = PRICE_RE.match(line)
                if p:
                    line = f"{p.group(1)}{int(int(p.group(2)) + 9000 * fac)}{p.group(3)}"
                line = re.sub(r'(^\s*name\s*:\s*")([^"]*?)(?: \d+ kWh)?(")',
                              lambda q: f'{q.group(1)}{q.group(2)} {tag.upper()} {cap * fac:.0f} kWh{q.group(3)}', line)
                out.append(line)
            if hit:
                extra = cap * (fac - 1) * KG_PER_KWH
                body = add_mass("\n".join(out) + "\n", extra * 0.4, extra * 0.6)
                wr(os.path.join(cdir, f"{tag}_{f}"), body); scaled += 1
            else:
                log(f"[RNG]  WARNING no capacity attribute in chassis {f} - range variant skipped")
                break
    log(f"[RNG]  created {scaled} extended-range chassis variants (ER x{rng:g}, XR x{xr:g})")

    # cabins that conflict with a frame must also conflict with its ER/XR versions
    cab = os.path.join(tgt, "cabin")
    for f in (x for x in os.listdir(cab) if x.endswith(".sii")):
        t = rd(os.path.join(cab, f))
        for old, new in pairs:
            t = re.sub(r'^(\s*conflict_with\[\]\s*:\s*")' + re.escape(old) + r'(\.' + re.escape(TARGET) + r'\.chassis"\s*)$',
                       lambda m: m.group(0) + "\n" + m.group(1) + new + m.group(2).rstrip(), t, flags=re.M)
        wr(os.path.join(cab, f), t)

    edir = os.path.join(tgt, "engine")
    for f in sorted(x for x in os.listdir(edir) if x.startswith("vnr_") and x.endswith(".sii")):
        t = rd(os.path.join(edir, f))
        if not re.search(r'^\s*type\s*:\s*electric', t, re.M):
            continue
        tq = re.search(r'^(\s*torque\s*:\s*)([0-9.]+)', t, re.M)
        if not tq:
            continue
        k = 605 / 455.0
        t2 = t.replace(tq.group(0), f"{tq.group(1)}{float(tq.group(2)) * k:.0f}", 1)
        t2 = re.sub(r'(\s[a-z0-9_]+\s*:\s*)([a-z0-9_]{1,12})(\.' + re.escape(TARGET) + r'\.engine)',
                    lambda m: m.group(1) + ("dm" + m.group(2))[:12] + m.group(3), t2, count=1)
        t2 = re.sub(r'(^\s*name\s*:\s*")[^"]*(")', r'\1Volvo Electric Dual-Motor 605 HP\2', t2, flags=re.M)
        t2 = re.sub(r'^(\s*info\[\]\s*:\s*").*@@hp@@.*$', r'\g<1>605 @@hp@@ (451 @@kw@@)"', t2, flags=re.M, count=1)
        t2 = re.sub(r'^(\s*info\[\]\s*:\s*").*@@lb_ft@@.*$',
                    lambda m: f'{m.group(1)}{float(tq.group(2)) * k * 0.7376:.0f} @@lb_ft@@ ({float(tq.group(2)) * k:.0f} @@nm@@)"',
                    t2, flags=re.M, count=1)
        t2 = PRICE_RE.sub(lambda p: f"{p.group(1)}{int(int(p.group(2)) * 1.35)}{p.group(3)}", t2)
        wr(os.path.join(edir, f.replace("vnr_", "vnr_dm_")), t2)
        log(f"[MOT]  added fictional dual-motor 605 hp variant of {f}")
        break


# ---------------------------------------------------------------- step 4: optional VNR dashboard
def vnr_interior(game, vnr, tgt):
    idir = os.path.join(game, *TRUCK_DIR, vnr, "interior")
    if not os.path.isdir(idir):
        return
    n = 0
    for f in walk(idir):
        t = id_re(vnr).sub(TARGET, rd(f))
        t = re.sub(r'([a-z0-9_]{1,12})(\.' + re.escape(TARGET) + r'\.interior)',
                   lambda m: ("vnr" + m.group(1))[:12] + m.group(2), t)
        t = re.sub(r'^\s*suitable_for.*$', "", t, flags=re.M)
        wr(os.path.join(tgt, "interior", "vnr_" + os.path.basename(f)), t); n += 1
    log(f"[INT]  added {n} VNR electric interior(s) for all cabins")


# ---------------------------------------------------------------- step 5: fix dangling refs (data.sii fallbacks etc.)
def fix_refs(tgt):
    ref_re = re.compile(r'/def/vehicle/truck/' + re.escape(TARGET) + r'/([a-z0-9_]+)/([^"\s]+\.s[iu]i)', re.I)
    default = {}
    for d in FROM_VNR:
        dd = os.path.join(tgt, d)
        c = sorted(x for x in os.listdir(dd) if x.startswith("vnr_") and x.endswith(".sii")
                   and not x.startswith(("vnr_er_", "vnr_xr_", "vnr_dm_"))) if os.path.isdir(dd) else []
        if c:
            default[d] = c[0]
    for f in walk(tgt):
        t = rd(f)
        def sub(m):
            if os.path.isfile(os.path.join(tgt, m.group(1), m.group(2))):
                return m.group(0)
            if m.group(1) in default:
                return f"/def/vehicle/truck/{TARGET}/{m.group(1)}/{default[m.group(1)]}"
            log(f"[REF]  WARNING dangling {m.group(0)} in {os.path.relpath(f, tgt)}")
            return m.group(0)
        t2 = ref_re.sub(sub, t)
        if t2 != t:
            wr(f, t2)
    log(f"[REF]  diesel fallbacks redirected to {default}")
    return default


# ---------------------------------------------------------------- step 6: dealer
def dealer(game, donor, out, default):
    ddir = os.path.join(game, "def", "vehicle", "truck_dealer")
    if not os.path.isdir(ddir):
        log("[DLR]  WARNING truck_dealer folder not found - buy via Snarfv-style dealer mods"); return
    rx = id_re(donor)
    show = [f for f in walk(ddir) if rx.search(rd(f))]
    if not show:
        log("[DLR]  WARNING no dealer showcase references the donor"); return
    src = show[0]
    t = rx.sub(TARGET, rd(src))
    for d, fn in default.items():
        t = re.sub(r'(/def/vehicle/truck/' + re.escape(TARGET) + '/' + d + r'/)[^"]+', r'\g<1>' + fn, t)
    sv = re.search(r'^\s*vehicle\s*:\s*\.tdealer\.([a-z0-9_]+)', t, re.M)
    if sv:
        t = re.sub(r'\.tdealer\.' + re.escape(sv.group(1)) + r'(?![a-z0-9_])', '.tdealer.vnl_e', t)
    rel_inc = os.path.relpath(src, ddir).replace(os.sep, "/")
    brand_dir = rel_inc.split("/")[0] if "/" in rel_inc else "volvo"
    inc = f"{brand_dir}/vnl_e.sii"
    wr(os.path.join(out, "def", "vehicle", "truck_dealer", *inc.split("/")), t)
    brand = "@@brand_volvo@@"
    for f in os.listdir(ddir):
        p = os.path.join(ddir, f)
        if f.endswith(".sii") and os.path.isfile(p) and rel_inc in rd(p):
            m = re.search(r'brand\s*:\s*"([^"]+)"', rd(p)); brand = m.group(1) if m else brand
    wr(os.path.join(out, "def", "vehicle", "truck_dealer", f"{brand_dir}.vnl_e.sii"),
       'SiiNunit\n{\ntruck_dealer_sortiment : .tdealer.sortiment\n{\n'
       f'\tbrand: "{brand}"\n\tshowcase_vehicles[0]: .tdealer.vnl_e\n}}\n@include "{inc}"\n}}\n')
    log(f"[DLR]  showcase slot added from {os.path.relpath(src, game)}")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--game", required=True); a.add_argument("--donor"); a.add_argument("--vnr", default="volvo.vnr_e")
    a.add_argument("--range", type=float, default=1.75); a.add_argument("--xr", type=float, default=2.5)
    a.add_argument("--vnr-interior", action="store_true"); a.add_argument("--list", action="store_true")
    a.add_argument("--pack", action="store_true")
    a.add_argument("--out", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    o = a.parse_args()
    if o.list:
        return do_list(o.game)
    if not o.donor:
        sys.exit("ERROR: --donor required (run --list)")
    tgt = os.path.join(o.out, *TRUCK_DIR, TARGET)
    shutil.rmtree(os.path.join(o.out, "def"), ignore_errors=True)
    clone_vnl(o.game, o.donor, tgt)
    copy_soundrefs(o.game, o.donor, tgt, log)
    clone_vnr(o.game, o.vnr, tgt)
    electrify(tgt)
    variants(tgt, o.range, o.xr)
    if o.vnr_interior:
        vnr_interior(o.game, o.vnr, tgt)
    default = fix_refs(tgt)
    extend_suitable(tgt, TARGET, rd, wr, log)
    dealer(o.game, o.donor, o.out, default)
    no_exhaust(tgt, o.out, TARGET, rd, wr, log)
    ev_frames(tgt, o.out, TARGET, rd, wr, log)
    ev_engines(tgt, TARGET, rd, wr, log)
    ev_paintjob(tgt, o.out, TARGET, wr, log)
    wr(os.path.join(o.out, "build_log.txt"), "\n".join(LOG) + "\n")
    if o.pack:
        scs = os.path.join(os.path.dirname(o.out), "vnl_electric_concept.scs")
        with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as z:
            for b in ("manifest.sii", "description.txt"):
                z.write(os.path.join(o.out, b), b)
            for f in walk(os.path.join(o.out, "def")):
                z.write(f, os.path.relpath(f, o.out).replace(os.sep, "/"))
            pack_models(z, o.out)
        mod = install(scs)
        if mod:
            print(f"Installed to {mod}")
        print(f"Packed {scs} -> Documents\\American Truck Simulator\\mod")


if __name__ == "__main__":
    main()
