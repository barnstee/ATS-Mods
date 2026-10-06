"""Adds definitions to the compiled ev_marker output and packs/installs ev_chargers.scs."""
import os, shutil, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "mod")

def write(rel, text):
    p = os.path.join(MOD, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)

write("manifest.sii", "SiiNunit\n{\nmod_package : .package_name\n{\n\tpackage_version: \"1.0\"\n\tdisplay_name: \"EV Chargers - map icons and plug markers\"\n\tauthor: \"Erich Barnstedt\"\n\tcategory[]: \"map\"\n\tdescription_file: \"description.txt\"\n\tcompatible_versions[]: \"1.61.*\"\n}\n}\n")
write("description.txt", "Plug icon for the world map (Map Overlay > Road, look ev_plug) and a spinning green plug marker\n(Animated model ev plug marker / Model ev plug marker) to tag the EV chargers on the map.\nVisual only - ATS has no charging trigger.\n")
write("material/ui/map/road/road_ev_plug.mat", "effect : \"ui.rfx\" {\n\ttexture : \"texture\" {\n\t\tsource : \"road_ev_plug.tobj\"\n\t\tu_address : clamp\n\t\tv_address : clamp\n\t\tmip_filter : none\n\t}\n}\n")
write("def/world/animated_model.ev_chargers.sii", "SiiNunit\n{\nanimated_model_data : anim_mdl.ev_plug\n{\n\tname: \"ev plug marker\"\n\tmodel: \"/model/ev_chargers/plug_marker.pmd\"\n\tanimations[]: \"/model/ev_chargers/plug_marker_spin.pma\"\n\tprobability_day: 1.0\n\tprobability_night: 1.0\n}\n}\n")
write("def/world/model.ev_chargers.sii", "SiiNunit\n{\nmodel_def : model.ev_plug\n{\n\tmodel_desc: \"/model/ev_chargers/plug_marker.pmd\"\n\tname: \"ev plug marker\"\n}\n}\n")
scs = os.path.join(os.path.dirname(HERE), "ev_chargers.scs")
with zipfile.ZipFile(scs, "w", zipfile.ZIP_DEFLATED) as z:
    for dp, _, fns in os.walk(MOD):
        for fn in fns:
            f = os.path.join(dp, fn); z.write(f, os.path.relpath(f, MOD).replace(os.sep, "/"))
home = os.path.expanduser("~")
for mod in (os.path.join(home, "OneDrive - Microsoft", "Documents", "American Truck Simulator", "mod"), os.path.join(home, "Documents", "American Truck Simulator", "mod")):
    if os.path.isdir(mod):
        shutil.copy2(scs, mod); print("Installed", scs, "->", mod); break
