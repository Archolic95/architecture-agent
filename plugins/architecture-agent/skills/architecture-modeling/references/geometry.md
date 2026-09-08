# Modeling contract

Coordinates are metres, right-handed and Z-up. The library stores exact capped extrusion geometry and computes matching preview meshes from the same polygon profiles and transforms.

```python
from geometry_kit import Scene

scene = Scene('Pavilion')
scene.add_profile(
    'floor.ground',
    [(0, 0), (12, 0), (12, 8), (0, 8)],
    holes_xy=[[(4, 3), (8, 3), (8, 6), (4, 6)]],
    z0=0, height=0.25, layer='Floor slabs',
    color=(0.85, 0.84, 0.80, 1.0),
    metadata={'role': 'floor_slab', 'storey': 0},
)
scene.add_box('column.01', [0.2, 0.2, 0.25, 0.4, 0.4, 3.45],
              layer='Structure', color=(0.2, 0.2, 0.2, 1.0))
scene.export('output/pavilion-r001')
```

Use Shapely polygon operations to construct profile differences for windows, stair holes and courtyards. Check the result type: disconnected regions need separate named components. Do not silently discard smaller regions or repair invalid self-intersecting rings. Coordinate transforms apply to both native and preview geometry.

A vertical wall can be an extrusion of its local elevation profile placed into the world coordinate system. Retain actual profile holes rather than drawing a dark rectangle over a solid wall. Layer and component metadata help later editing but do not supply complete BIM ownership or host relationships automatically.

The helper validates positive finite dimensions, profiles, transform orientation, native validity, watertight preview geometry and analytic volume agreement. Unsupported shape classes need a different backend or an explicitly described approximation. Lofting, arbitrary solid booleans and unrestricted NURBS operations are outside this initial helper API.
