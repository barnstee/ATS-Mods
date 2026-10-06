# EV chargers (ATS 1.61)

ATS has charger props on the map but no charging function. This folder finds them and provides a plug
world-map icon and plug marker model to tag them in the map editor (visual only).

| Path | What |
|---|---|
| `ChargerFinder/` | .NET + TruckLib: lists placed charger models (`ibe_09018`, `2124`, `3a029`) with nearest city/company from the extracted base + state DLC maps |
| `data/chargers.csv` | result: 15 chargers |
| `ev_marker/build_ev_marker.py` | draws the plug art, writes the marker model/skeleton/spin animation, compiles with resconvert |
| `ev_marker/package_ev_marker.py` | adds defs (Model / Animated model `ev plug marker`, map icon `road_ev_plug`), packs + installs `ev_chargers.scs` |
| `EV_chargers_map_editor_guide.md` | step by step placement in the editor (`-edit -developer -console`) |

## Build
```
# map data: scs_extractor base_map.scs -> C:\ATSExtract\map_extract, dlc_<state>.scs -> C:\ATSExtract\map_dlc\<dlc>
cd ChargerFinder && dotnet run
cd ../ev_marker && python build_ev_marker.py && python package_ev_marker.py
```
Generated (git-ignored): `ev_marker/project/`, `ev_marker/mod/`, `*.scs`, `ChargerFinder/bin|obj`.
