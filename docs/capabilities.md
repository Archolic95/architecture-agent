# Backend and viewer scope

| Capability | Source beta |
| --- | --- |
| Brief and hybrid reference interpretation | The host multimodal agent observes inputs and records measurements/assumptions. |
| Geometry generation | Planar polygon profiles with interior holes, capped native extrusions, boxes, affine placement. |
| Preview delivery | Explicit matching triangle sidecars; fresh native extrusions do not contain cached meshes. |
| Native delivery | `.3dm` objects retain geometry type, layers, materials and component metadata. |
| Retained edits | Python source and parameters regenerate a new output directory; preserve earlier results. |
| Browser view | Perspective/axonometric camera, orbit/pan/zoom, layers, selection and uncapped section cuts. |
| Portable HTML | One embedded native model and validated paired preview, with bundled display modules and file hashes. The recipient opens the downloaded file in a desktop browser without a server or Python. No arbitrary model import, native-app dispatch or live progress in this mode. |
| Filled 2D solid sections | Separate opt-in native-file command for capped, unmitered polygonal Extrusions and world X/Y/Z planes. Combined solid occupancy with holes; no construction-material boundaries or projected geometry behind the cut. Preserves source units and explicitly rejects unsupported or unresolved input. |
| Rhino open | Optional local file dispatch; it does not prove successful native load. |
| Grasshopper | The viewer can open an explicitly supplied `.gh` file. This backend does not generate a GH definition. |
| Advanced booleans, lofts, pipes, arbitrary BRep meshing | Outside the initial helper set. Report the limitation or use a separately configured full Rhino backend. |
| BIM semantics and Revit | Component metadata is retained; it is not a certified BIM or Revit export. |
| Public progress | The viewer accepts optional public action/status events. No model reasoning is exposed. |
| Incremental geometry | Not implemented in this release. |
| PDF processing | Use the host's document/image tools. This package does not bundle a PDF rasterizer. |

## ChatGPT web delivery

| Capability | Optional v0.3.0-beta.4 ChatGPT web skill |
| --- | --- |
| Installation | **Skills → Create → Upload from your computer** was accepted on one ChatGPT Work account. Account and workspace availability can vary. |
| Modeling runtime | Uses the writable Python execution environment supplied by ChatGPT. The accepted smoke imported all six pinned dependencies. |
| Deliverables | Retained Python source and parameters, `.3dm`, validation records, inspected static previews, and downloadable portable HTML when host attachment delivery is available. |
| Viewer | The user downloads the self-contained HTML and opens it in a desktop browser. One accepted smoke rendered 182 objects and 3,308 triangles and passed axonometric, roof-visibility, and Z=3.05 section checks in Chrome. |
| Local/native features | No MCP, loopback server, native Rhino/Grasshopper, native-app dispatch, live preview, arbitrary `.3dm` browser import, or directory publication. |
| Evidence boundary | The completed smoke used the unchanged bundled demo. Native validation was host-reported, not independently reopened by the reviewer. No new-building fidelity benchmark was performed. |

A native file and its preview must use the same parameters and placements. A mesh preview is not evidence that every native object can be edited as a solid. Validation reports distinguish native shape checks, preview checks and visual review.

The portable packager reuses the generator report and the viewer's artifact checks; it does not independently certify native/mesh equivalence. Core controls passed actual Chrome checks on bounded fixtures. ChatGPT attachment delivery and downloaded file-origin rendering passed once on the recorded Work account. Pan, file-drop refusal, the WebGL-unavailable fallback, saved native-download byte identity and other chat hosts remain outside completed acceptance.

Filled sections do not change the CPU or browser's uncapped cuts. The native reader checks all objects regardless of visibility and rejects the entire file when any object is unsupported. See [section scope and error semantics](../plugins/architecture-agent/skills/architecture-modeling/references/native-sections.md).

Do not call a guessed reconstruction surveyed, construction-ready, code-compliant or benchmark-validated. These are separate claims requiring their own evidence.
