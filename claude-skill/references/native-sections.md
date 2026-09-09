# Filled 2D solid sections

`scripts/native_sections.py` reads a native `.3dm` directly and draws the solid
occupancy intersecting a world X, Y or Z coordinate plane. It needs no mesh
sidecar, retained builder, Rhino process or new dependency beyond the pinned
Python environment. This is separate from `cpu_preview.py` and the browser's
uncapped 3D display cuts.

Run from the repository root, choosing a fresh destination for each view:

```sh
.architecture-venv/bin/python scripts/native_sections.py output/courtyard/model.3dm --axis y --coordinate 3 --output output/courtyard/sections-filled/y-3-r001 --title "Filled 2D solid section"
```

Choose a plane from the actual model. `--axis z` gives a horizontal section;
`--axis x` and `--axis y` give vertical sections. `--up` selects a signed world
axis in the plane, for example `--up=-y` for a horizontal section. `--reverse`
reverses the look direction. The JSON and image state the actual look, right
and up axes. Arbitrary plane normals are unsupported.

Coordinates and `--tolerance` use the file's declared source units, with no
automatic conversion to metres. The default linear tolerance is `1e-7` source
units; choose it for the model's scale. Areas use squared source units. The
modeling helper normally writes metres, but this reader also preserves other
native unit systems.

The command writes `section.png` and `section.json` only after the section
calculation succeeds. The JSON records input path and SHA-256, units, plane,
tolerance, object IDs and cut areas, polygon rings and holes, boundary policy,
and the observed rhino3dm module version. Its current schema is
`native-polygonal-sections.prototype.1`. The installed distribution is pinned
to rhino3dm 8.32.1 even though its module reports 8.32.2. Inspect the image and
receipt together; successful geometry checks do not establish source fidelity.

| Outcome | Meaning and CLI behavior |
| --- | --- |
| `ready` | Positive filled area; PNG, JSON and a stdout summary; exit 0. |
| `empty` | Supported input with a resolved zero-area cut; empty-view PNG, JSON and summary; exit 0. |
| `rejected` | A `SectionError` receipt on stderr with code, message and object ID when available; exit 2. No successful section is emitted. |

Keep rejection receipts. Existing output folders are refused. Invalid command
syntax also exits nonzero with argparse usage text; filesystem/rendering failures
must not be presented as a completed section.

Supported geometry consists of valid, fully capped, unmitered native Extrusions
whose closed polygon profiles, holes and world placement form a translated
prism. Rotated prisms can be sectioned by the world coordinate planes. Every
object is checked, including hidden and off-plane objects; there is no layer
filter. Breps, meshes, instances, curved profiles, open solids, miters and
invalid hole topology reject the entire file. Typical codes include
`unsupported_geometry`, `unsupported_profile`, `uncapped_extrusion`,
`mitered_extrusion` and `non_prismatic`.

Cap or side-face coincidence within tolerance raises `ambiguous_boundary`.
Unresolved near-parallel cuts or interior slivers raise `numerical_instability`.
The command never silently shifts the plane, repairs polygons, samples curves,
substitutes bounds, or skips an unsupported object. “Exact requested plane” in
the image means the requested coordinate was used; arithmetic and polygon
booleans remain floating point, with conservative rejection gates.

The fill unions occupancy across objects. It does not retain construction-material
boundaries, colors, assemblies or hatches, and includes no projected geometry
behind the cut. “Material” in the renderer means solid occupancy. This is an
inspection view, not a dimensioned architectural or BIM drawing.
