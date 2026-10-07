# EV chargers (ATS 1.61)

ATS has charger props on the map but no charging function. This folder finds every charger on the base map and all
installed state DLC maps and marks it automatically (no map editor needed): green plug icon on the world map / GPS and
a green plug marker next to the charger. Charging = F7 > Emergency recharge at a marked charger; the mod overrides
`def/economy_data.sii` (copied from `C:\ATSExtract`) so it gives a full battery at regular price in 20 min.

| Path | What |
|---|---|
| `extract_maps.py` | extracts base_map + every state DLC map into `C:\ATSExtract\map_all`, writes `sector_source.csv` |
| `ChargerFinder/` | .NET + TruckLib: lists all chargers -> `data/chargers.csv`; `--place` adds icon + marker per charger site and writes only the changed map sectors to `ev_marker/mod/map/usa` |
| `data/chargers.csv` | result: 128 objects = 38 charger posts at 32 sites + 90 standalone charging power boxes (not marked) |
| `ev_marker/build_ev_marker.py` | draws the plug art, writes the marker model and the map icon, compiles with resconvert |
| `ev_marker/package_ev_marker.py` | adds defs (marker model `ev plug marker`, map icon `road_ev_plug`), emergency-recharge override (`def/economy_data.sii`, optional arg: extract dir), packs + installs `ev_chargers.scs` |

## How chargers are found
- Charger models = every model whose materials use a charger texture (`ca_e_charger*`, `e-charger-station*`,
  `ia_charging_station_power_box*`): `2124`, `3a029`, `ibe_09018` (posts) and `ia_5e004` (power box).
- Prefabs: none of the 6024 prefab models (base + all state DLCs) uses a charger material, so no truck stop or gas
  station has a built-in charger (ATS 1.61). `chargerPrefabs` in `Program.cs` is ready if SCS adds some.
- Posts within 100 m are one site (one icon + marker). Power boxes are never next to a post, so they are not marked.
- Map mod: TruckLib re-saves the changed sectors (+ a neighbour sector if an item crossing the border moves there);
  `--place` checks that every original item is still in the shipped sectors and only the new icons/markers are added.
  These sectors replace the game's, so rebuild after an ATS map update.

## Build
```
python extract_maps.py --game <ATS dir> --extractor <extractor.exe>
cd ev_marker && python build_ev_marker.py
cd ../ChargerFinder && dotnet run --place
cd ../ev_marker && python package_ev_marker.py
```
Generated (git-ignored): `ev_marker/project/`, `ev_marker/mod/`, `*.scs`, `ChargerFinder/bin|obj`.
