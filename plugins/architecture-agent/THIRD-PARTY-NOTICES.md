# Third-party notices

Original plugin instructions, geometry helpers, CPU renderer and viewer source are Apache-2.0. Their source is supplied in this repository.

The offline viewer includes these pinned browser libraries, with full license texts alongside the files:

| Component | Version | License | Source |
| --- | --- | --- | --- |
| Three.js | 0.128.0 | MIT | https://github.com/mrdoob/three.js/tree/r128 |
| rhino3dm JavaScript/WebAssembly | 8.32.2 | MIT | https://github.com/mcneel/rhino3dm |

License files are in `plugins/architecture-agent/skills/architecture-modeling/scripts/viewer/dist/vendor/`. `package-lock.json` records npm integrity hashes and `build.mjs` reproduces the vendored assets from pinned packages.

Python packages are downloaded into the user's environment during setup; Python wheels, Python itself, and native libraries from those wheels are not redistributed in this source archive. The dependency pins are:

| Distribution | Version | Project license |
| --- | --- | --- |
| rhino3dm | 8.32.1 | MIT |
| Shapely | 2.1.2 | BSD-3-Clause |
| NumPy | 2.5.3 | BSD-3-Clause and bundled component notices |
| trimesh | 5.1.0 | MIT |
| mapbox-earcut | 2.0.0 | ISC |
| Pillow | 12.3.0 | MIT-CMU |

Binary wheels can include additional libraries and notices; retain their installed license files when redistributing an environment. For example, Shapely wheels include GEOS under LGPL-2.1-or-later. This repository does not bundle or depend on PyMuPDF, MuPDF, Rhino desktop, Grasshopper, or a proprietary modeling-service program.

`rhino3dm` Python distribution metadata is version 8.32.1 while the imported module reports 8.32.2; setup pins the distribution version.
