"""Independently authored section controls; never imports the section engine.

Only rhino3dm and the Python standard library are used. These small synthetic
prisms are software controls, not architectural fixtures or acceptance models.
Coordinates remain in each file's declared source units.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import uuid

import rhino3dm as r


OUTER = ((0, 0), (6, 0), (6, 2), (3, 2), (3, 5), (0, 5), (0, 0))
HOLE = ((0.5, 0.5), (0.5, 1.5), (1.5, 1.5), (1.5, 0.5), (0.5, 0.5))
QUARTER_TURN = ((0, -1, 0, 11), (1, 0, 0, -7), (0, 0, 1, 3))
TILT = ((0.8, 0, 0.6, 11), (0, 1, 0, -7), (-0.6, 0, 0.8, 3))
NAMESPACE = uuid.UUID("6da2753d-3723-41d3-b1ee-5d9932fcba2b")


def polyline(points):
    return r.PolylineCurve([r.Point3d(x, y, 0) for x, y in points])


def transform(rows):
    result = r.Transform.Identity()
    for row, values in enumerate(rows):
        for column, value in enumerate(values):
            setattr(result, "M%d%d" % (row, column), value)
    return result


def prism(*, cap=True, curved_outer=False, curved_inner=False, rows=QUARTER_TURN):
    extrusion = r.Extrusion()
    assert extrusion.SetPathAndUp(r.Point3d(0, 0, 0), r.Point3d(0, 0, 4), r.Vector3d(0, 1, 0))
    outer = r.Circle(r.Point3d(3, 3, 0), 2).ToNurbsCurve() if curved_outer else polyline(OUTER)
    assert extrusion.SetOuterProfile(outer, cap)
    if not curved_outer:
        inner = r.Circle(r.Point3d(1, 1, 0), 0.4).ToNurbsCurve() if curved_inner else polyline(HOLE)
        assert extrusion.AddInnerProfile(inner)
    assert extrusion.Transform(transform(rows))
    assert extrusion.IsValid
    assert extrusion.IsSolid is cap
    assert extrusion.CapCount == (2 if cap else 0)
    return extrusion


def brep_box():
    result = r.Brep.CreateFromBox(r.Box(r.BoundingBox(20, 20, 0, 22, 23, 4)))
    assert result.IsValid and result.IsSolid
    return result


def build(directory):
    """Write a fresh set; refuse to overwrite existing retained controls."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    specifications = {
        "quarter_turn_prism": (r.UnitSystem.Millimeters, [prism()]),
        "tilted_prism": (r.UnitSystem.Centimeters, [prism(rows=TILT)]),
        "curved_outer": (r.UnitSystem.Millimeters, [prism(curved_outer=True)]),
        "curved_inner": (r.UnitSystem.Millimeters, [prism(curved_inner=True)]),
        "uncapped_prism": (r.UnitSystem.Millimeters, [prism(cap=False)]),
        "brep_only": (r.UnitSystem.Millimeters, [brep_box()]),
        "mixed_geometry": (r.UnitSystem.Millimeters, [prism(), brep_box()]),
    }
    manifest = {
        "kind": "independent_native_section_controls",
        "author": "Architecture Agent contributors",
        "rhino3dm_version": r.__version__,
        "geometry_source": "original synthetic polygons and explicit rigid transformations in this source",
        "native_rhino_execution": False,
        "architectural_acceptance": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "files": [],
        "primary_api_references": [
            "https://mcneel.github.io/rhino3dm/python/api/Extrusion.html",
            "https://mcneel.github.io/rhino3dm/python/api/Transform.html",
        ],
    }
    destinations = [directory / (name + ".3dm") for name in specifications]
    destinations.append(directory / "manifest.json")
    if any(path.exists() for path in destinations):
        raise FileExistsError("Control output already exists; use a fresh directory")
    for name, (units, geometries) in specifications.items():
        document = r.File3dm()
        document.Settings.ModelUnitSystem = units
        document.Settings.ModelAbsoluteTolerance = 1e-8
        ids = []
        for index, geometry in enumerate(geometries):
            attributes = r.ObjectAttributes()
            attributes.Id = uuid.uuid5(NAMESPACE, name + ":" + str(index))
            attributes.Name = name + ":" + str(index)
            attributes.SetUserString("control_origin", "independent_original")
            ids.append(str(document.Objects.Add(geometry, attributes)))
        path = directory / (name + ".3dm")
        assert document.Write(str(path), 8)
        reopened = r.File3dm.Read(str(path))
        assert reopened is not None
        actual = list(reopened.Objects)
        assert len(actual) == len(geometries)
        assert [type(item.Geometry).__name__ for item in actual] == [type(g).__name__ for g in geometries]
        manifest["files"].append({
            "name": name,
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "units": str(units).split(".")[-1],
            "object_ids": ids,
            "geometry_types": [type(item.Geometry).__name__ for item in actual],
            "valid": [item.Geometry.IsValid for item in actual],
            "solid": [item.Geometry.IsSolid for item in actual],
        })
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
