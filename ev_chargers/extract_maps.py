"""extract_maps.py --game <ATS install dir> [--extractor <extractor.exe>] [--out C:\\ATSExtract\\map_all]

Extracts the map of base_map.scs and every installed state DLC (any dlc_*.scs that contains map sectors) into ONE
folder for ChargerFinder, and writes sector_source.csv (sector -> archive) so the charger list can show the state.
Each map sector exists in exactly one archive, so the extraction order does not matter.
Extractor: the game's scs_extractor.exe or sk-zk/Extractor (https://github.com/sk-zk/Extractor/releases).
"""
import argparse, glob, os, re, shutil, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--game", required=True)
ap.add_argument("--extractor", default=os.path.join(os.environ.get("TEMP", ""), "skzk", "extractor.exe"))
ap.add_argument("--out", default=r"C:\ATSExtract\map_all")
o = ap.parse_args()

SEC = re.compile(r"^/map/usa/(sec[+-]\d{4}[+-]\d{4})\.base$")
shutil.rmtree(o.out, ignore_errors=True)
os.makedirs(o.out)
rows = ["sector,source"]
for scs in [os.path.join(o.game, "base_map.scs")] + sorted(glob.glob(os.path.join(o.game, "dlc_*.scs"))):
    name = os.path.splitext(os.path.basename(scs))[0]
    listing = subprocess.run([o.extractor, scs, "--list"], capture_output=True, text=True).stdout.splitlines()
    sectors = [m.group(1) for m in map(SEC.match, listing) if m]
    if not sectors:
        continue
    subprocess.run([o.extractor, scs, "-f", "/map/*", "-d", o.out], capture_output=True, check=True)
    rows += [f"{s},{name}" for s in sectors]
    print(f"{name:14} {len(sectors):4} sectors")
open(os.path.join(o.out, "sector_source.csv"), "w", newline="\n").write("\n".join(rows) + "\n")
print(f"{len(rows) - 1} sectors -> {o.out}")
