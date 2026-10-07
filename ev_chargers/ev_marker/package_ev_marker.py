"""Adds definitions to the compiled ev_marker output and packs/installs ev_chargers.scs."""
import os, re, shutil, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "mod")
GAME = sys.argv[1] if len(sys.argv) > 1 else r"C:\ATSExtract"
# F7 emergency recharge = the EV "charger stop": +300 kWh (fast-charge stop; the option is greyed out if that does not
# fit into the battery - 2000 = "always full" made it never available), regular energy price, 20 min
RECHARGE = {"refuel_fuel": "300", "refuel_price_base": "50", "refuel_price_factor": "1", "refuel_time_base": "1200"}

def write(rel, text):
    p = os.path.join(MOD, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)

write("manifest.sii", "SiiNunit\n{\nmod_package : .package_name\n{\n\tpackage_version: \"1.0\"\n\tdisplay_name: \"EV Chargers - charge here\"\n\tauthor: \"Erich Barnstedt\"\n\tcategory[]: \"map\"\n\tdescription_file: \"description.txt\"\n\tcompatible_versions[]: \"1.61.*\"\n}\n}\n")
write("description.txt", "Marks every EV charger on the map (base map + state DLCs, 32 sites): green plug icon on the world map / GPS\nand a green plug marker at the charger. Placed automatically (map sectors from ChargerFinder --place).\nATS has no charging trigger: stop at a marked charger and use F7 > emergency recharge.\nThis mod makes it a charger stop: +300 kWh, regular price, 20 minutes (applies to all trucks).\n")
write("material/ui/map/road/road_ev_plug.mat", "effect : \"ui.rfx\" {\n\ttexture : \"texture\" {\n\t\tsource : \"road_ev_plug.tobj\"\n\t\tu_address : clamp\n\t\tv_address : clamp\n\t\tmip_filter : none\n\t}\n}\n")
write("def/world/animated_model.ev_chargers.sii", "SiiNunit\n{\nanimated_model_data : anim_mdl.ev_plug\n{\n\tname: \"ev plug marker\"\n\tmodel: \"/model/ev_chargers/plug_marker.pmd\"\n\tanimations[]: \"/model/ev_chargers/plug_marker_spin.pma\"\n\tprobability_day: 1.0\n\tprobability_night: 1.0\n}\n}\n")
write("def/world/model.ev_chargers.sii", "SiiNunit\n{\nmodel_def : model.ev_plug\n{\n\tmodel_desc: \"/model/ev_chargers/plug_marker.pmd\"\n\tname: \"ev plug marker\"\n}\n}\n")
eco = open(os.path.join(GAME, "def", "economy_data.sii"), encoding="utf-8-sig").read()
for k, v in RECHARGE.items():
    eco, n = re.subn(r"^(\s*" + k + r":\s*)[0-9.]+", lambda m: m.group(1) + v, eco, flags=re.M)
    assert n == 1, k
write("def/economy_data.sii", eco)
scs = os.path.join(os.path.dirname(HERE), "ev_chargers.scs")
with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fns in os.walk(MOD):
        for fn in fns:
            f = os.path.join(dp, fn); z.write(f, os.path.relpath(f, MOD).replace(os.sep, "/"))
home = os.path.expanduser("~")
for mod in (os.path.join(home, "OneDrive - Microsoft", "Documents", "American Truck Simulator", "mod"), os.path.join(home, "Documents", "American Truck Simulator", "mod")):
    if os.path.isdir(mod):
        shutil.copy2(scs, mod); print("Installed", scs, "->", mod); break
