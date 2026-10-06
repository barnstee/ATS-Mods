import sys, bpy, addon_utils
from mathutils import Vector
addon_utils.enable("io_scs_tools", default_set=True)
files = sys.argv[sys.argv.index("--") + 1:]
for f in files:
    bpy.ops.wm.read_homefile(); [bpy.data.objects.remove(o) for o in list(bpy.data.objects)]
    import os; bpy.ops.scs_tools.import_pim(directory=os.path.dirname(f), files=[{"name": os.path.basename(f)}])
    print("\n=== " + f)
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type != "MESH":
            print("  [%s] %s loc=%s" % (o.type, o.name, tuple(round(v, 3) for v in o.matrix_world.translation)))
            continue
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
        hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
        mats = sorted({s.material.name for s in o.material_slots if s.material})
        print("  %-40s v=%6d min=%s max=%s mats=%s" % (o.name, len(o.data.vertices), lo, hi, mats))
