# Independent native section controls

These original synthetic controls exercise a narrow polygonal-extrusion section
reader. They are unrelated to architectural source packets or model acceptance.
The builder imports only rhino3dm and the standard library; it never imports the
section engine. Native files are retained in `native/`, with hashes and stable
object IDs in `native/manifest.json`.

The local profile is the concave polygon `(0,0), (6,0), (6,2), (3,2), (3,5),
(0,5)`, minus the square `[0.5,1.5] × [0.5,1.5]`. Its area is
`6×2 + 3×3 − 1 = 20`. Extrusion height is 4. The quarter-turn transform is
`X=11−v, Y=−7+u, Z=3+w`. The tilted transform is
`X=11+4u/5+3w/5, Y=−7+v, Z=3−3u/5+4w/5`.

| Control | Independent expectation |
|---|---|
| Cap-parallel, translated and rotated prism | At Z=5: area 20, one polygon and one square hole; asymmetric placement tests the full coordinate frame. |
| World-axis cut through the hole | At Y=−6: X intervals `[6,9.5]` and `[10.5,11]`, Z interval `[3,7]`; two polygons, total area 16. At X=10: Y intervals `[−7,−6.5]` and `[−5.5,−1]`, total area 20. |
| Oblique cut through the tilted prism | At Z=3.4: `w=1/2+3u/4`, so `u≤14/3`; profile area becomes `2×14/3+9−1=52/3`. Its section mapping is `X=113/10+5u/4`, so area is `65/3` and hole area is `5/4`. |
| Empty and nominally tangent cuts | Z=19 and tilted X=18.3 are disjoint. The tilted file's stored maximum X is 18.200000000000003, so decimal X=18.2 is strictly inside by one floating-point step; the updated precision policy rejects it as `numerical_instability` rather than claiming empty. |
| Explicit boundary policy | Exact cap or side-face coincidence, including a hole side face, must raise `ambiguous_boundary`. Cuts within the configured linear tolerance are also rejected; sufficiently offset cuts use their actual coordinate, not a silent perturbation. |
| Curved profile negatives | Both a circular outer profile and a circular inner profile are valid native capped Extrusions, but must raise `unsupported_profile`; no polygon approximation. |
| Uncapped negative | A valid uncapped polygonal Extrusion must raise `uncapped_extrusion`. |
| Unsupported and mixed geometry negatives | A native solid Brep and a file containing both an Extrusion and a Brep must raise `unsupported_geometry`; a file cannot partially succeed by skipping the unsupported object. |

The first prism uses millimeters and the tilted prism centimeters deliberately.
The numerical areas above remain in squared source units; reporting meters or
silently converting would be wrong. Tests also reverse the look direction and
invert screen up, checking the expected reflection of every polygon and hole.

The construction API is documented by McNeel in
[Extrusion](https://mcneel.github.io/rhino3dm/python/api/Extrusion.html) and
[Transform](https://mcneel.github.io/rhino3dm/python/api/Transform.html). The actual
retained files were written and reopened with rhino3dm 8.32.2. This is offline
file-library execution, with no Rhino application, native UI, or model author
invocation. Rendering and visual inspection remain separate checks.

Run the tests from the repository root with the scripts directory on the import path:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/architecture-agent/skills/architecture-modeling/scripts \
  .architecture-venv/bin/python -m unittest discover \
  -s plugins/architecture-agent/skills/architecture-modeling/scripts/section_controls/tests -v
```

The builder writes a fresh destination only; it refuses to replace existing
retained control files. No exact hash is promised across regeneration because
the native file container may encode creation metadata. The recorded hashes
identify the retained bytes used by these tests.

The later API audit justified four additional negative files in
`native-negatives/`: a hole outside the outer loop, a hole touching its boundary,
two overlapping holes, and a mitered prism. The first three deliberately reopen
with `IsValid=True` and `IsSolid=True`; these flags do not establish valid filled
profile topology. All three must produce `unsupported_profile`. The mitered
solid must produce `mitered_extrusion`. Their independent construction source is
`build_negative_controls.py`, with separate retained hashes that identify the
two control groups.

After independent numerical review, tests also read two original reviewer-owned
files under `../review/`, without regenerating them. Their byte hashes and native
profiles are pinned. `conditioning-original-0.3dm` has a path X component of
1e-12; double-precision division by that component cannot establish the requested
1e-7 accuracy, so it must report `numerical_instability`.
`tangent-triangle-original.3dm` has profile `0<=Y<=X<=1` and height 1. Its X=c
section has exact analytical area c: c=0 is empty tangency, c=5e-15 is an
unresolved strictly interior cut requiring rejection, and c=1e-6 must retain a
positive-area rectangle. These files were authored by the independent reviewer;
their inputs and the stated expectations were separately checked for these tests.

For distribution, the two builders and manifests use public contributor attribution in place of an internal task identifier. The original builder hashes remain in `original_source_sha256` fields; `source_sha256` identifies the bundled source. All thirteen public native fixtures were re-encoded in memory to remove private save-path metadata. Complete native geometry and object-attribute encodings, IDs, profiles, caps, holes and units were verified unchanged; manifest and test hashes identify the sanitized public copies. Numerical test expectations are unchanged. See the [reviewer fixtures' provenance and construction](../review/README.md). These original sources and fixtures use the package Apache-2.0 license.
