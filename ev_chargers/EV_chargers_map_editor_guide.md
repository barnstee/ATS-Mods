# Placing the EV charger icons and plug markers in the ATS map editor

Mod needed (already installed): `ev_chargers.scs` (enable it in Mod Manager, above other map mods).
It adds:
- **Map Overlay, type Road, look `ev_plug`**: the green plug icon on the world map / GPS.
- **Animated model `ev plug marker`**: green plug sign, about 1.6 m, 3.2-4.8 m above the ground, spinning once every 3 s.
- **Model `ev plug marker`**: the same sign without animation (fallback).

## 1. Start the editor
1. Steam > American Truck Simulator > Properties > Launch options: `-developer -console`.
2. Start ATS, choose a profile, then in the main menu open the console (`~`) and type `edit` (Enter).
   Opening the full USA map takes a few minutes.

## 2. Go to a charger
In the editor console (`~`) type the `goto` line from the table, for example `goto -110259;6;-5384`.
The camera jumps above the charger prop (y is +5 m so you start above it).

## 3. Place the spinning marker
1. Choose the **Animated model** item (item toolbar, or Insert > Animated model).
2. Click on the ground right next to the charger, then in the properties choose `ev plug marker`.
3. Move or rotate it with the gizmo so the sign floats above or beside the charger.

## 4. Place the world map icon
1. Choose **Map Overlay** and click next to the charger.
2. Properties: Type = **Road**, Look = `ev_plug`. Leave "show in UI zoom levels" at the defaults.

## 5. Save
1. Map > Save (Ctrl+S). The editor writes your change as a map mod; save it under `mod/user_map` or use "Save as mod".
2. Only the sectors you touched change. Keep this map mod above `ev_chargers.scs` in Mod Manager.
3. After an ATS map update, open the editor again, load and save to refresh it.

## Chargers
| # | Nearest city | Nearest company | Editor console | Map |
|---|---|---|---|---|
| 1 | medford (68.1 km) | dg_wd_hrv (66.3 km) | `goto -116053.3;11;-35177.6` | dlc_or |
| 2 | medford (36.3 km) | dg_wd_saw (26.2 km) | `goto -111918.9;17;-36776.9` | dlc_or |
| 3 | redding (11.7 km) | dc_car_dlr (19.5 km) | `goto -111580.1;19.6;-25892.7` | map_extract |
| 4 | modesto (18.8 km) | cal_farm_alm (15.7 km) | `goto -110492.7;11.5;-5212.8` | map_extract |
| 5 | modesto (15.0 km) | cal_farm_alm (10.8 km) | `goto -110259.0;6;-5384.3` | map_extract |
| 6 | modesto (12.4 km) | gal_oil_gst (21.8 km) | `goto -107953.6;15;-3790.9` | map_extract |
| 7 | eugene (8.7 km) | ed_mkt (3.9 km) | `goto -107357.9;7.5;-45845.1` | dlc_or |
| 8 | bellingham (7.2 km) | wal_mkt (1.4 km) | `goto -98740.5;9.3;-71265.5` | dlc_wa |
| 9 | primm (83.7 km) | hau_oil_gst (84.9 km) | `goto -91769.7;27.3;10647.5` | map_extract |
| 10 | primm (80.7 km) | hau_oil_gst (82.2 km) | `goto -91557.5;27.3;10875.9` | map_extract |
| 11 | omak (10.0 km) | gal_oil_gst (5.1 km) | `goto -88532.7;18.1;-64635.2` | dlc_wa |
| 12 | flagstaff (10.7 km) | fb_farm_mkt (5.9 km) | `goto -70846.0;91.4;14505.9` | dlc_arizona |
| 13 | flagstaff (10.6 km) | fb_farm_mkt (5.9 km) | `goto -70840.2;91.4;14506.4` | dlc_arizona |
| 14 | rangely (146.2 km) | avs_met_scr (148.3 km) | `goto -49208.2;99.3;-15895.1` | map_extract |
| 15 | shreveport (37.7 km) | pho_oil_gst (41.8 km) | `goto 15734.8;6.4;35503.3` | map_extract |

Note: these markers and icons are **visual only**. ATS has no trigger action that charges an electric truck, so the chargers still cannot charge.
Menu names may differ slightly in your editor version.
