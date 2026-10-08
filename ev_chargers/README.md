# EV chargers (ATS 1.61)

ATS has charger props on the map but no charging function. This folder finds every charger on the base map and all
installed state DLC maps (`data/chargers.csv`) and provides a green plug world-map icon and plug marker model.
Charging = F7 > Emergency recharge at a charger. For electric trucks ATS 1.61 offers it only when the State of Charge (SoC) is low
and always adds 100 kWh for about $350.

| Path | What |
|---|---|
| `extract_maps.py` | extracts base_map + every state DLC map into `C:\ATSExtract\map_all`, writes `sector_source.csv` |
| `ChargerFinder/` | .NET + TruckLib: lists all chargers -> `data/chargers.csv`; `--place` adds a plug icon per charger site in one extra map sector (`ev_marker/mod/map/usa`, experimental) |
| `data/chargers.csv` | result: 128 objects = 38 charger posts at 32 sites + 90 standalone charging power boxes (not marked) |
| `ev_marker/build_ev_marker.py` | draws the plug art, writes the marker model and the map icon, compiles with resconvert |
| `ev_marker/package_ev_marker.py` | adds defs (marker model `ev plug marker`, map icon `road_ev_plug`), packs + installs `ev_chargers.scs` |

## How chargers are found
- Charger models = every model whose materials use a charger texture (`ca_e_charger*`, `e-charger-station*`,
  `ia_charging_station_power_box*`): `2124`, `3a029`, `ibe_09018` (posts) and `ia_5e004` (power box).
- Prefabs: none of the 6024 prefab models (base + all state DLCs) uses a charger material, so no truck stop or gas
  station has a built-in charger (ATS 1.61). `chargerPrefabs` in `Program.cs` is ready if SCS adds some.
- Posts within 100 m are one site (one icon + marker). Power boxes are never next to a post, so they are not marked.
- Map mod: one new sector at an unused coordinate holds only the 32 plug icons (3D markers are not placed: models load only near the player, and this sector is off the map) (written with TruckLib's own
  sector writer); its `.desc` is copied from a game sector (ATS 1.61 uses 40 bytes, TruckLib writes 32). The game
  may log "Excessive sector boundary" for it.

## Build
```
python extract_maps.py --game <ATS dir> --extractor <extractor.exe>
cd ev_marker && python build_ev_marker.py
cd ../ChargerFinder && dotnet run --place
cd ../ev_marker && python package_ev_marker.py
```
Generated (git-ignored): `ev_marker/project/`, `ev_marker/mod/`, `*.scs`, `ChargerFinder/bin|obj`.

`--place` (map icons, **experimental**) writes the plug icons into ONE extra sector (`map/usa/sec-0040-0030.*`); no SCS sector is replaced (re-saving SCS sectors with TruckLib 0.5.1 crashed ATS 1.61). Keep the order above: `build_ev_marker.py` clears `ev_marker\mod`. If a save does not load, build without `--place`.
