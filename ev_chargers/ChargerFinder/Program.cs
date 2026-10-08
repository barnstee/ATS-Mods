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
const float IconOffset = 50f;                        // m east of the charger: plug icon next to (not on) the gas symbol
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
        var icon = MapOverlay.Add(ev, c + new Vector3(IconOffset, 0, 0), OverlayType.RoadName);   // beside the gas symbol of the refuel spots   // world map / GPS icon (material/ui/map/road/road_ev_plug)
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

// ---- --fuel-test <charger uid>: gas trigger prefab at one charger, spliced into its REAL sector ----
// The game only activates gas spots (prefab spawn point GasStation) in the sectors around the truck, so the prefab
// must be in the charger's own sector. Re-saving that sector with TruckLib 0.5.1 breaks it (float rounding of node
// positions, items moved between files/sectors), so the original files are kept byte for byte: the new prefab, its
// service item and their nodes are appended to the item/node lists of .base and the payload to .data.
var ftIdx = Array.IndexOf(args, "--fuel-test");
const float BaySide = 3.5f;                          // m from the charger post to the middle of the parking bay
if (ftIdx >= 0)
{
    // comma separated charger post uids; all chargers of one sector are spliced in one go
    var uids = args[ftIdx + 1] == "all"                 // all charger posts (power boxes are not chargers)
        ? chargers.Where(c => c.model != "ia_5e004").Select(c => c.uid).ToList()
        : args[ftIdx + 1].Split(',', StringSplitOptions.RemoveEmptyEntries).Select(s => Convert.ToUInt64(s, 16)).ToList();
    var ppd = TruckLib.Models.Ppd.PrefabDescriptor.Open(@"C:\ATSExtract\prefab\gas\us_gas_station_trigger_only.ppd");
    var sp = ppd.SpawnPoints.First(s => s.Type.ToString() == "GasStation").Position - ppd.Nodes[0].Position;
    var srcDir = Path.Combine(Path.GetDirectoryName(mbd)!, "usa");
    var dstDir = Path.GetFullPath(Path.Combine("..", "ev_marker", "mod", "map", "usa"));
    Directory.CreateDirectory(dstDir);
    foreach (var grp in uids.Select(u => (Model)map.MapItems[u]).GroupBy(m => Map.GetSectorOfCoordinate(m.Node.Position)))
    {
        var gm = new Map();
        var auxNodes = new List<Node>();                   // no aux items any more (plug sign removed)
        foreach (var post in grp)
        {
            var rot = post.Node.Rotation;
            // one gas spot in each parking bay beside the charger island (post-local z = sideways; x is along the island), not on the post itself
            foreach (var side in new[] { -BaySide, BaySide })
            {
                var spot = post.Node.Position + Vector3.Transform(new Vector3(0, 0, side), rot);
                var pos = spot - Vector3.Transform(new Vector3(sp.X, 0, sp.Z), rot);   // prefab placed so its GasStation spot is in the bay
                var gas = Prefab.Add(gm, pos, "02003", ppd, rot);
                gas.Variant = "default"; gas.Look = "asphalt"; gas.TerrainShadows = false;   // as SCS's own "us gas / trigger only" instances
                Console.WriteLine($"fuel test: charger {post.Uid:X}: gas spot {(side < 0 ? "left " : "right")} at {spot} (prefab {gas.Uid:X})");
            }
        }
        var secName = Path.GetFileNameWithoutExtension(Sector.SectorFileNameFromSectorCoords(grp.Key));
        var newBase = gm.MapItems.Values.Where(x => x.ItemFile == ItemFile.Base).OrderBy(x => x.Uid).ToList();
        var newAux = gm.MapItems.Values.Where(x => x.ItemFile == ItemFile.Aux).OrderBy(x => x.Uid).ToList();
        var baseNodes = gm.Nodes.Values.OfType<Node>().Where(n => !auxNodes.Contains(n)).OrderBy(x => x.Uid).ToList();
        // TruckLib writes a placeholder k-DOP bounding box (1..2 near the map origin) for new items; the game culls and
        // activates items by that box, so new items were never drawn / never triggered. Give every new item a real box.
        foreach (var it in gm.MapItems.Values) SectorSplice.SetBounds(it, gm);
        SectorSplice.Patch(Path.Combine(srcDir, secName), Path.Combine(dstDir, secName), newBase, baseNodes, newAux, auxNodes);
        Console.WriteLine($"  -> {newBase.Count} base items, {baseNodes.Count} base nodes, {newAux.Count} aux items spliced into {secName}");
    }
}

