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

// ---- --place: put the plug icon (world map) and the plug marker model at every charger site, no map editor needed ----
// Charger posts within 100 m form one site (power boxes ia_5e004 are electrical cabinets, never next to a post).
// Only the sectors that get items are written, into ev_marker/mod/map/usa (packed into ev_chargers.scs).
if (args.Contains("--place"))
{
    var posts = chargers.Where(c => c.model != "ia_5e004").Select(c => c.pos).ToList();
    var sites = new List<List<Vector3>>();
    foreach (var p in posts)
    {
        var s = sites.FirstOrDefault(s => s.Any(o => Vector2.Distance(new(o.X, o.Z), new(p.X, p.Z)) < 100));
        if (s != null) s.Add(p); else sites.Add(new() { p });
    }
    var targets = sites.Select(s => Map.GetSectorOfCoordinate(s[0])).Distinct().ToList();
    var tmp = Path.Combine(Path.GetTempPath(), "ev_chargers_map");
    // load the target sectors plus their neighbours, add the items, save
    var load = targets.SelectMany(t => from dx in new[] { -1, 0, 1 } from dz in new[] { -1, 0, 1 } select new SectorCoordinate(t.X + dx, t.Z + dz))
                      .Distinct().Where(c => map.Sectors.ContainsKey(c)).ToList();
    var sub = Map.Open(mbd, load);
    foreach (var s in sites)
    {
        var c = new Vector3(s.Average(p => p.X), s.Average(p => p.Y), s.Average(p => p.Z));
        var icon = MapOverlay.Add(sub, c, OverlayType.RoadName);   // world map / GPS icon (material/ui/map/road/road_ev_plug)
        icon.Look = "ev_plug";
        Model.Add(sub, c + new Vector3(3, 0, 0), "ev_plug", "default", "default");   // green plug sign (model.ev_plug)
    }
    if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
    sub.Save(tmp, "usa", true);
    // TruckLib may store an item that crosses a sector border in the neighbour sector: ship that sector too, until
    // every original item of the shipped sectors is in the shipped files (otherwise e.g. a road would vanish in game)
    var ship = targets.ToHashSet();
    var savedBySector = new Dictionary<SectorCoordinate, Dictionary<ulong, MapItem>>();
    while (true)
    {
        var saved = Map.Open(Path.Combine(tmp, "usa.mbd"), ship.ToList()).MapItems;
        var lost = Map.Open(mbd, ship.ToList()).MapItems.Keys.Where(k => !saved.ContainsKey(k)).ToList();
        Console.WriteLine($"shipping {ship.Count} sectors, {lost.Count} items stored in other sectors");
        if (lost.Count == 0) break;
        foreach (var k in lost)
        {
            var sec = load.Where(c => !ship.Contains(c)).FirstOrDefault(c => (savedBySector.TryGetValue(c, out var m) ? m
                : savedBySector[c] = Map.Open(Path.Combine(tmp, "usa.mbd"), new List<SectorCoordinate> { c }).MapItems).ContainsKey(k));
            if (sec == default) throw new InvalidOperationException($"item {k:X} not found in the loaded sectors");
            ship.Add(sec);
        }
    }
    targets = ship.ToList();
    var outDir = Path.GetFullPath(Path.Combine("..", "ev_marker", "mod", "map", "usa"));
    if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
    Directory.CreateDirectory(outDir);
    var names = targets.Select(t => Path.GetFileNameWithoutExtension(Sector.SectorFileNameFromSectorCoords(t))).ToHashSet();
    var files = Directory.GetFiles(Path.Combine(tmp, "usa")).Where(f => names.Contains(Path.GetFileNameWithoutExtension(f))).ToList();
    foreach (var f in files) File.Copy(f, Path.Combine(outDir, Path.GetFileName(f)));
    Console.WriteLine($"placed icon + marker at {sites.Count} sites ({posts.Count} posts) in {targets.Count} sectors -> {outDir} ({files.Count} files)");
}
