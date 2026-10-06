# Volvo VNL Electric (ATS 1.61)

VNL 2025 cabins/interiors/accessories on electrified VNL 2025 frames, with the VNR Electric battery packs
(cut out of the VNR frame, plus a 3rd pack between the rails) and Volvo e-axle drive units.

| Part | Result |
|---|---|
| Frames | all 9 VNL 2025 frames, step ladder removed; Standard / ER / XR battery per frame |
| Battery | pack length fills the space between door steps and rear axle; capacity 126 kWh/m (real VNR density) over 2 side + centre pack; 5.5 kg/kWh |
| Motors | 1 option per layout: e-axle 460 kW (4x2, 6x2) or dual e-axle 920 kW (6x4) |
| 74" 6x4 | labelled 246in, Standard pack = 6x2 ER pack (946 kWh) |
| Paint | "Phoenix Trucking": white metallic + `assets/logo.jpg` on sleeper sides (door window height) and back |
| Other | exhaust removed, VNL horns/sounds, interior cameras from VNL 2025, own dealer slot |

## Build
```
# 1. extract the game defs + Volvo DLCs (once) into C:\ATSExtract with scs_extractor
# 2. models: frames without ladder, 27 battery packs, paint masks  -> vnl_electric/vehicle, automat
python tools/build_models.py --game C:\ATSExtract --conv C:\ATSExtract\conversion_tools
# 3. definitions + pack + install to Documents\American Truck Simulator\mod
python tools/make_vnl_electric.py --game C:\ATSExtract --donor volvo.vnl2025 --pack
```

## Scripts
| File | Purpose |
|---|---|
| `make_vnl_electric.py` | generator: clones VNL 2025 + VNR e-drivetrain defs, electrifies frames, ER/XR variants, dealer, pack/install |
| `batteries.py` | battery/frame/motor/paint/sound steps used by the generator |
| `build_models.py` | runs ConverterPIX + the PIM tools + resconvert for all custom models |
| `pim_tool.py` / `pim_compose.py` / `pim_remove.py` | text PIM utilities: analyse, extract/compose island copies, remove islands |
| `make_paintjob.py` | projects the logo through the cab paint UVs into airbrush masks |
| `inspect_models.py` | Blender helper to list mesh parts (optional) |
| `build_battery_models.ps1` | legacy, superseded by `build_models.py` |

Generated (git-ignored): `def/`, `vehicle/`, `automat/`, `blender/`, `build_log.txt`, `*.scs`, `tools/bin/`.
