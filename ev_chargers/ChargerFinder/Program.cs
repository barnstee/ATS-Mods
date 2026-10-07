using System.Globalization;
using System.Numerics;
using TruckLib.ScsMap;

// Lists every EV charger on the combined ATS map (base_map + all owned state DLCs, extracted into one folder)
// with the state (source archive), nearest city and nearest company.
//   dotnet run [-- <path to usa.mbd>]
// Charger model tokens / prefab models were identified by their charger textures (see ev_chargers/README.md):
// every model whose materials use ca_e_charger*, e-charger-station* or ia_charging_station_power_box* textures.
var mbd = args.FirstOrDefault(a => a.EndsWith(".mbd")) ?? @"C:\ATSExtract\map_all\map\usa.mbd";
var chargerModels = new HashSet<string> { "2124", "3a029", "ibe_09018", "ia_5e004" };
var chargerPrefabs = new HashSet<string>();   // prefab tokens with built-in chargers - none in ATS 1.61 (6024 prefabs checked)

var sectorSource = new Dictionary<string, string>();
var srcCsv = Path.Combine(Path.GetDirectoryName(Path.GetDirectoryName(mbd)!)!, "sector_source.csv");
if (File.Exists(srcCsv))
    foreach (var l in File.ReadLines(srcCsv).Skip(1)) { var p = l.Split(','); sectorSource[p[0]] = p[1]; }
string Source(Vector3 p)
{
    int sx = (int)Math.Floor(p.X / 4000f), sz = (int)Math.Floor(p.Z / 4000f);
    var key = $"sec{(sx < 0 ? "-" : "+")}{Math.Abs(sx):D4}{(sz < 0 ? "-" : "+")}{Math.Abs(sz):D4}";
    return sectorSource.TryGetValue(key, out var s) ? s : "?";
}

var map = Map.Open(mbd);
Console.WriteLine($"{mbd}: {map.MapItems.Count} items");
var chargers = new List<(string kind, string model, Vector3 pos, ulong uid)>();
var cities = new List<(string name, Vector3 pos)>();
var companies = new List<(string name, Vector3 pos)>();
foreach (var item in map.MapItems.Values)
{
    switch (item)
    {
        case Model m when chargerModels.Contains(m.Name.String): chargers.Add(("model", m.Name.String, m.Node.Position, m.Uid)); break;
        case Prefab pf when chargerPrefabs.Contains(pf.Model.String): chargers.Add(("prefab", pf.Model.String, pf.Nodes[0].Position, pf.Uid)); break;
        case CityArea c: cities.Add((c.Name.String, c.Node.Position + new Vector3(c.Width / 2, 0, c.Height / 2))); break;
        case Company co: companies.Add((co.CompanyName.String, co.Node.Position)); break;
    }
}
string Near(List<(string name, Vector3 pos)> l, Vector3 p)
{
    var b = l.MinBy(x => Vector3.Distance(new(x.pos.X, 0, x.pos.Z), new(p.X, 0, p.Z)));
    return $"{b.name} ({Vector3.Distance(new(b.pos.X, 0, b.pos.Z), new(p.X, 0, p.Z)) / 1000 * 19:F1} km)";
}
var rows = new List<string> { "kind,model,x,y,z,uid,source,nearest_city,nearest_company" };
foreach (var c in chargers.OrderBy(c => Source(c.pos)).ThenBy(c => c.pos.X))
    rows.Add(string.Format(CultureInfo.InvariantCulture, "{0},{1},{2:F1},{3:F1},{4:F1},{5:X},{6},{7},{8}",
        c.kind, c.model, c.pos.X, c.pos.Y, c.pos.Z, c.uid, Source(c.pos), Near(cities, c.pos), Near(companies, c.pos)));
var outCsv = Path.GetFullPath(Path.Combine("..", "data", "chargers.csv"));   // run from ev_chargers\ChargerFinder
Directory.CreateDirectory(Path.GetDirectoryName(outCsv)!);
File.WriteAllLines(outCsv, rows);
Console.WriteLine($"{rows.Count - 1} chargers, {cities.Count} city areas, {companies.Count} companies -> {outCsv}");
foreach (var r in rows) Console.WriteLine(r);

// ---- --place (EXPERIMENTAL): plug icon (world map / GPS) at every charger site, in ONE extra sector file ----
// Re-saving SCS sectors with TruckLib 0.5.1 crashed ATS 1.61 (it re-encodes every item). So nothing of SCS is re-saved:
// all icons/markers go into one new sector at an unused coordinate (items outside their sector's bounds only give an
// "Excessive sector boundary" warning). The .desc (40 bytes in 1.61, TruckLib writes 32) is copied from a game sector.
if (args.Contains("--place"))
{
    var posts = chargers.Where(c => c.model != "ia_5e004").Select(c => c.pos).ToList();
    var sites = new List<List<Vector3>>();
    foreach (var p in posts)
    {
        var s = sites.FirstOrDefault(s => s.Any(o => Vector2.Distance(new(o.X, o.Z), new(p.X, p.Z)) < 100));
        if (s != null) s.Add(p); else sites.Add(new() { p });
    }
    var ev = new Map();
    foreach (var s in sites)
    {
        var c = new Vector3(s.Average(p => p.X), s.Average(p => p.Y), s.Average(p => p.Z));
        var icon = MapOverlay.Add(ev, c, OverlayType.RoadName);   // world map / GPS icon (material/ui/map/road/road_ev_plug)
        icon.Look = "ev_plug";
        // no 3D marker: models are aux items, streamed only for the sector around the player - this sector is off the map
    }
    // unused sector coordinate next to the map (no SCS file is replaced)
    var used = map.Sectors.Keys.ToHashSet();
    var home = Enumerable.Range(0, 100).Select(i => new SectorCoordinate(-40 - i, -30)).First(c => !used.Contains(c));
    var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Static;
    var mt = typeof(Map);
    var far = mt.GetMethod("GetFarModelChildren", bf)!.Invoke(ev, null)!;
    var bySector = (System.Collections.IDictionary)mt.GetMethod("GetSectorItems", bf)!.Invoke(ev, new[] { far })!;
    object? merged = null;
    foreach (var si in bySector.Values)
    {
        if (merged == null) { merged = si; continue; }
        foreach (var list in new[] { "BaseItems", "AuxItems", "SndItems" })
        {
            var f = si.GetType().GetProperty(list) ?? throw new MissingMemberException(list);
            var dst = (System.Collections.IList)f.GetValue(merged)!;
            foreach (var it in (System.Collections.IList)f.GetValue(si)!) dst.Add(it);
        }
    }
    var nodes = mt.GetMethod("GetSectorNodes", bf)!.Invoke(null, new[] { merged!, far })!;
    var outDir = Path.GetFullPath(Path.Combine("..", "ev_marker", "mod", "map", "usa"));
    if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
    Directory.CreateDirectory(outDir);
    mt.GetMethod("SaveSector", bf)!.Invoke(ev, new object[] { home, outDir, merged!, nodes, Array.Empty<ulong>() });
    var name = Path.GetFileNameWithoutExtension(Sector.SectorFileNameFromSectorCoords(home));
    var anyDesc = Directory.GetFiles(Path.Combine(Path.GetDirectoryName(mbd)!, "usa"), "*.desc").First();
    File.Copy(anyDesc, Path.Combine(outDir, name + ".desc"));
    Console.WriteLine($"placed {ev.MapItems.Count} items ({sites.Count} sites, {posts.Count} posts) in new sector {name} -> {outDir}");
}
