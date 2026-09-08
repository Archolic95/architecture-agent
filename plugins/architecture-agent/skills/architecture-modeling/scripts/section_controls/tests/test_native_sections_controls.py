"""Independent synthetic controls for the native-file section prototype.

These are section software tests, not architectural acceptance tests.
Expected coordinates are authored here from elementary arithmetic, never
calculated by importing the section engine's clipping/projection internals.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

import rhino3dm
from shapely import affinity
from shapely.geometry import Polygon, MultiPolygon, box

from native_sections import SectionError, section_file


CONTROL_DIR = Path(__file__).resolve().parents[1] / "controls" / "native"
NEGATIVE_DIR = CONTROL_DIR.parent / "native-negatives"
REVIEW_DIR = CONTROL_DIR.parent.parent / "review"
PLAN = Polygon(
    [(11, -7), (11, -1), (9, -1), (9, -4), (6, -4), (6, -7)],
    [[(9.5, -6.5), (10.5, -6.5), (10.5, -5.5), (9.5, -5.5)]],
)
WORLD_Y_CUT = MultiPolygon([box(6, 3, 9.5, 7), box(10.5, 3, 11, 7)])
WORLD_X_CUT = MultiPolygon([box(-7, 3, -6.5, 7), box(-5.5, 3, -1, 7)])
OBLIQUE = Polygon(
    [(113 / 10, -7), (257 / 15, -7), (257 / 15, -5),
     (301 / 20, -5), (301 / 20, -2), (113 / 10, -2)],
    [[(477 / 40, -6.5), (527 / 40, -6.5), (527 / 40, -5.5), (477 / 40, -5.5)]],
)


class IndependentSectionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((CONTROL_DIR / "manifest.json").read_text())
        cls.controls = {entry["name"]: entry for entry in cls.manifest["files"]}
        negative_manifest = json.loads((NEGATIVE_DIR / "manifest.json").read_text())
        cls.negative_controls = {entry["name"]: entry for entry in negative_manifest["files"]}

    def run_cut(self, control="quarter_turn_prism", **kwargs):
        directory = NEGATIVE_DIR if control in self.negative_controls else CONTROL_DIR
        path = directory / (control + ".3dm")
        return section_file(path, **kwargs)

    def assert_region(self, result, expected, *, area, polygons, holes, units):
        geometry, report = result["geometry"], result["report"]
        self.assertTrue(geometry.is_valid)
        self.assertLess(geometry.symmetric_difference(expected).area, 1e-6)
        self.assertLess(geometry.hausdorff_distance(expected), 1e-7)
        self.assertAlmostEqual(geometry.area, area, places=7)
        self.assertEqual(report["status"], "ready")
        self.assertAlmostEqual(report["area"], area, places=7)
        self.assertEqual(report["polygon_count"], polygons)
        self.assertEqual(report["hole_count"], holes)
        self.assertEqual(report["units"], units)
        json.dumps(report, allow_nan=False)

    def assert_error(self, code, control="quarter_turn_prism", **kwargs):
        with self.assertRaises(SectionError) as caught:
            self.run_cut(control, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_retained_bytes_and_native_geometry_types(self):
        for name, entry in self.controls.items():
            with self.subTest(control=name):
                path = CONTROL_DIR / entry["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
                native = rhino3dm.File3dm.Read(str(path))
                self.assertIsNotNone(native)
                self.assertEqual([type(o.Geometry).__name__ for o in native.Objects], entry["geometry_types"])
                self.assertEqual([str(o.Attributes.Id) for o in native.Objects], entry["object_ids"])
                self.assertTrue(all(o.Geometry.IsValid for o in native.Objects))
        native = rhino3dm.File3dm.Read(str(CONTROL_DIR / "quarter_turn_prism.3dm"))
        geometry = list(native.Objects)[0].Geometry
        self.assertEqual(geometry.ProfileCount, 2)
        self.assertEqual(geometry.CapCount, 2)
        self.assertTrue(geometry.IsSolid)
        points = geometry.Profile3d(0, 0.0).TryGetPolyline()
        self.assertIsNotNone(points)
        self.assertEqual(
            [(p.X, p.Y, p.Z) for p in points],
            [(11, -7, 3), (11, -1, 3), (9, -1, 3), (9, -4, 3),
             (6, -4, 3), (6, -7, 3), (11, -7, 3)],
        )

    def test_translated_rotated_concavity_and_hole(self):
        result = self.run_cut(axis="z", coordinate=5)
        self.assert_region(result, PLAN, area=20, polygons=1, holes=1, units="Millimeters")
        self.assertEqual(result["report"]["input_sha256"], self.controls["quarter_turn_prism"]["sha256"])
        self.assertEqual(result["report"]["plane"]["look"], [0, 0, -1])
        self.assertEqual(result["report"]["plane"]["right"], [1, 0, 0])
        self.assertEqual(result["report"]["plane"]["up"], [0, 1, 0])
        self.assertAlmostEqual(Polygon(result["geometry"].interiors[0]).area, 1)

    def test_y_axis_cut_opens_hole_into_two_components(self):
        result = self.run_cut(axis="y", coordinate=-6)
        self.assert_region(result, WORLD_Y_CUT, area=16, polygons=2, holes=0, units="Millimeters")
        self.assertEqual(result["report"]["plane"]["right"], [1, 0, 0])
        self.assertEqual(result["report"]["plane"]["look"], [0, 1, 0])

    def test_x_axis_cut_uses_positive_y_screen_coordinate(self):
        result = self.run_cut(axis="x", coordinate=10)
        self.assert_region(result, WORLD_X_CUT, area=20, polygons=2, holes=0, units="Millimeters")
        self.assertEqual(result["report"]["plane"]["right"], [0, 1, 0])
        self.assertEqual(result["report"]["plane"]["look"], [-1, 0, 0])

    def test_oblique_cut_clips_cap_and_preserves_hole(self):
        result = self.run_cut("tilted_prism", axis="z", coordinate=3.4)
        self.assert_region(result, OBLIQUE, area=65 / 3, polygons=1, holes=1, units="Centimeters")
        self.assertAlmostEqual(Polygon(result["geometry"].interiors[0]).area, 5 / 4, places=7)

    def test_reverse_reflects_geometry_without_recentering(self):
        result = self.run_cut(axis="z", coordinate=5, reverse=True)
        expected = affinity.scale(PLAN, xfact=-1, yfact=1, origin=(0, 0))
        self.assert_region(result, expected, area=20, polygons=1, holes=1, units="Millimeters")
        self.assertEqual(result["report"]["plane"]["look"], [0, 0, 1])
        self.assertEqual(result["report"]["plane"]["right"], [-1, 0, 0])

    def test_signed_up_changes_both_screen_axes(self):
        result = self.run_cut(axis="z", coordinate=5, up="-y")
        expected = affinity.scale(PLAN, xfact=-1, yfact=-1, origin=(0, 0))
        self.assert_region(result, expected, area=20, polygons=1, holes=1, units="Millimeters")
        self.assertEqual(result["report"]["plane"]["up"], [0, -1, 0])

    def test_disjoint_cut_is_explicit_empty(self):
        result = self.run_cut(axis="z", coordinate=19)
        self.assertTrue(result["geometry"].is_empty)
        self.assertEqual(result["report"]["status"], "empty")
        self.assertEqual(result["report"]["area"], 0)
        self.assertEqual(result["report"]["polygon_count"], 0)
        self.assertEqual(result["report"]["hole_count"], 0)
        self.assertEqual(result["report"]["units"], "Millimeters")
        json.dumps(result["report"], allow_nan=False)

    def test_nominal_tangent_with_unresolved_inside_sliver_is_rejected(self):
        native = rhino3dm.File3dm.Read(str(CONTROL_DIR / "tilted_prism.3dm"))
        extrusion = list(native.Objects)[0].Geometry
        actual_max = max(p.X for p in extrusion.Profile3d(0, 1.0).TryGetPolyline())
        # Stored coordinates have max X=18.200000000000003. The decimal 18.2
        # lies strictly inside by one floating-point step, so an empty result
        # would erase an unresolved sliver. The documented policy now rejects it.
        self.assertGreater(actual_max, 18.2)
        self.assertLess(actual_max - 18.2, 1e-12)
        self.assert_error("numerical_instability", "tilted_prism", axis="x", coordinate=18.2)

    def test_clearly_outside_tilted_prism_remains_empty(self):
        result = self.run_cut("tilted_prism", axis="x", coordinate=18.3)
        self.assertTrue(result["geometry"].is_empty)
        self.assertEqual(result["report"]["status"], "empty")
        self.assertEqual(result["report"]["area"], 0)

    def test_reviewers_original_near_parallel_input_rejects_unresolved_precision(self):
        path = REVIEW_DIR / "conditioning-original-0.3dm"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "9dd217e82499d7b45eb3b75341fd8e622a6350ec600553e9a78b4c63056e54e6")
        extrusion = list(rhino3dm.File3dm.Read(str(path)).Objects)[0].Geometry
        self.assertTrue(extrusion.IsSolid)
        self.assertFalse(extrusion.IsMiteredAtStart)
        self.assertFalse(extrusion.IsMiteredAtEnd)
        self.assertEqual(extrusion.PathEnd.X - extrusion.PathStart.X, 1e-12)
        self.assertEqual(extrusion.PathEnd.Z - extrusion.PathStart.Z, 1)
        self.assertEqual(
            [(p.X, p.Y, p.Z) for p in extrusion.Profile3d(0, 0.0).TryGetPolyline()],
            [(0, 0, 0), (1, 0, -1e-12), (1, 1, -1e-12), (0, 1, 0), (0, 0, 0)],
        )
        # At X=0.5 the true section has essentially unit area. Solving via a
        # 1e-12 path projection amplifies double precision beyond 1e-7 units;
        # this supported-domain limit must be reported, not a claimed exact cut.
        with self.assertRaises(SectionError) as caught:
            section_file(path, axis="x", coordinate=0.5, tolerance=1e-7)
        self.assertEqual(caught.exception.code, "numerical_instability")

    def test_reviewers_triangle_distinguishes_tangent_unresolved_and_resolved_interior(self):
        path = REVIEW_DIR / "tangent-triangle-original.3dm"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "fd849883a69e5841cdf135819287408d5de1469c82fbe91490485a427c20d0f1")
        extrusion = list(rhino3dm.File3dm.Read(str(path)).Objects)[0].Geometry
        self.assertEqual(
            [(p.X, p.Y, p.Z) for p in extrusion.Profile3d(0, 0.0).TryGetPolyline()],
            [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)],
        )
        self.assertEqual(extrusion.PathEnd.Z - extrusion.PathStart.Z, 1)
        # Triangle is 0<=Y<=X<=1. Therefore the X=c material section is
        # [0,c] in screen Y by [0,1] in Z, with exactly c square source units.
        tangent = section_file(path, axis="x", coordinate=0, tolerance=1e-7)
        self.assertTrue(tangent["geometry"].is_empty)
        with self.assertRaises(SectionError) as caught:
            section_file(path, axis="x", coordinate=5e-15, tolerance=1e-7)
        self.assertEqual(caught.exception.code, "numerical_instability")
        resolved = section_file(path, axis="x", coordinate=1e-6, tolerance=1e-7)
        self.assert_region(resolved, box(0, 0, 1e-6, 1), area=1e-6, polygons=1, holes=0, units="Meters")

    def test_cap_outer_side_and_inner_side_coplanarity_rejected(self):
        for axis, coordinate in (("z", 3), ("z", 7), ("x", 11), ("x", 10.5)):
            with self.subTest(axis=axis, coordinate=coordinate):
                self.assert_error("ambiguous_boundary", axis=axis, coordinate=coordinate)

    def test_boundary_tolerance_is_explicit_and_not_a_hidden_offset(self):
        tolerance = 1e-7
        self.assert_error("ambiguous_boundary", axis="z", coordinate=3 + tolerance / 2, tolerance=tolerance)
        inside = self.run_cut(axis="z", coordinate=3 + 5 * tolerance, tolerance=tolerance)
        self.assert_region(inside, PLAN, area=20, polygons=1, holes=1, units="Millimeters")
        self.assertEqual(inside["report"]["plane"]["coordinate"], 3 + 5 * tolerance)
        outside = self.run_cut(axis="z", coordinate=3 - 5 * tolerance, tolerance=tolerance)
        self.assertTrue(outside["geometry"].is_empty)

    def test_curved_outer_and_inner_profiles_fail_closed(self):
        for name in ("curved_outer", "curved_inner"):
            with self.subTest(control=name):
                self.assert_error("unsupported_profile", name, axis="z", coordinate=5)

    def test_uncapped_extrusion_is_not_promoted_to_solid(self):
        self.assert_error("uncapped_extrusion", "uncapped_prism", axis="z", coordinate=5)

    def test_native_valid_flags_do_not_bypass_hole_topology(self):
        for name in ("outside_hole", "touching_hole", "overlapping_holes"):
            with self.subTest(control=name):
                path = NEGATIVE_DIR / (name + ".3dm")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.negative_controls[name]["sha256"])
                native = rhino3dm.File3dm.Read(str(path))
                geometry = list(native.Objects)[0].Geometry
                self.assertTrue(geometry.IsValid)
                self.assertTrue(geometry.IsSolid)
                self.assert_error("unsupported_profile", name, axis="z", coordinate=5)

    def test_mitered_solid_is_rejected(self):
        path = NEGATIVE_DIR / "mitered_prism.3dm"
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.negative_controls["mitered_prism"]["sha256"])
        native = rhino3dm.File3dm.Read(str(path))
        geometry = list(native.Objects)[0].Geometry
        self.assertTrue(geometry.IsSolid)
        self.assertTrue(geometry.IsMiteredAtStart)
        self.assert_error("mitered_extrusion", "mitered_prism", axis="z", coordinate=5)

    def test_brep_and_mixed_file_never_return_partial_exact_success(self):
        self.assert_error("unsupported_geometry", "brep_only", axis="z", coordinate=2)
        # The Brep is outside this slice, while the supported prism intersects.
        # Unsupported input must still be reported; no silent file-level omission.
        self.assert_error("unsupported_geometry", "mixed_geometry", axis="z", coordinate=5)

    def test_invalid_section_arguments_fail_before_geometry(self):
        for overrides in ({"axis":"q"}, {"coordinate":float("nan")},
                          {"coordinate":float("inf")}, {"tolerance":0},
                          {"tolerance":-1}, {"tolerance":float("nan")},
                          {"up":"+z"}, {"up":"north"}):
            with self.subTest(overrides=overrides):
                arguments = {"axis":"z", "coordinate":5, **overrides}
                self.assert_error("invalid_input", **arguments)


if __name__ == "__main__":
    unittest.main()
