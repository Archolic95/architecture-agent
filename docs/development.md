# Reproduce this source beta

Python 3.12–3.13 is required by the pinned dependency set. The source and browser server are portable Python; release QA has run on macOS Apple Silicon. Linux and Windows still need platform-specific acceptance. The setup script requires compatible binary wheels and fails clearly if they are unavailable.

```sh
python3 plugins/architecture-agent/skills/architecture-modeling/scripts/setup.py --venv .architecture-venv
.architecture-venv/bin/python plugins/architecture-agent/skills/architecture-modeling/scripts/test_kit.py
python3 tools/build_release.py --output dist
```

For the viewer, enter `plugins/architecture-agent/skills/architecture-modeling/scripts/viewer`. Node 20+ is needed only to rebuild and test the browser bundle:

```sh
npm ci --ignore-scripts --no-audit --no-fund
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
node build.mjs
```

The source release includes the resulting offline `dist` assets. End users do not need npm to view a model. `tools/build_release.py` emits source and skill-only ZIPs with stable ordering, fixed ZIP timestamps, file checksums and no installed dependency environments.

For CPU visual review of a generated scene:

```sh
.architecture-venv/bin/python plugins/architecture-agent/skills/architecture-modeling/scripts/cpu_preview.py output/courtyard --roof-layer Roof --plan-hide-layer Roof --plan-hide-layer Site --plan-cut 1.5 --section-axis y --section-offset 3
```

Choose cut coordinates and layer names for the actual model. Roof names are case-insensitive and repeatable; the roof-off image is skipped with a recorded reason when no requested roof layer exists. Empty cut geometry fails. `preview-views.json` records the choices and actual output views. These are orthographic, uncapped visual clips, not BIM section drawings.

To show the exact native model paired with its generated preview:

```sh
python3 plugins/architecture-agent/skills/architecture-modeling/scripts/viewer/viewer_service.py --model output/courtyard/model.3dm --preview output/courtyard/model.preview.json --validation output/courtyard/validation.json --title 'Courtyard house'
```

The server verifies both file hashes from the generation report and matching component IDs. It retains native download independently of display. The pairing check establishes correspondence to the supplied report; it does not certify arbitrary third-party claims or replace geometric validation.
