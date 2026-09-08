import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from shapely.geometry import Point
from build_demo import build
from geometry_kit import Scene, polygon


class KitTests(unittest.TestCase):
    def test_concave_hole_native_profiles_and_preview(self):
        outer=[(0,0),(5,0),(5,2),(2,2),(2,5),(0,5)]
        holes=[[(.4,.5),(1.5,.5),(1.5,1.5),(.4,1.5)]]
        s=Scene();s.add_profile("test",outer,holes_xy=holes,z0=1.2,height=2.8)
        part=s.parts["test"];mesh=part["mesh"]
        self.assertAlmostEqual(mesh.volume,polygon(outer,holes).area*2.8)
        cap=mesh.triangles[np.ptp(mesh.triangles[:,:,2],axis=1)<1e-8]
        for centroid in cap.mean(axis=1):
            self.assertFalse(polygon(holes[0]).contains(Point(*centroid[:2])))
        with tempfile.TemporaryDirectory() as d:
            r=s.export(d);self.assertEqual(r["objects"],1)
            self.assertFalse(r["parts"][0]["cached_render_mesh"])

    def test_affine_placement_native_preview_agree(self):
        m=np.eye(4);m[0,0]=1.4;m[2,1]=.3;m[:3,3]=[4,-3,2]
        s=Scene();s.add_box("inclined",[0,0,0,2,3,.4],transform=m)
        with tempfile.TemporaryDirectory() as d:s.export(d)
        self.assertAlmostEqual(s.parts["inclined"]["mesh"].volume,2*3*.4*1.4)

    def test_invalid_profiles_and_nonfinite_are_atomic(self):
        s=Scene();valid=[(0,0),(2,0),(2,2),(0,2)]
        for profile in [[(0,0),(2,2),(0,2),(2,0)],[(0,0),(float("nan"),0),(1,1)]]:
            with self.assertRaises(ValueError):s.add_profile("bad",profile)
            self.assertFalse(s.parts)
        for height in [float("inf"),0,-1]:
            with self.assertRaises(ValueError):s.add_profile("bad",valid,height=height)
        with self.assertRaises(ValueError):s.add_box("bad",[0,0,0,1,float("inf"),1])
        with self.assertRaises(ValueError):s.add_profile("bad",valid,transform=np.diag([-1,1,1,1]))
        self.assertFalse(s.parts)

    def test_duplicate_id_is_refused(self):
        s=Scene();s.add_box("same",[0,0,0,1,1,1])
        with self.assertRaises(ValueError):s.add_box("same",[0,0,0,2,2,2])
        self.assertEqual(len(s.parts),1)
        self.assertAlmostEqual(s.parts["same"]["mesh"].volume,1)

    def test_parameters_change_real_geometry_preserve_identity(self):
        base=build();changed=build(16,3.6);height_only=build(14,3.6)
        self.assertEqual(set(base.parts),set(changed.parts))
        self.assertFalse(np.allclose(base.parts["floor.0"]["mesh"].bounds,changed.parts["floor.0"]["mesh"].bounds))
        self.assertFalse(np.allclose(base.parts["roof"]["mesh"].bounds,changed.parts["roof"]["mesh"].bounds))
        self.assertTrue(np.array_equal(base.parts["terrace.slab"]["mesh"].vertices,height_only.parts["terrace.slab"]["mesh"].vertices))
        with tempfile.TemporaryDirectory() as d:
            a=base.export(Path(d)/"base");b=changed.export(Path(d)/"changed")
            self.assertEqual([p["native_id"] for p in a["parts"]],[p["native_id"] for p in b["parts"]])
            self.assertNotEqual(a["files"]["model.3dm"],b["files"]["model.3dm"])
            self.assertNotEqual(a["files"]["model.preview.glb"],b["files"]["model.preview.glb"])


if __name__=="__main__":unittest.main(verbosity=2)
