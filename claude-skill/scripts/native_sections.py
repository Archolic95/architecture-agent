"""Native polygonal Extrusion sections; original, bounded source prototype.

No mesh cache, bounding-box replacement, native Rhino process, or fixture oracle
is used. The public entry point returns filled material regions in a declared
world-axis section frame. See README.md for scope and numerical policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import rhino3dm
from shapely import affinity
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, LineString, Polygon
from shapely.ops import unary_union
from shapely.validation import explain_validity


class SectionError(ValueError):
    def __init__(self, code, message, object_id=None):
        super().__init__(message)
        self.code = code
        self.object_id = object_id

    def receipt(self):
        return {"status": "rejected", "code": self.code,
                "message": str(self), "object_id": self.object_id}


def _xyz(point):
    return (float(point.X), float(point.Y), float(point.Z))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _mul(a, s):
    return tuple(x * s for x in a)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _length(a):
    return math.hypot(*a)


def _signed_axis(vector):
    return next(("+" if x > 0 else "-") + "xyz"[i]
                for i, x in enumerate(vector) if x)


def _frame(axis, coordinate, up, reverse, tolerance):
    if axis not in ("x", "y", "z"):
        raise SectionError("invalid_input", "axis must be x, y, or z")
    if (not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool)
            or not math.isfinite(coordinate)):
        raise SectionError("invalid_input", "coordinate must be finite")
    if (not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool)
            or not math.isfinite(tolerance) or tolerance <= 0):
        raise SectionError("invalid_input", "tolerance must be finite and positive")
    if not isinstance(reverse, bool):
        raise SectionError("invalid_input", "reverse must be a Boolean")
    up = up if up is not None else ("+y" if axis == "z" else "+z")
    if up not in ("+x", "-x", "+y", "-y", "+z", "-z") or up[1] == axis:
        raise SectionError("invalid_input", "up must be a signed axis in the cut plane")
    up_vector = tuple((1 if up[0] == "+" else -1) if a == up[1] else 0
                      for a in "xyz")
    sign = {"x": -1, "y": 1, "z": -1}[axis] * (-1 if reverse else 1)
    look = tuple(sign if a == axis else 0 for a in "xyz")
    right = _cross(look, up_vector)
    return {"axis": axis, "coordinate": float(coordinate),
            "up": list(up_vector), "right": list(right), "look": list(look),
            "up_axis": _signed_axis(up_vector), "right_axis": _signed_axis(right),
            "look_axis": _signed_axis(look)}


def _polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for part in geometry.geoms for p in _polygons(part)]
    return []


def _lines(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    if geometry.geom_type in ("MultiLineString", "GeometryCollection"):
        return [p for part in geometry.geoms for p in _lines(part)]
    return []


def _profile_prism(extrusion, object_id, tolerance):
    def reject(code, message):
        raise SectionError(code, message, object_id)

    if not isinstance(extrusion, rhino3dm.Extrusion):
        reject("unsupported_geometry", f"Expected Extrusion, got {type(extrusion).__name__}")
    if extrusion.IsMiteredAtStart or extrusion.IsMiteredAtEnd:
        reject("mitered_extrusion", "Mitered Extrusions are outside this prototype")
    if (not extrusion.IsCappedAtBottom or not extrusion.IsCappedAtTop
            or extrusion.CapCount != 2 or not extrusion.IsSolid):
        reject("uncapped_extrusion", "Both native caps and solid status are required")
    if not extrusion.IsValid or extrusion.ProfileCount < 1:
        reject("unsupported_profile", "Invalid native Extrusion or missing outer profile")
    displacement = _sub(_xyz(extrusion.PathEnd), _xyz(extrusion.PathStart))
    if not all(map(math.isfinite, displacement)) or _length(displacement) <= tolerance:
        reject("non_prismatic", "Path displacement is non-finite or below tolerance")
    plane = extrusion.GetProfilePlane(0.0)
    if plane is None:
        reject("non_prismatic", "Missing native profile plane")
    origin, u, v, normal = map(_xyz, (plane.Origin, plane.XAxis, plane.YAxis, plane.ZAxis))
    if (not all(math.isfinite(x) for vector in (origin, u, v, normal) for x in vector)
            or any(abs(_length(vector) - 1) > 1e-12 for vector in (u, v, normal))
            or _length(_sub(_cross(u, v), normal)) > 1e-12):
        reject("non_prismatic", "Native profile frame must be finite and orthonormal")
    if max(abs(_dot(displacement, u)), abs(_dot(displacement, v))) > tolerance:
        reject("non_prismatic", "Unmitered path must be perpendicular to its profile")
    rings, bottom_rings, top_rings = [], [], []
    for profile_index in range(extrusion.ProfileCount):
        samples = []
        for parameter in (0.0, 0.5, 1.0):
            curve = extrusion.Profile3d(profile_index, parameter)
            if curve is None or not curve.IsValid or not curve.IsClosed:
                reject("unsupported_profile", f"Profile {profile_index} is not valid and closed")
            polyline = curve.TryGetPolyline()
            if polyline is None:
                reject("unsupported_profile", f"Profile {profile_index} is curved; no approximation used")
            points = [_xyz(p) for p in polyline]
            if (len(points) < 4 or not all(math.isfinite(x) for p in points for x in p)
                    or _length(_sub(points[0], points[-1])) > tolerance):
                reject("unsupported_profile", f"Profile {profile_index} is not a finite closed polygon")
            points.pop()  # Only the explicit closing point; never simplify the native ring.
            if any(_length(_sub(a, b)) <= tolerance
                   for a, b in zip(points, points[1:] + points[:1])):
                reject("unsupported_profile", f"Profile {profile_index} has an edge at/below tolerance")
            samples.append(points)
        bottom, middle, top = samples
        if len({len(p) for p in samples}) != 1:
            reject("non_prismatic", "Profile vertex counts differ along the native path")
        for p, m, q in zip(bottom, middle, top):
            if (_length(_sub(_sub(q, p), displacement)) > tolerance
                    or _length(_sub(m, _mul(_add(p, q), 0.5))) > tolerance):
                reject("non_prismatic", "Profiles do not correspond by native path translation")
        for parameter, points in zip((0.0, 0.5, 1.0), samples):
            displaced_origin = _add(origin, _mul(displacement, parameter))
            if any(abs(_dot(_sub(p, displaced_origin), normal)) > tolerance for p in points):
                reject("non_prismatic", "A profile does not lie in its translated common plane")
        rings.append([(_dot(_sub(p, origin), u), _dot(_sub(p, origin), v)) for p in bottom])
        bottom_rings.append(bottom)
        top_rings.append(top)

    ring_polygons = [Polygon(ring) for ring in rings]
    for ring in ring_polygons:
        if not ring.is_valid or ring.area <= tolerance * tolerance:
            reject("unsupported_profile", "Profile rings must be simple and have resolved nonzero area")
    outer, holes = ring_polygons[0], ring_polygons[1:]
    for i, hole in enumerate(holes):
        if not outer.contains(hole) or not outer.boundary.disjoint(hole):
            reject("unsupported_profile", "Inner profile must be strictly inside the outer profile")
        if any(not hole.disjoint(other) for other in holes[:i]):
            reject("unsupported_profile", "Inner profiles touch or overlap")
    polygon = Polygon(rings[0], rings[1:])
    if not polygon.is_valid or polygon.area <= tolerance * tolerance:
        reject("unsupported_profile", "Invalid profile topology: " + explain_validity(polygon))
    return {"polygon": polygon, "origin": origin, "u": u, "v": v,
            "displacement": displacement, "bottom": bottom_rings, "top": top_rings,
            "object_id": object_id}


def _clip_halfplane(vertices, a, b, bound):
    """Clip an enclosing rectangle by a*u+b*v <= bound (no polygon sampling)."""
    clipped = []
    if not vertices:
        return clipped
    for p, q in zip(vertices, vertices[1:] + vertices[:1]):
        fp, fq = a * p[0] + b * p[1] - bound, a * q[0] + b * q[1] - bound
        if fp <= 0:
            clipped.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            fraction = fp / (fp - fq)
            clipped.append((p[0] + fraction * (q[0] - p[0]),
                            p[1] + fraction * (q[1] - p[1])))
        elif fp > 0 and fq == 0:
            clipped.append(q)
    return clipped


def _cut_prism(prism, frame, tolerance):
    axis = "xyz".index(frame["axis"])
    coordinate = frame["coordinate"]
    all_points = [p for ring in prism["bottom"] + prism["top"] for p in ring]
    # Distinguish exact tangency from a thin, genuine slice using roundoff only.
    # If the world coordinates themselves cannot resolve the requested tolerance,
    # reject instead of pretending that profile checks are precise at that scale.
    roundoff = 32 * math.ulp(max(1.0, abs(coordinate), *(abs(x) for p in all_points for x in p)))
    if roundoff >= tolerance:
        raise SectionError("invalid_input", "World coordinates cannot resolve this tolerance; rebase the model or choose a coarser tolerance", prism["object_id"])
    faces = [prism["bottom"][0], prism["top"][0]]
    for bottom, top in zip(prism["bottom"], prism["top"]):
        for i in range(len(bottom)):
            j = (i + 1) % len(bottom)
            faces.append([bottom[i], bottom[j], top[j], top[i]])
    if any(all(abs(p[axis] - coordinate) <= tolerance for p in face) for face in faces):
        raise SectionError("ambiguous_boundary", "Cut is coincident with a cap or side face within tolerance; choose an explicit offset", prism["object_id"])
    minimum, maximum = min(p[axis] for p in all_points), max(p[axis] for p in all_points)
    if coordinate <= minimum or coordinate >= maximum:
        return GeometryCollection()
    if min(coordinate - minimum, maximum - coordinate) <= roundoff:
        raise SectionError("numerical_instability", "Cut is strictly inside the prism but too close to a tangency to resolve; choose an explicit offset", prism["object_id"])

    polygon = prism["polygon"]
    origin, u, v, displacement = (prism[key] for key in ("origin", "u", "v", "displacement"))
    right, up = frame["right"], frame["up"]
    a, b, d, k = u[axis], v[axis], displacement[axis], coordinate - origin[axis]
    min_u, min_v, max_u, max_v = polygon.bounds
    padding = max(max_u - min_u, max_v - min_v, 1.0)
    rectangle = [(min_u - padding, min_v - padding), (max_u + padding, min_v - padding),
                 (max_u + padding, max_v + padding), (min_u - padding, max_v + padding)]

    if d != 0:
        # Near-parallel cuts create a narrow profile strip and amplify error by
        # 1/d on the way back to the section plane. Refuse unresolved arithmetic
        # rather than silently snapping a nonzero path component to zero.
        amplification = max(1.0, _length(displacement) / abs(d))
        if not math.isfinite(amplification) or amplification * roundoff >= tolerance:
            raise SectionError("numerical_instability", "Near-parallel section mapping cannot resolve the requested tolerance; this prototype needs a better-conditioned cut", prism["object_id"])
        # A section of a translated prism is its profile restricted to 0 <= t <= 1.
        low, high = sorted((k, k - d))
        strip = _clip_halfplane(rectangle, a, b, high)
        strip = _clip_halfplane(strip, -a, -b, -low)
        if len(strip) < 3:
            return GeometryCollection()
        clipped = polygon.intersection(Polygon(strip))
        mapped_origin = _add(origin, _mul(displacement, k / d))
        mapped_u = _sub(u, _mul(displacement, a / d))
        mapped_v = _sub(v, _mul(displacement, b / d))
        matrix = [_dot(mapped_u, right), _dot(mapped_v, right),
                  _dot(mapped_u, up), _dot(mapped_v, up),
                  _dot(mapped_origin, right), _dot(mapped_origin, up)]
        return unary_union(_polygons(affinity.affine_transform(clipped, matrix)))

    # The plane runs along the prism path. Intersect each material interval in
    # the profile, then sweep that interval between the two native endpoints.
    squared = a * a + b * b
    if squared < 1e-24:
        raise SectionError("non_prismatic", "Section/profile frame is numerically unresolved", prism["object_id"])
    center = ((min_u + max_u) / 2, (min_v + max_v) / 2)
    correction = (k - a * center[0] - b * center[1]) / squared
    center = (center[0] + a * correction, center[1] + b * correction)
    norm = math.sqrt(squared)
    direction = (-b / norm, a / norm)
    radius = max(math.dist(center, corner) for corner in rectangle) + padding
    endpoints = [(center[0] + sign * radius * direction[0],
                  center[1] + sign * radius * direction[1]) for sign in (-1, 1)]
    intersection = polygon.intersection(LineString(endpoints))
    regions = []
    for interval in _lines(intersection):
        p, q = interval.coords[0], interval.coords[-1]
        start = _add(origin, _add(_mul(u, p[0]), _mul(v, p[1])))
        end = _add(origin, _add(_mul(u, q[0]), _mul(v, q[1])))
        vertices = [start, end, _add(end, displacement), _add(start, displacement)]
        region = Polygon([(_dot(vertex, right), _dot(vertex, up)) for vertex in vertices])
        if region.area > 0:
            regions.append(region)
    return unary_union(regions)


def section_file(path, axis="z", coordinate=0.0, up=None, reverse=False, tolerance=1e-7):
    """Return {geometry, report}; reject unsupported objects anywhere in the file.

    geometry is a Shapely polygon collection of material in absolute screen UV.
    report is JSON-safe, including all polygon rings, units, plane and input hash.
    """
    frame = _frame(axis, coordinate, up, reverse, tolerance)
    try:
        source = Path(path).resolve()
        payload = source.read_bytes()
        model = rhino3dm.File3dm.FromByteArray(payload)
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise SectionError("invalid_input", f"Cannot read native 3dm: {error}") from error
    if model is None:
        raise SectionError("invalid_input", "Cannot decode native 3dm")
    try:
        # Validate the whole input before performing cuts. A mixed model cannot
        # silently drop unsupported geometry that happens to lie off this plane.
        prisms = []
        for obj in model.Objects:
            prism = _profile_prism(obj.Geometry, str(obj.Attributes.Id), tolerance)
            prism["name"] = obj.Attributes.Name
            prisms.append(prism)
        regions, objects = [], []
        for prism in prisms:
            region = _cut_prism(prism, frame, tolerance)
            if not region.is_valid:
                raise SectionError("non_prismatic", "Invalid intersection: " + explain_validity(region), prism["object_id"])
            regions.extend(_polygons(region))
            objects.append({"id": prism["object_id"], "name": prism["name"],
                            "profiles": len(prism["bottom"]), "cut_area": region.area})
        geometry = unary_union(regions)
        if not geometry.is_valid:
            raise SectionError("non_prismatic", "Invalid union: " + explain_validity(geometry))
    except GEOSException as error:
        raise SectionError("non_prismatic", f"Polygon operation failed: {error}") from error
    polygons = sorted(_polygons(geometry), key=lambda p: (*p.bounds, -p.area))
    report = {
        "schema": "native-polygonal-sections.prototype.1",
        "status": "ready" if polygons else "empty",
        "input_path": str(source), "input_sha256": hashlib.sha256(payload).hexdigest(),
        "units": model.Settings.ModelUnitSystem.name, "area": geometry.area,
        "area_units": "squared source units", "tolerance": tolerance,
        "plane": frame, "polygon_count": len(polygons),
        "hole_count": sum(len(p.interiors) for p in polygons),
        "object_count": len(prisms), "objects": objects,
        "bounds": list(geometry.bounds) if polygons else None,
        "regions": [{"outer": list(p.exterior.coords),
                     "holes": [list(ring.coords) for ring in p.interiors]} for p in polygons],
        "method": "native world profiles + analytic prism/plane intersection + planar polygon boolean",
        "boundary_policy": "reject cap/side coincidence within tolerance; no plane offset",
        "object_policy": "all model objects regardless of visibility; unsupported input rejects entire file",
        "runtime": {"rhino3dm": rhino3dm.__version__},
    }
    json.dumps(report, allow_nan=False)
    return {"geometry": geometry, "report": report}


def render_section(result, output_path, title="Native material section", width=1200, height=900):
    """Draw filled material only, with empty holes, equal axis scale and plane labels."""
    from PIL import Image, ImageChops, ImageDraw, ImageFont

    if width < 600 or height < 450:
        raise SectionError("invalid_input", "Image size must be at least 600 by 450")
    report = result["report"]
    supersampling = 2
    image = Image.new("RGB", (width * supersampling, height * supersampling), "white")
    draw = ImageDraw.Draw(image)
    def font(size):
        return ImageFont.load_default(size=size * supersampling)
    def text(position, value, size=14, fill="#334155"):
        draw.text(tuple(round(c * supersampling) for c in position), value, font=font(size), fill=fill)
    def line(points, fill="#e2e8f0", thickness=1):
        draw.line([tuple(round(c * supersampling) for c in point) for point in points],
                  fill=fill, width=thickness * supersampling)
    plane = report["plane"]
    text((40, 22), title, 25, "#0f172a")
    text((40, 61), f"{plane['axis'].upper()} = {plane['coordinate']:g} {report['units']}   |   look {plane['look_axis']}   |   right {plane['right_axis']}   up {plane['up_axis']}", 16)
    text((40, height - 60), f"Filled material: {report['area']:.8g} squared source units   |   {report['polygon_count']} regions, {report['hole_count']} holes   |   {report['object_count']} native objects", 14)
    text((40, height - 34), "Native polygonal Extrusions / exact requested plane / no surfaces behind the cut", 13)
    if result["geometry"].is_empty:
        text((width / 2 - 115, height / 2), "No material at this plane", 21)
    else:
        x0, y0, x1, y1 = report["bounds"]
        available = (85, 122, width - 70, height - 122)
        scale = min((available[2] - available[0]) / (x1 - x0),
                    (available[3] - available[1]) / (y1 - y0))
        center = ((available[0] + available[2]) / 2, (available[1] + available[3]) / 2)
        def screen(x, y):
            return (center[0] + (x - (x0 + x1) / 2) * scale,
                    center[1] - (y - (y0 + y1) / 2) * scale)
        def pixels(coords):
            return [tuple(round(c * supersampling) for c in screen(x, y)) for x, y in coords]
        raw_step = max(x1 - x0, y1 - y0) / 6
        magnitude = 10 ** math.floor(math.log10(raw_step))
        step = next(value * magnitude for value in (1, 2, 5, 10) if value * magnitude >= raw_step)
        for index in range(math.ceil(x0 / step), math.floor(x1 / step) + 1):
            x = index * step
            start, end = screen(x, y0), screen(x, y1)
            line([start, end])
            text((start[0] - 12, start[1] + 10), f"{x:g}", 12)
        for index in range(math.ceil(y0 / step), math.floor(y1 / step) + 1):
            y = index * step
            start, end = screen(x0, y), screen(x1, y)
            line([start, end])
            text((start[0] - 48, start[1] - 7), f"{y:g}", 12)
        mask = Image.new("L", image.size, 0)
        for polygon in _polygons(result["geometry"]):
            component = Image.new("L", image.size, 0)
            pen = ImageDraw.Draw(component)
            pen.polygon(pixels(polygon.exterior.coords), fill=255)
            for hole in polygon.interiors:
                pen.polygon(pixels(hole.coords), fill=0)
            mask = ImageChops.lighter(mask, component)
        image.paste("#172c40", mask=mask)
        draw = ImageDraw.Draw(image)
        text((width - 210, height - 93), f"horizontal {plane['right_axis']}  /  vertical {plane['up_axis']}", 12)
    image.resize((width, height), Image.Resampling.LANCZOS).save(output_path, "PNG")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--axis", choices=("x", "y", "z"), required=True)
    parser.add_argument("--coordinate", type=float, required=True)
    parser.add_argument("--up", help="signed world axis in plane; for a negative value use --up=-y")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--tolerance", type=float, default=1e-7, help="linear source units")
    parser.add_argument("--output", type=Path, required=True, help="new output directory; will not overwrite")
    parser.add_argument("--title", default="Native material section")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise SectionError("invalid_input", "Output directory already exists; choose a fresh path")
        result = section_file(args.model, args.axis, args.coordinate, args.up, args.reverse, args.tolerance)
        args.output.mkdir(parents=True, exist_ok=False)
        render_section(result, args.output / "section.png", title=args.title)
        (args.output / "section.json").write_text(json.dumps(result["report"], indent=2, allow_nan=False) + "\n")
        print(json.dumps({"status": result["report"]["status"], "output": str(args.output.resolve()),
                          "area": result["report"]["area"], "units": result["report"]["units"]}))
        return 0
    except SectionError as error:
        print(json.dumps(error.receipt()), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
