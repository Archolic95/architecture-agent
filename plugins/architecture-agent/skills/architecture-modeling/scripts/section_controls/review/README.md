# Original numerical regression fixtures

These two small native files were independently authored to expose numerical
failures during section development. They contain no architectural source data.
The public copies were re-encoded in memory to remove private save-path metadata.
Native object IDs, attributes, complete geometry encodings, world profiles,
path endpoints, caps, holes, validity and units were checked unchanged. The
hashes below identify these public copies; the original files remain retained
outside the distribution.
The focused tests pin their byte hashes and verify their native profiles before
checking the section behavior. The source and fixtures use the package Apache-2.0
license. Offline rhino3dm file operations were used; no Rhino application was run.

| Retained file | SHA-256 |
| --- | --- |
| `conditioning-original-0.3dm` | `9dd217e82499d7b45eb3b75341fd8e622a6350ec600553e9a78b4c63056e54e6` |
| `tangent-triangle-original.3dm` | `fd849883a69e5841cdf135819287408d5de1469c82fbe91490485a427c20d0f1` |

The conditioning file's original construction used a capped unit-square
Extrusion, then set its path as follows. This excerpt preserves its geometry
construction; the unrelated review execution is omitted.

```python
import math
import rhino3dm as r

points = [r.Point3d(x, y, 0) for x, y in
          ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0))]
extrusion = r.Extrusion.Create(r.PolylineCurve(points), 1, True)
assert extrusion.SetPathAndUp(
    r.Point3d(0, 0, 0),
    r.Point3d(math.sin(1e-12), 0, math.cos(1e-12)),
    r.Vector3d(0, 1, 0),
)
```

Its stored bottom profile is `(0,0,0), (1,0,-1e-12), (1,1,-1e-12),
(0,1,0), (0,0,0)` and its path displacement is `(1e-12,0,1)`. The section
at X=0.5 has essentially unit area, but dividing by a path component of 1e-12
cannot establish 1e-7 accuracy in double precision. It must report
`numerical_instability`.

The triangle file has the closed XY profile `(0,0), (1,0), (1,1), (0,0)`
and a capped unit-height extrusion along +Z. Both files declare metres.
The following is a portable reconstruction recipe for its verified profile,
not a claim that the original ad hoc creation script was retained:

```python
points = [r.Point3d(x, y, 0) for x, y in
          ((0, 0), (1, 0), (1, 1), (0, 0))]
extrusion = r.Extrusion.Create(r.PolylineCurve(points), 1, True)
```

For the triangle, `0 <= Y <= X <= 1`, so X=c has section area c for
`0 < c < 1`. X=0 is empty tangency; X=5e-15 is an unresolved interior
sliver and must reject; X=1e-6 must retain a positive-area rectangle.
These expectations come from the stated profiles, independently of the section
implementation. Regeneration may change native file metadata and byte hashes;
the shipped tests read the retained files rather than replacing them.
