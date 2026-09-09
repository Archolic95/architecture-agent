---
name: architecture-modeling
description: Build or revise editable architectural Rhino models from briefs, plans, sections, elevations, photos, or mixed references using retained Python source and downloadable browser previews.
---

# Architecture modeling

Use the host's multimodal reasoning and execution tools to build, inspect and revise a retained model. Read `references/geometry.md` before authoring geometry. The helper set is deliberately small; do not claim it implements all RhinoCommon or Grasshopper operations.

## Confirm cloud capabilities first

Before authoring or running source, confirm that this conversation provides a writable project folder, Python 3.12 or 3.13 execution, and either the pinned dependencies from `scripts/requirements.txt` or permission to create a project-local environment with `scripts/setup.py`. Also confirm that generated files can be returned as downloadable attachments. If any required capability is absent, state exactly what is unavailable and stop before claiming a model was built. Do not redirect cloud users to local MCP, native Rhino/Grasshopper execution or a loopback URL.

## Begin with the available evidence

Inspect supplied inputs using the host's image/document tools. For PDFs, prefer vector measurements when available; this skill includes no PDF rasterizer. Record units, common axes, known dimensions, image coverage, observed facts, inferred dimensions, and unresolved conflicts in the project folder. Use plans, sections and photographs together when provided. Do not invent a source file or state that inferred dimensions were measured.

For a reasonably specified modeling request, make progress using explicit assumptions. Ask only for input that materially prevents a useful result. Keep source/reference provenance separate from generated output.

## Build and verify

1. Create a task output folder and retain `build_model.py` plus `params.json`. Do not overwrite earlier delivered revisions.
2. Reuse a compatible environment only after importing every pinned dependency successfully. Otherwise, when downloads and subprocess execution are available, run `scripts/setup.py --venv <project>/.architecture-venv`. If dependency installation is unavailable, return the retained inputs and capability result without generating substitute geometry. Never change a global Python environment.
3. Use the optional `Scene` helpers from the bundled `scripts/geometry_kit.py` (copy the helper beside retained source when handing off a self-contained project). The host agent authors its own Python; the demo is an example, not the only design it can generate. Direct rhino3dm calls may be used where supported, with equally explicit validation and preview correspondence. Prefer native solids, real openings and meaningful component IDs. For helper API and output details, read `references/standalone-kit.md`. The bundled `scripts/build_demo.py` shows a complete courtyard example.
4. Run the source with the chosen parameters. Inspect validation output and resolve failed native/mesh checks. Preserve the exact source, parameters and dependency versions used.
5. For a CPU preview, run `scripts/cpu_preview.py <output folder> --roof-layer <roof layer> --plan-cut <absolute Z> --section-axis y --section-offset <absolute Y>`. Choose coordinates and layers for the actual model; inspect `preview-views.json` for skipped views. Render or view the result with the host's supported tools. Compare important views against the supplied drawings: footprint, storey elevations, opening positions, stairs, structure and interior details. A successful export alone is not a visual check. The browser viewer can assist inspection but does not replace source comparison.
6. When a filled 2D section is useful, read `references/native-sections.md` and run `scripts/native_sections.py <model.3dm> --axis y --coordinate <absolute Y> --output <new section folder> --title "Filled 2D solid section"`. Choose the plane and source-unit tolerance explicitly. Inspect both `section.png` and `section.json`; retain any structured rejection. This separate command supports only capped, unmitered polygonal Extrusions, checks every object regardless of visibility, and never substitutes a mesh clip for unsupported geometry. Its fill is combined solid occupancy, not construction-material categories or a complete architectural drawing. CPU and browser cuts remain uncapped display cuts.
7. Revise the retained source when defects appear, regenerate into a new revision folder and repeat the relevant checks.

## Deliver and continue

Provide the editable `.3dm`, `build_model.py`, `params.json`, complete validation records and inspected previews as downloadable files. Explain what is modeled, which dimensions were inferred, and remaining limitations. Keep changes tied to component IDs and parameters so later edits are reproducible.

For a downloadable interactive preview, read `references/portable-viewer.md` and run `python scripts/portable/build_portable.py --model <model.3dm> --preview <model.preview.json> --validation <validation.json> --output <new viewer folder> --title "<project title>"` after the model and paired preview pass validation. The command locates its bundled viewer automatically and writes `model-portable.html`. Deliver that HTML with the original model files; the user downloads it and opens it in a desktop browser. Do not claim it runs inline in ChatGPT or Claude. This portable file displays one embedded pair; arbitrary `.3dm` import and native-app dispatch are unavailable.

This cloud workflow does not activate `viewer_service.py`. A cloud host's loopback address is not the user's localhost and must never be presented as a usable viewer URL. Deliver `model-portable.html` as an attachment; it is a fixed validated snapshot that the recipient downloads and opens in a current desktop browser. Do not claim that the HTML runs inline in ChatGPT, that it contains live updates, or that it opens Rhino.

The viewer offers perspective/axonometric cameras, layers, selection and uncapped section cuts. Missing display data must be reported honestly. A separately supplied GH artifact can be registered with `--gh`; this initial geometry helper does not produce GH definitions or Revit models.

Public progress may describe plans, actions, checks and results. Do not expose hidden reasoning, raw private logs or invented progress. Incremental geometry updates are optional and are not implemented by this release.
