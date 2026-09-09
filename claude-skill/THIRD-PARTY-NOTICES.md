# Third-party notices

Architecture Agent skill instructions, geometry helpers, CPU renderer and portable viewer source are Apache-2.0. The license is included as `LICENSE`.

The portable viewer embeds Three.js 0.128.0 under the MIT License. Its source and complete license text are included at `scripts/viewer/dist/vendor/three.module.js` and `scripts/viewer/dist/vendor/THREE-LICENSE.txt`. Source: https://github.com/mrdoob/three.js/tree/r128

Python packages are downloaded into a project-local environment during setup and are not redistributed in this archive. Pinned distributions and their project licenses are: rhino3dm 8.32.1 (MIT), Shapely 2.1.2 (BSD-3-Clause), NumPy 2.5.3 (BSD-3-Clause and bundled component notices), trimesh 5.1.0 (MIT), mapbox-earcut 2.0.0 (ISC), and Pillow 12.3.0 (MIT-CMU). Binary wheels can include additional libraries and notices; retain their installed license files when redistributing an environment. Shapely wheels, for example, include GEOS under LGPL-2.1-or-later.
