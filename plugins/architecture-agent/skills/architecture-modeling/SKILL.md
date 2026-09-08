---
name: architecture-modeling
description: Generate or revise editable architectural Rhino models from a brief, plans, sections, elevations, photographs, or mixed references using ordinary Python, with retained source and a browser preview. Use for architectural 3D modeling and model inspection; not for unrelated image editing or general CAD API questions.
---

# Architecture modeling

Use the host's multimodal reasoning and execution tools to build, inspect and revise a retained model. Read `references/geometry.md` before authoring geometry. The helper set is deliberately small; do not claim it implements all RhinoCommon or Grasshopper operations.

## Begin with the available evidence

Inspect supplied inputs using the host's image/document tools. For PDFs, prefer vector measurements when available; this plugin includes no PDF rasterizer. Record units, common axes, known dimensions, image coverage, observed facts, inferred dimensions, and unresolved conflicts in the project folder. Use plans, sections and photographs together when provided. Do not invent a source file or state that inferred dimensions were measured.

For a reasonably specified modeling request, make progress using explicit assumptions. Ask only for input that materially prevents a useful result. Keep source/reference provenance separate from generated output.

## Build and verify

1. Create a task output folder and retain `build_model.py` plus `params.json`. Do not overwrite earlier delivered revisions.
2. Use a compatible existing Python environment, or run `scripts/setup.py --venv <project>/.architecture-venv` to create one. This downloads pinned libraries once; it does not require Rhino or an API key. Never change a global Python environment for this workflow.
3. Use the optional `Scene` helpers from the bundled `scripts/geometry_kit.py` (copy the helper beside retained source when handing off a self-contained project). The host agent authors its own Python; the demo is an example, not the only design it can generate. Direct rhino3dm calls may be used where supported, with equally explicit validation and preview correspondence. Prefer native solids, real openings and meaningful component IDs. The original `scripts/build_demo.py` shows a complete courtyard example.
4. Run the source with the chosen parameters. Inspect validation output and resolve failed native/mesh checks. Preserve the exact source, parameters and dependency versions used.
5. For a CPU preview, run `scripts/cpu_preview.py <output folder> --roof-layer <roof layer> --plan-cut <absolute Z> --section-axis y --section-offset <absolute Y>`. Choose coordinates and layers for the actual model; inspect `preview-views.json` for skipped views. Render or view the result with the host's supported tools. Compare important views against the supplied drawings: footprint, storey elevations, opening positions, stairs, structure and interior details. A successful export alone is not a visual check. The browser viewer can assist inspection but does not replace source comparison.
6. Revise the retained source when defects appear, regenerate into a new revision folder and repeat the relevant checks.

## Deliver and continue

Provide the editable `.3dm`, source, parameters, validation summary and preview. Explain what is modeled, which dimensions were inferred, and remaining limitations. Keep changes tied to component IDs and parameters so later edits are reproducible.

For a local desktop host, run `scripts/viewer/viewer_service.py --model <absolute model.3dm> --preview <absolute model.preview.json> --validation <absolute validation.json> --title <project title>` in a retained process, then open its returned URL in the user's browser. The process must remain alive. Optional `--allow-open` enables local Rhino/GH file dispatch when the user requests it; do not claim dispatch proves the application loaded or solved the file. A cloud execution host's loopback viewer URL is not reachable as the user's own local URL; deliver files instead if the host cannot expose the viewer.

The viewer offers perspective/axonometric cameras, layers, selection and uncapped section cuts. Missing display data must be reported honestly. A separately supplied GH artifact can be registered with `--gh`; this initial geometry helper does not produce GH definitions or Revit models.

Public progress may describe plans, actions, checks and results. Do not expose hidden reasoning, raw private logs or invented progress. Incremental geometry updates are optional and are not implemented by this release.