static class SectorSplice
{
    // k-DOP box of a new item: its nodes +-8 m horizontally, 3 m below to 8 m above. Axes as written by SCS:
    // x, y, z, (x+z)/2, (x-z)/2 (checked against the bounds of an original charger post).
    public static void SetBounds(MapItem item, Map owner)
    {
        var pts = owner.Nodes.Values.OfType<Node>().Where(n => n.ForwardItem == item || n.BackwardItem == item).Select(n => n.Position).ToList();
        if (item is Service sv) pts.Add(sv.Node.Position);
        if (pts.Count == 0) throw new InvalidOperationException($"no nodes for {item.Uid:X}");
        const float H = 8, Down = 3, Up = 8;
        float x0 = pts.Min(p => p.X) - H, x1 = pts.Max(p => p.X) + H, z0 = pts.Min(p => p.Z) - H, z1 = pts.Max(p => p.Z) + H;
        float y0 = pts.Min(p => p.Y) - Down, y1 = pts.Max(p => p.Y) + Up;
        var kdop = typeof(MapItem).GetProperty("Kdop", BF)!.GetValue(item)!;
        var mins = (float[])kdop.GetType().GetProperty("Minimums", BF)!.GetValue(kdop)!;
        var maxs = (float[])kdop.GetType().GetProperty("Maximums", BF)!.GetValue(kdop)!;
        float[] lo = { x0, y0, z0, (x0 + z0) / 2, (x0 - z1) / 2 }, hi = { x1, y1, z1, (x1 + z1) / 2, (x1 - z0) / 2 };
        Array.Copy(lo, mins, 5); Array.Copy(hi, maxs, 5);
    }

    static readonly System.Reflection.BindingFlags BF = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Instance;
    static object Ser(ItemType t) => typeof(Map).Assembly.GetTypes().First(x => x.Name == "MapItemSerializerFactory").GetMethod("Get", BF)!.Invoke(null, new object[] { t })!;

    // copies <src>.* to <dst>.*: new base items + nodes appended to .base (payloads to .data), new aux items + nodes to .aux;
    // every original item and node stays byte for byte
    public static void Patch(string src, string dst, List<MapItem> baseItems, List<Node> baseNodes, List<MapItem> auxItems, List<Node> auxNodes, Func<MapItem, bool>? editAux = null)
    {
        foreach (var ext in new[] { "snd", "desc", "layer" })
            if (File.Exists(src + "." + ext)) File.Copy(src + "." + ext, dst + "." + ext, true);
        var orig = Splice(src + ".base", dst + ".base", baseItems, baseNodes);
        Splice(src + ".aux", dst + ".aux", auxItems, auxNodes, editAux);
        var d = File.ReadAllBytes(src + ".data");
        using var r = new BinaryReader(new MemoryStream(d));
        new Header().Deserialize(r);
        int hdrEnd = (int)r.BaseStream.Position;
        var entries = new List<(ulong uid, byte[] bytes)>();
        while (true)
        {
            long p0 = r.BaseStream.Position;
            var uid = r.ReadUInt64();
            if (uid == ulong.MaxValue) break;
            var it = orig[uid]; var ser = Ser(it.ItemType);
            ser.GetType().GetMethod("DeserializeDataPayload")!.Invoke(ser, new object[] { r, it });
            entries.Add((uid, d[(int)p0..(int)r.BaseStream.Position]));
        }
        bool sorted = entries.Zip(entries.Skip(1)).All(p => p.First.uid < p.Second.uid);
        foreach (var it in baseItems.Where(x => (bool)typeof(MapItem).GetProperty("HasDataPayload", BF)!.GetValue(x)!))
        {
            using var m = new MemoryStream(); using var w0 = new BinaryWriter(m);
            w0.Write(it.Uid); var ser = Ser(it.ItemType);
            ser.GetType().GetMethod("SerializeDataPayload")!.Invoke(ser, new object[] { w0, it }); w0.Flush();
            entries.Add((it.Uid, m.ToArray()));
        }
        using var ms2 = new MemoryStream(); using var w2 = new BinaryWriter(ms2);
        w2.Write(d, 0, hdrEnd);
        foreach (var x in (sorted ? entries.OrderBy(x => x.uid) : entries.AsEnumerable())) w2.Write(x.bytes);
        w2.Write(ulong.MaxValue); w2.Flush(); File.WriteAllBytes(dst + ".data", ms2.ToArray());
        Console.WriteLine($"  .data: {entries.Count} entries, original order sorted by uid: {sorted}");
    }

