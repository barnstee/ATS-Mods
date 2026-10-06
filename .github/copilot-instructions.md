# Copilot Instructions

## Project Guidelines
- Repo root: `C:\Users\erichb\source\repos\ATS-Mods`. Game data is extracted to `C:\ATSExtract` (see README, Setup).
- Only commit our own sources. Never commit extracted SCS game files or generated output (`def/`, `vehicle/`, `automat/`, `blender/`, `*.scs`, `tools/bin/`).
- After any change to the VNL Electric mod, always rebuild it and install it yourself:
  - if models, battery sizes, motor layout or the logo/paint changed: `python vnl_electric\tools\build_models.py`
  - always: `python vnl_electric\tools\make_vnl_electric.py --game C:\ATSExtract --donor volvo.vnl2025 --pack` (copies `vnl_electric_concept.scs` into `Documents\American Truck Simulator\mod`; if ATS is running, ask the user to close it and run again).
- After changes to the EV charger marker/icon: `python ev_chargers\ev_marker\build_ev_marker.py` then `python ev_chargers\ev_marker\package_ev_marker.py`.
- Keep `README.md` setup/build instructions in sync with any new tool, path or step.
