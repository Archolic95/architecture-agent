"""Additional original topology/miter controls requested after API auditing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import uuid

import rhino3dm as r

from build_controls import OUTER, QUARTER_TURN, NAMESPACE, polyline, prism, transform


def rectangle(x0, y0, x1, y1):
    return ((x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0))


def malformed(holes):
    result = r.Extrusion()
    assert result.SetPathAndUp(r.Point3d(0, 0, 0), r.Point3d(0, 0, 4), r.Vector3d(0, 1, 0))
    assert result.SetOuterProfile(polyline(OUTER), True)
    for hole in holes:
        assert result.AddInnerProfile(polyline(hole))
    assert result.Transform(transform(QUARTER_TURN))
    # The control specifically witnesses the insufficiency of these native flags.
    assert result.IsValid and result.IsSolid
    return result


def build(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    mitered = prism()
    mitered.MiterPlaneNormalAtStart = r.Vector3d(0.2, 0, 1)
    assert mitered.IsMiteredAtStart and mitered.IsValid and mitered.IsSolid
    controls = {
        "outside_hole": malformed([rectangle(7, 0.5, 8, 1.5)]),
        "touching_hole": malformed([rectangle(0, 0.5, 1, 1.5)]),
        "overlapping_holes": malformed([rectangle(0.5, 0.5, 1.5, 1.5), rectangle(1, 0.75, 2, 1.75)]),
        "mitered_prism": mitered,
    }
    destinations = [directory / (name + ".3dm") for name in controls]
    destinations.append(directory / "manifest.json")
    if any(path.exists() for path in destinations):
        raise FileExistsError("Negative control output already exists")
    manifest = {
        "kind": "independent_native_section_negative_controls",
        "author": "Architecture Agent contributors",
        "rhino3dm_version": r.__version__,
        "native_rhino_execution": False,
        "architectural_acceptance": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_source_sha256": hashlib.sha256(Path(__file__).with_name("build_controls.py").read_bytes()).hexdigest(),
        "files": [],
    }
    for name, geometry in controls.items():
        document = r.File3dm()
        document.Settings.ModelUnitSystem = r.UnitSystem.Millimeters
        document.Settings.ModelAbsoluteTolerance = 1e-8
        attributes = r.ObjectAttributes()
        attributes.Id = uuid.uuid5(NAMESPACE, name)
        attributes.Name = name
        identity = str(document.Objects.AddExtrusion(geometry, attributes))
        path = directory / (name + ".3dm")
        assert document.Write(str(path), 8)
        reopened = r.File3dm.Read(str(path))
        objects = list(reopened.Objects)
        assert len(objects) == 1
        actual = objects[0].Geometry
        assert isinstance(actual, r.Extrusion) and actual.IsValid and actual.IsSolid
        manifest["files"].append({
            "name": name, "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "units": "Millimeters", "object_ids": [identity],
            "geometry_types": ["Extrusion"], "valid": [True], "solid": [True],
            "profile_count": actual.ProfileCount,
            "mitered_start": actual.IsMiteredAtStart,
            "expected_error": "mitered_extrusion" if name == "mitered_prism" else "unsupported_profile",
        })
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output), indent=2))
