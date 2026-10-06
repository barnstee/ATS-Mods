using System.Globalization;
using System.Numerics;
using TruckLib.ScsMap;

// Lists every placed EV charger model on the ATS map (base + state DLC maps) with nearest city and company.
var mbds = args.Length > 0 ? args : new[] {
    @"C:\ATSExtract\map_extract\map\usa.mbd", @"C:\ATSExtract\map_dlc\dlc_arizona\map\usa.mbd", @"C:\ATSExtract\map_dlc\dlc_nevada\map\usa.mbd",
    @"C:\ATSExtract\map_dlc\dlc_or\map\usa.mbd", @"C:\ATSExtract\map_dlc\dlc_wa\map\usa.mbd" };
var targets = new HashSet<string> { "ibe_09018", "2124", "3a029" };
var chargers = new Dictionary<ulong, (string model, Vector3 pos, string src)>();
var cities = new List<(string name, Vector3 pos)>();
var companies = new List<(string name, Vector3 pos)>();
foreach (var mbd in mbds)
{
    var src = Path.GetFileName(Path.GetDirectoryName(Path.GetDirectoryName(mbd))!);
    var map = Map.Open(mbd);
    foreach (var item in map.MapItems.Values)
    {
        switch (item)
        {
            case Model m when targets.Contains(m.Name.String): chargers[m.Uid] = (m.Name.String, m.Node.Position, src); break;
            case CityArea c: cities.Add((c.Name.String, c.Node.Position + new Vector3(c.Width / 2, 0, c.Height / 2))); break;
            case Company co: companies.Add((co.CompanyName.String, co.Node.Position)); break;
        }
    }
    Console.WriteLine($"{src}: {map.MapItems.Count} items");
}
string Near(List<(string name, Vector3 pos)> l, Vector3 p) { var b = l.MinBy(x => Vector3.Distance(new(x.pos.X, 0, x.pos.Z), new(p.X, 0, p.Z))); return $"{b.name} ({Vector3.Distance(new(b.pos.X, 0, b.pos.Z), new(p.X, 0, p.Z)) / 1000 * 19:F1} km)"; }
var rows = new List<string> { "model,x,y,z,uid,map,nearest_city,nearest_company" };
foreach (var (uid, c) in chargers.OrderBy(k => k.Value.pos.X))
    rows.Add(string.Format(CultureInfo.InvariantCulture, "{0},{1:F1},{2:F1},{3:F1},{4:X},{5},{6},{7}", c.model, c.pos.X, c.pos.Y, c.pos.Z, uid, c.src, Near(cities, c.pos), Near(companies, c.pos)));
var outCsv = Path.GetFullPath(Path.Combine("..", "data", "chargers.csv"));   // run from ev_chargers\ChargerFinder
Directory.CreateDirectory(Path.GetDirectoryName(outCsv)!);
File.WriteAllLines(outCsv, rows);
Console.WriteLine($"{rows.Count - 1} chargers, {cities.Count} city areas, {companies.Count} companies");
foreach (var r in rows) Console.WriteLine(r);
