# Builds the VNR Electric battery-pack + e-motor models used in place of the VNL fuel tanks.
# Needs: tools\bin\converter_pix.exe, SCS conversion tools in C:\ATSExtract\conversion_tools.
param([string]$Game = "C:\ATSExtract", [string]$Conv = "C:\ATSExtract\conversion_tools")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$src = Join-Path $root "blender\src"
$proj = Join-Path $root "blender\project"
$rel = "vehicle\truck\volvo_vnl_e\accessory\tank"
& (Join-Path $PSScriptRoot "bin\converter_pix.exe") -b $Game -e $src -m /vehicle/truck/volvo_vnr_e/chassis/chs_4x2 | Out-Null
$pim = Join-Path $src "vehicle\truck\volvo_vnr_e\chassis\chs_4x2.pim"
# battery packs + e-motor/inverter: everything fully inside this box of the VNR frame (SCS axes, m)
$box = "-1.25", "0.2", "-1.35", "1.25", "1.0", "0.97"
# std: VNR length, centred in the short/mid tank slot; long: stretched 1.4x to fill the 275 gal slot
python (Join-Path $PSScriptRoot "pim_tool.py") extract $pim (Join-Path $proj "$rel\vnr_battery_std.pim") --box @box --offset 0 -0.639 -0.40
python (Join-Path $PSScriptRoot "pim_tool.py") extract $pim (Join-Path $proj "$rel\vnr_battery_long.pim") --box @box --offset 0 -0.639 -0.205 --scale-z 1.4
# XR: 20% longer than the std/long packs, front edge kept, extended towards the rear axle
python (Join-Path $PSScriptRoot "pim_tool.py") extract $pim (Join-Path $proj "$rel\vnr_battery_std_xr.pim") --box @box --offset 0 -0.639 -0.176 --scale-z 1.2
python (Join-Path $PSScriptRoot "pim_tool.py") extract $pim (Join-Path $proj "$rel\vnr_battery_long_xr.pim") --box @box --offset 0 -0.639 0.109 --scale-z 1.68
$link = Join-Path $Conv "rsrc\vnl_e"
if (-not (Test-Path $link)) { cmd /c mklink /J $link $proj | Out-Null }
Push-Location (Join-Path $Conv "bin\win_x64\tools")
.\resconvert.exe -update -root rsrc/vnl_e 2>&1 | Out-Null
$log = Get-Content mass_convert.log
Pop-Location
if ($log -match "\*\*\* ERROR") { $log | Select-String "ERROR"; throw "conversion failed" }
$cache = Join-Path $Conv "rsrc\rsrc\vnl_e\@cache\$rel"
$dst = Join-Path $root $rel
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item (Join-Path $cache "vnr_battery_*.pm?") $dst -Force
# materials generated from the inline PIT materials
$mat = Join-Path $root "automat"
Remove-Item $mat -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Conv "rsrc\rsrc\vnl_e\@cache\automat") $mat -Recurse -Force
Get-ChildItem $dst | Select-Object Name, Length