    // SCS keeps items and nodes sorted by uid (the game looks them up by binary search), so the new ones are merged in
    // at their sorted position; the bytes of every original item / node are copied unchanged
    static Dictionary<ulong, MapItem> Splice(string src, string dst, List<MapItem> items, List<Node> nodes, Func<MapItem, bool>? edit = null)
    {
        var b = File.ReadAllBytes(src);
        var orig = new Dictionary<ulong, MapItem>();
        using var r = new BinaryReader(new MemoryStream(b));
        new Header().Deserialize(r);
        int hdrEnd = (int)r.BaseStream.Position;
        var nItems = r.ReadUInt32();
        var all = new List<(ulong uid, byte[] bytes)>();
        for (int i = 0; i < nItems; i++)
        {
            long p0 = r.BaseStream.Position;
            var ser = Ser((ItemType)r.ReadInt32());
            var it = (MapItem)ser.GetType().GetMethod("Deserialize")!.Invoke(ser, new object[] { r })!;
            if (edit != null && edit(it))                       // changed original item: re-encode just this one
            {
                using var m2 = new MemoryStream(); using var w3 = new BinaryWriter(m2);
                w3.Write((int)it.ItemType); ser.GetType().GetMethod("Serialize")!.Invoke(ser, new object[] { w3, it }); w3.Flush();
                all.Add((it.Uid, m2.ToArray()));
            }
            else all.Add((it.Uid, b[(int)p0..(int)r.BaseStream.Position]));
            orig[it.Uid] = it;
        }
        foreach (var it in items)
        {
            using var m = new MemoryStream(); using var w0 = new BinaryWriter(m);
            w0.Write((int)it.ItemType); var ser = Ser(it.ItemType); ser.GetType().GetMethod("Serialize")!.Invoke(ser, new object[] { w0, it }); w0.Flush();
            all.Add((it.Uid, m.ToArray()));
        }
        var nNodes = r.ReadUInt32();
        var ctor = typeof(Node).GetConstructors(BF).First(c => c.GetParameters().Length == 1 && c.GetParameters()[0].ParameterType == typeof(bool));
        var allNodes = new List<(ulong uid, byte[] bytes)>();
        for (int i = 0; i < nNodes; i++)
        {
            long p0 = r.BaseStream.Position;
            var nd = (Node)ctor.Invoke(new object[] { false }); nd.Deserialize(r, null);
            allNodes.Add((nd.Uid, b[(int)p0..(int)r.BaseStream.Position]));
        }
        int nodesEnd = (int)r.BaseStream.Position;
        foreach (var n in nodes)
        {
            using var m = new MemoryStream(); using var w0 = new BinaryWriter(m); n.Serialize(w0); w0.Flush();
            allNodes.Add((n.Uid, m.ToArray()));
        }
        using var ms = new MemoryStream(); using var w = new BinaryWriter(ms);
        w.Write(b, 0, hdrEnd);
        w.Write((uint)all.Count); foreach (var x in all.OrderBy(x => x.uid)) w.Write(x.bytes);
        w.Write((uint)allNodes.Count); foreach (var x in allNodes.OrderBy(x => x.uid)) w.Write(x.bytes);
        w.Write(b, nodesEnd, b.Length - nodesEnd);                 // vis-area children list, unchanged
        w.Flush(); File.WriteAllBytes(dst, ms.ToArray());
        return orig;
    }
}
