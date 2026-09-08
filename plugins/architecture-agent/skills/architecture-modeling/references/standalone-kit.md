# Standalone geometry kit

Ordinary CPython creates exact native Rhino extrusions and matched preview meshes. Rhino, Grasshopper and Compute are not used during generation. This is a small planar-prism backend, not a RhinoCommon implementation or complete building-design system.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build_demo.py --output output/house --length 14 --storey-height 3.2
.venv/bin/python cpu_preview.py output/house
.venv/bin/python test_kit.py
```

The demonstration is an independently authored two-storey courtyard study: 182 native Extrusions, 3,308 preview triangles, real courtyard and stair holes, façade openings, an inclined stair and a timber terrace. It is an open-plan geometry fixture; it has no complete residential room program or code-compliance claim. `length` ranges13–18m and `storey_height`3–4m. Default floor level is0.22m above ground.

```python
from geometry_kit import Scene

scene = Scene("Study")
scene.add_profile(
    "floor.ground", [(0,0),(8,0),(8,6),(0,6)],
    holes_xy=[[(3,2),(5,2),(5,4),(3,4)]],
    z0=0, height=0.25, layer="Floor slabs",
    color=(0.86,0.84,0.79,1),
    metadata={"role":"floor_slab","storey":0,"opening":"courtyard"},
)
scene.add_box("column.01", [0,0,0.25,0.2,0.2,3.25], layer="Columns")
scene.export("output/study")
```

`add_profile` accepts finite simple XY polygons, concavity and interior holes; `add_box` uses `[x0,y0,z0,x1,y1,z1]`. Coordinates are metres, Z-up. `transform` is an optional4×4 affine matrix with positive determinant. The operation refuses placements not representable as a native Extrusion. Nonfinite coordinates, invalid/self-intersecting rings, zero dimensions, reflected/singular placements and duplicate component IDs raise exceptions. An unsuccessful add does not insert a partial part. Scene export writes the specified output directory; callers should give each revision its own directory.

Outputs:

- `model.3dm`: editable native Extrusions, layers, materials and deterministic object IDs.
- `model.preview.json`: explicit Z-up triangle preview in the architecture viewer's decoded scene format.
- `model.preview.glb`: the same preview in standard Y-up glTF.
- `scene.json`: retained profiles, placements, metadata and dependency versions.
- `validation.json`: native reopen, profile/hole correspondence, solid validity, mesh winding/volume, native/preview identity and file hashes.

The demo additionally retains `parameters.json`, its source files and timing. Re-executing the retained program supplies parametric editing; the `.3dm` alone is baked geometry. Unaffected component IDs stay stable across parameter changes. This helper does not generate a GH program.

**Preview delivery is explicitly separate.** The current rhino3dm wheel's `Extrusion.SetMesh` transfers an existing mesh pointer into another owning pointer; a minimal CPython reproduction crashes during teardown. This kit does not call it. Native files therefore have no cached display meshes. Browser integrations should use the supplied preview JSON after checking its hash against `validation.json`, while downloading/opening the matching native file. Do not claim that an arbitrary3dm-only browser loader can display these fresh extrusions. Upstream implementation: [bnd_beam.cpp](https://github.com/mcneel/rhino3dm/blob/8.x/src/bindings/bnd_beam.cpp).

Validation establishes individual solid geometry and preview correspondence. It does not establish inter-part collision freedom, room coverage, structure, fabrication tolerances or code compliance. The original house includes thin architectural glazing by design; its courtyard is an intentional open-to-sky void. CPU section views clip triangles without capping the cut. Curved/swept/freeform geometry and general3D boolean operations require another backend. Python wheel metadata is8.32.1 while its imported module reports8.32.2; the pinned distribution version is authoritative for installation.

The separate optional `native_sections.py` command creates filled 2D solid sections directly from supported native Extrusions. It preserves source units and holes, unions solid occupancy, and rejects unsupported or unresolved input instead of falling back to a mesh clip. It does not draw construction-material boundaries or geometry behind the cut. See [native section commands, outputs and limitations](native-sections.md). CPU and browser cuts remain uncapped.
