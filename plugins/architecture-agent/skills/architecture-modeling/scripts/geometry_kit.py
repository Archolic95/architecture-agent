"""Small agent-facing planar-prism scene kit. No Rhino application required."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import time
import uuid

import numpy as np
import rhino3dm as rhino
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.validation import explain_validity
import trimesh

NAMESPACE = uuid.UUID("070c89d3-d544-4828-bef0-a7594ca3d682")


def polygon(outer, holes=()):
    """Validated XY polygon. Never repairs or silently drops invalid regions."""
    rings = [np.asarray(r, dtype=float) for r in [outer, *holes]]
    if any(r.ndim != 2 or r.shape[1] != 2 or len(r) < 3 or not np.isfinite(r).all() for r in rings):
        raise ValueError("Profiles require finite XY rings with at least three vertices")
    p = Polygon(rings[0], rings[1:])
    if not p.is_valid or p.is_empty or p.area <= 1e-10:
        raise ValueError("Invalid profile: " + explain_validity(p))
    return orient(p, sign=1.0)


def mesh_to_rhino(mesh):
    result = rhino.Mesh()
    for vertex in mesh.vertices:
        result.Vertices.Add(*map(float, vertex))
    for face in mesh.faces:
        result.Faces.AddFace(*map(int, face))
    result.Normals.ComputeNormals()
    if not result.IsValid:
        raise ValueError("Display mesh failed native validation")
    return result


def rhino_mesh_to_trimesh(mesh):
    vertices = [[v.X, v.Y, v.Z] for v in mesh.Vertices]
    faces = []
    for face in mesh.Faces:
        a, b, c, d = face
        faces.append([a, b, c])
        if c != d:
            faces.append([a, c, d])
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def check_mesh(mesh, volume):
    if not np.isfinite(mesh.vertices).all() or not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Preview must be finite, closed and consistently wound")
    if mesh.volume <= 0 or not math.isclose(float(mesh.volume), volume, rel_tol=2e-6, abs_tol=1e-7):
        raise ValueError(f"Volume mismatch: mesh={mesh.volume}, analytic={volume}")


class Scene:
    def __init__(self, title="Architecture model"):
        self.title = str(title)
        self.parts = {}

    def add_profile(self, component_id, outer_xy, *, holes_xy=(), z0=0.0,
                    height=1.0, layer="Architecture", color=(0.8, 0.8, 0.8, 1.0),
                    transform=None, metadata=None):
        """Create exact capped native extrusion plus matching triangulation.

        Coordinates are metres, Z-up. Affine placement must be finite,
        orientation-preserving, and representable by Rhino's Extrusion type.
        Returns component_id. Existing IDs are never overwritten.
        """
        if not isinstance(component_id, str) or not component_id or component_id in self.parts:
            raise ValueError("Component ID must be a new nonempty string")
        if not math.isfinite(z0) or not math.isfinite(height) or height <= 1e-6:
            raise ValueError("Extrusion elevation and positive height must be finite")
        color = np.asarray(color, dtype=float)
        if color.shape != (4,) or not np.isfinite(color).all() or np.any(color < 0) or np.any(color > 1):
            raise ValueError("Color must be RGBA in [0, 1]")
        matrix = np.eye(4) if transform is None else np.asarray(transform, dtype=float)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]):
            raise ValueError("Placement must be a finite affine matrix")
        det = float(np.linalg.det(matrix[:3, :3]))
        if det <= 1e-12:
            raise ValueError("Placement must be nonsingular and orientation-preserving")
        p = polygon(outer_xy, holes_xy)
        curve = lambda ring: rhino.PolylineCurve([rhino.Point3d(x, y, z0) for x, y in ring.coords])
        extrusion = rhino.Extrusion.Create(curve(p.exterior), height, True)
        if extrusion is None:
            raise ValueError("Native extrusion construction failed")
        for ring in p.interiors:
            # AddInnerProfile uses the extrusion's local XY profile coordinates.
            # Create chooses its own local origin; transform world XY to that plane.
            plane = extrusion.GetProfilePlane(0)
            inner_world = curve(ring)
            inner_world.Transform(rhino.Transform.PlaneToPlane(plane, rhino.Plane.WorldXY()))
            if not extrusion.AddInnerProfile(inner_world):
                raise ValueError("Native extrusion rejected inner profile")
        native_matrix = rhino.Transform(1.0)
        for i in range(4):
            for j in range(4):
                setattr(native_matrix, f"M{i}{j}", float(matrix[i, j]))
        if not extrusion.Transform(native_matrix) or not extrusion.IsValid or not extrusion.IsSolid:
            raise ValueError("Affine placement is not representable as a valid solid extrusion")
        mesh = trimesh.creation.extrude_polygon(p, height=height, engine="earcut")
        mesh.apply_translation([0, 0, z0])
        mesh.apply_transform(matrix)
        expected_volume = float(p.area * height * det)
        check_mesh(mesh, expected_volume)
        bounds = extrusion.GetBoundingBox()
        native_bounds = [[bounds.Min.X, bounds.Min.Y, bounds.Min.Z], [bounds.Max.X, bounds.Max.Y, bounds.Max.Z]]
        if not np.allclose(native_bounds, mesh.bounds, atol=2e-6, rtol=1e-7):
            raise ValueError("Native/preview bounds differ")
        manifest = dict(id=component_id, layer=str(layer), rgba=color.tolist(), z0=z0, height=height,
                        outer_xy=list(map(list, p.exterior.coords)), holes_xy=[list(map(list, r.coords)) for r in p.interiors],
                        transform=matrix.tolist(), analytic_volume=expected_volume, bounds=mesh.bounds.tolist(),
                        metadata=dict(metadata or {}), native_type="Extrusion", triangles=len(mesh.faces))
        # Commit only after construction and every validation succeeds.
        # rhino3dm 8.32's SetMesh has an upstream ownership/double-free defect.
        # Keep exact native geometry and explicitly linked preview artifacts apart.
        self.parts[component_id] = {"native": extrusion, "mesh": mesh, "record": manifest}
        return component_id

    def add_box(self, component_id, bounds, **kwargs):
        values = np.asarray(bounds, dtype=float)
        if values.shape != (6,) or not np.isfinite(values).all():
            raise ValueError("Box bounds must be [x0, y0, z0, x1, y1, z1]")
        x0, y0, z0, x1, y1, z1 = map(float, values)
        if min(x1-x0, y1-y0, z1-z0) <= 1e-6:
            raise ValueError("Box dimensions must be positive")
        return self.add_profile(component_id, [(x0,y0),(x1,y0),(x1,y1),(x0,y1)], z0=z0, height=z1-z0, **kwargs)

    def export(self, output_dir):
        started = time.perf_counter()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        if not self.parts:
            raise ValueError("Cannot export an empty scene")
        doc = rhino.File3dm()
        doc.ApplicationName = "Standalone Architecture Kit"
        doc.Settings.ModelUnitSystem = rhino.UnitSystem.Meters
        doc.Settings.ModelAbsoluteTolerance = .001
        layer_ids, material_ids = {}, {}
        preview = trimesh.Scene()
        browser = {"objects": [], "layers": [], "definitions": [], "warnings": [], "units": "Meters", "sourceCount": len(self.parts),
                   "previewKind": "explicit_generated_mesh_sidecar", "nativeGeometry": "exact_extrusions_without_cached_meshes"}
        z_to_y = np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]], dtype=float)
        for cid, part in self.parts.items():
            rec = part["record"]
            rgba = tuple(int(round(v * 255)) for v in rec["rgba"])
            if rec["layer"] not in layer_ids:
                layer = rhino.Layer(); layer.Name = rec["layer"]; layer.Color = rgba
                layer_ids[rec["layer"]] = doc.Layers.Add(layer)
                browser["layers"].append({"index": layer_ids[rec["layer"]], "name": rec["layer"], "visible": True, "color": dict(zip("rgba", rgba))})
            if rgba not in material_ids:
                material = rhino.Material(); material.Name = "RGBA " + str(rgba)
                material.DiffuseColor = rgba; material.Transparency = 1 - rec["rgba"][3]
                material_ids[rgba] = doc.Materials.Add(material)
            attrs = rhino.ObjectAttributes()
            attrs.Id = uuid.uuid5(NAMESPACE, self.title + ":" + cid)
            attrs.Name = cid; attrs.LayerIndex = layer_ids[rec["layer"]]
            attrs.MaterialIndex = material_ids[rgba]; attrs.MaterialSource = rhino.ObjectMaterialSource.MaterialFromObject
            attrs.ObjectColor = rgba; attrs.ColorSource = rhino.ObjectColorSource.ColorFromObject
            attrs.SetUserString("component_id", cid)
            attrs.SetUserString("component_metadata", json.dumps(rec["metadata"], sort_keys=True))
            attrs.SetUserString("geometry_kind", "exact_planar_extrusion")
            doc.Objects.AddExtrusion(part["native"], attrs)
            native_preview = part["mesh"]
            positions = native_preview.triangles.reshape((-1,3))
            normals = np.repeat(native_preview.face_normals, 3, axis=0)
            browser["objects"].append({"id": str(attrs.Id), "name": cid, "layer": attrs.LayerIndex, "visible": True,
                "definitionObject": False, "color": dict(zip("rgba",rgba)), "kind": "Mesh", "opacity": rec["rgba"][3],
                "materialFromParent": False, "userStrings": [["component_id",cid],["geometry_kind","exact_planar_extrusion"]],
                "data": {"metadata":{"type":"BufferGeometry"},"data":{"attributes":{
                    "position":{"itemSize":3,"type":"Float32Array","array":positions.ravel().tolist()},
                    "normal":{"itemSize":3,"type":"Float32Array","array":normals.ravel().tolist()}}}}})
            mesh = native_preview.copy(); mesh.visual.vertex_colors = rgba
            mesh.apply_transform(z_to_y)
            preview.add_geometry(mesh, node_name=cid, geom_name=cid)
        native_path = out / "model.3dm"
        if not doc.Write(str(native_path), 8):
            raise ValueError("Native 3dm export failed")
        preview.export(out / "model.preview.glb")
        reopened = rhino.File3dm.Read(str(native_path))
        if reopened is None or len(reopened.Objects) != len(self.parts):
            raise ValueError("Native file reopen/object count failed")
        validated = []
        for obj in reopened.Objects:
            cid = obj.Attributes.GetUserString("component_id")
            part = self.parts[cid]; geo = obj.Geometry
            if not isinstance(geo, rhino.Extrusion) or not geo.IsValid or not geo.IsSolid:
                raise ValueError("Native reopen lost exact solid extrusion")
            if geo.ProfileCount != 1+len(part["record"]["holes_xy"]):
                raise ValueError("Native reopen lost profile holes")
            rec = part["record"]
            for index, ring in enumerate([rec["outer_xy"], *rec["holes_xy"]]):
                expected = np.asarray([[x,y,rec["z0"],1] for x,y in ring]) @ np.asarray(rec["transform"]).T
                native_ring = geo.Profile3d(index, 0).TryGetPolyline()
                if native_ring is None:
                    raise ValueError("Native profile ceased to be polygonal")
                actual = np.asarray([[p.X,p.Y,p.Z] for p in native_ring])
                distances = np.linalg.norm(expected[:,:3,None]-actual.T[None,:,:],axis=1)
                if max(distances.min(axis=0).max(),distances.min(axis=1).max()) > 2e-6:
                    raise ValueError("Serialized native profile differs from the preview source")
            bb = geo.GetBoundingBox()
            if not np.allclose([[bb.Min.X,bb.Min.Y,bb.Min.Z],[bb.Max.X,bb.Max.Y,bb.Max.Z]],part["mesh"].bounds,atol=2e-6):
                raise ValueError("Serialized native bounds changed")
            mesh = part["mesh"]
            validated.append({"id": cid, "native_id": str(obj.Attributes.Id), "native_type": "Extrusion", "valid": True,
                              "solid": True, "mesh_closed": True, "outward_winding": True, "triangles": len(mesh.faces), "volume": float(mesh.volume),
                              "preview_delivery": "explicit_sidecar", "cached_render_mesh": geo.GetMesh(rhino.MeshType.Render) is not None})
        glb = trimesh.load(out / "model.preview.glb", force="scene", process=False)
        if set(glb.geometry) != set(self.parts):
            raise ValueError("GLB reopen changed component IDs")
        for cid, mesh in glb.geometry.items():
            original = self.parts[cid]["mesh"].copy(); original.apply_transform(z_to_y)
            if not np.allclose(mesh.bounds, original.bounds, atol=2e-6):
                raise ValueError("GLB/native bounds disagree")
        (out / "model.preview.json").write_text(json.dumps(browser,separators=(",",":"))+"\n")
        manifest = {"title": self.title, "units": "metres", "native_up": "Z", "glb_up": "Y",
                    "parts": [p["record"] for p in self.parts.values()],
                    "dependencies": {p: importlib.metadata.version(p) for p in ["rhino3dm","shapely","numpy","trimesh","mapbox-earcut"]}}
        (out / "scene.json").write_text(json.dumps(manifest, indent=2) + "\n")
        receipt = {"objects": len(validated), "native_process_used": False, "preview_delivery": "explicit_sidecar_due_to_upstream_SetMesh_ownership_bug", "export_validation_seconds": time.perf_counter()-started,
                   "parts": validated, "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [native_path,out/"model.preview.glb",out/"model.preview.json",out/"scene.json"]}}
        (out / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
