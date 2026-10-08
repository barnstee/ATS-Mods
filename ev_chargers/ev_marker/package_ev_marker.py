"""Adds definitions to the compiled ev_marker output and packs/installs ev_chargers.scs."""
import os, re, shutil, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "mod")
# No economy_data.sii override: ATS 1.61 ignores refuel_* for electric trucks (emergency recharge is always
# +100 kWh for about $350, offered below 20 miles of range), so overriding it only changed diesel trucks.

def write(rel, text):
    p = os.path.join(MOD, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8", newline="\n").write(text)

write("manifest.sii", "SiiNunit\n{\nmod_package : .package_name\n{\n\tpackage_version: \"1.0\"\n\tdisplay_name: \"EV Chargers - charge here\"\n\tauthor: \"Erich Barnstedt\"\n\tcategory[]: \"map\"\n\tdescription_file: \"description.txt\"\n\ticon: \"mod_icon.jpg\"\n\tcompatible_versions[]: \"1.61.*\"\n}\n}\n")
write("description.txt", "Every EV charger on the map (base map + state DLCs, 32 sites) becomes a charging stop: drive into the bay\n"
      "beside the charger and refuel like at a pump (full battery). A green plug icon on the world map / GPS shows the chargers.\n\n"
      "Needs a truck whose e-motor can be refuelled, e.g. the Volvo VNL Electric concept mod.\n\n"
      "Requires the state DLCs Arizona, Oregon, Washington, Utah, Idaho, Wyoming, Montana, Texas, Oklahoma and Arkansas\n"
      "(the mod updates map sectors of these states). After an ATS map update, wait for an updated version of this mod.\n\n"
      "Source and build instructions: https://github.com/barnstee/ATS-Mods\n")
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

# --workshop: Steam Workshop Uploader input in <repo>/workshop (same layout as vnl_electric):
#   workshop/ev_chargers/versions.sii + universal/ (manifest without version/name fields, ev_chargers.scs, mod_icon.jpg)
#   workshop/ev_chargers_preview.jpg (640x360)
if "--workshop" in sys.argv:
    from PIL import Image
    root = os.path.dirname(os.path.dirname(HERE))
    ws = os.path.join(root, "workshop", "ev_chargers")
    shutil.rmtree(ws, ignore_errors=True)
    uni = os.path.join(ws, "universal")
    # Same layout as the uploaded vnl_electric. Note: the uploader rejects map sector files
    # (.base/.data/.aux/.snd/.desc) with "unsupported extension", also inside nested archives.
    shutil.copytree(MOD, uni)
    mf = os.path.join(uni, "manifest.sii")
    m = open(mf, encoding="utf-8").read()
    open(mf, "w", encoding="utf-8", newline="\n").write(re.sub(r"^\s*(compatible_versions\[\]|display_name)\s*:.*\n", "", m, flags=re.M))
    open(os.path.join(ws, "versions.sii"), "w", newline="\n").write('SiiNunit\n{\npackage_version_info : .universal\n{\n\tpackage_name: "universal"\n}\n}\n')
    plug = Image.open(os.path.join(HERE, "plug_preview.png")).convert("RGBA")
    def card(w, h):
        img = Image.new("RGB", (w, h), (22, 26, 30))
        s = int(h * 0.86); p = plug.resize((s, s), Image.LANCZOS)
        img.paste(p, ((w - s) // 2, (h - s) // 2), p)
        return img
    card(276, 162).save(os.path.join(uni, "mod_icon.jpg"), "JPEG", quality=92)
    card(640, 360).save(os.path.join(root, "workshop", "ev_chargers_preview.jpg"), "JPEG", quality=90)
    print("Workshop folder", ws, "+ ev_chargers_preview.jpg ready for the Workshop Uploader")
