"""Package one validated generated preview and native model as offline HTML.

No geometry generation, browser launch, HTTP server or dependency installation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_for_html(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def read_regular(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Input must be a regular file within the size limit")
    return path.read_bytes()


def adapt_app(source):
    # Exact beta.2 boundaries: fail on drift instead of rewriting unfamiliar code.
    edits = []
    def replace_line(prefix, replacement):
        nonlocal source
        lines = source.splitlines(keepends=True)
        matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError("Unsupported viewer source: " + prefix)
        old = lines[matches[0]]
        lines[matches[0]] = replacement + "\n"
        source = "".join(lines)
        edits.append({"anchor": prefix, "before_sha256": digest(old.encode()), "replacement": replacement})
    replace_line("const token=", "// This portable viewer has no loopback service or session token.")
    replace_line("async function api(", "import {api} from './portable-api.mjs';")
    replace_line("import {mountCheckpoints,", "// Live checkpoint transport is excluded from this offline snapshot.")
    live_start = source.index("async function prepareLiveCheckpoint(")
    live_end = source.index("async function load(bytes,name,local=false){", live_start)
    source = source[:live_start] + "function startLive(){throw new Error('Live sessions are unavailable in this offline snapshot.');}\n" + source[live_end:]
    edits.append({"anchor": "source live transport", "change": "Remove live polling, preparation and mount path; portable output remains one immutable snapshot."})
    start = source.index("async function load(bytes,name,local=false){")
    end = source.index("async function loadPreview(artifact){", start)
    source = source[:start] + "async function load(){throw new Error('This portable file requires its embedded paired preview.');}\n" + source[end:]
    edits.append({"anchor": "async function load", "change": "Replace native decoder/Worker path with explicit unsupported error."})
    replace_line("async function importFile(", "async function importFile(){toast('Import is unavailable in this portable file. It contains one model and its paired preview.');}")
    replace_line("async function openArtifact(", "async function openArtifact(){toast('Native application opening is unavailable here. Download the model to open it manually.');}")
    old_catch = "catch(e){if(token)toast(e.message,true);}"
    if source.count(old_catch) != 1:
        raise ValueError("Unsupported viewer bootstrap error handling")
    source = source.replace(old_catch, "catch(e){toast(e.message,true);}")
    edits.append({"anchor": "bootstrap catch", "change": "Show startup errors without a service token."})
    if re.search(r"\bfetch\s*\(|\bnew\s+Worker\s*\(|\bimportScripts\s*\(", source):
        raise ValueError("Portable app still contains a network or decoder operation")
    return source, edits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", type=Path, default=HERE.parent / "viewer", help="Viewer directory (default: bundled scripts/viewer beside this packager)")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--title", default="Portable architecture model")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output directory already exists; use a new directory")
    viewer = args.viewer.resolve(strict=True)
    model_path = args.model.absolute()
    native_bytes = read_regular(model_path, 256 * 1024 * 1024)
    record = {"path": model_path, "sha256": digest(native_bytes), "kind": "3dm"}
    spec = importlib.util.spec_from_file_location("frozen_viewer_service", viewer / "viewer_service.py")
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    # Reuse registration's exact native hash, report/hash/ID/check correspondence.
    native_readback = service._artifact_bytes(record)
    if native_readback != native_bytes:
        raise ValueError("Native artifact changed during packaging")
    registered = service.register_preview(args.preview, args.validation, record)
    preview_bytes = read_regular(args.preview, 32 * 1024 * 1024)
    validation_bytes = read_regular(args.validation, 8 * 1024 * 1024)
    if digest(preview_bytes) != registered["sha256"]:
        raise ValueError("Preview changed during packaging")
    report = json.loads(validation_bytes)
    if report["files"][model_path.name] != digest(native_bytes) or report["files"][args.preview.name] != digest(preview_bytes):
        raise ValueError("Validation changed during packaging")
    payload = {"version": 1, "title": args.title, "files": []}
    for role, path, data in (("native", args.model, native_bytes), ("preview", args.preview, preview_bytes), ("validation", args.validation, validation_bytes)):
        payload["files"].append({"role": role, "filename": path.name, "bytes": len(data), "sha256": digest(data), "base64": base64.b64encode(data).decode("ascii")})

    dist = viewer / "dist"
    module_names = ["vendor/three.module.js", "camera-math.mjs", "model-state.mjs", "activity.mjs", "preview.mjs", "app.mjs"]
    modules = {name: (dist / name).read_bytes() for name in module_names}
    original_hashes = {name: digest(data) for name, data in modules.items()}
    adapted, edits = adapt_app(modules["app.mjs"].decode("utf-8"))
    modules["app.mjs"] = adapted.encode()
    modules["portable-api.mjs"] = (HERE / "portable-api.mjs").read_bytes()
    bundle = {"payload": payload, "modules": {name: {"sha256": digest(data), "base64": base64.b64encode(data).decode("ascii")} for name, data in modules.items()}}
    loader = (HERE / "module-loader.mjs").read_text(encoding="utf-8").replace("export function buildModuleURLs", "function buildModuleURLs")
    bootstrap = loader + "\n" + (HERE / "bootstrap.mjs").read_text(encoding="utf-8")
    css = (dist / "style.css").read_text(encoding="utf-8")
    if "</script" in bootstrap.lower() or "</style" in css.lower():
        raise ValueError("Unexpected HTML delimiter in embedded runtime")
    template = (dist / "index.html").read_text(encoding="utf-8")
    def substitute(old, new):
        nonlocal template
        if template.count(old) != 1:
            raise ValueError("Unsupported viewer template: " + old)
        template = template.replace(old, new)
    substitute('<meta charset="utf-8">', '<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\' blob:; style-src \'unsafe-inline\'; img-src data: blob:; connect-src \'none\'; worker-src \'none\'; object-src \'none\'; base-uri \'none\'">')
    substitute('<title>Architecture Agent · Model studio</title>', '<title>' + html.escape(args.title) + ' · Architecture Agent</title>')
    substitute('<link rel="stylesheet" href="./style.css">', '<style>' + css + '\n#portable-status{font-size:11px;color:#6b7466;margin:8px 0;line-height:1.4}#portable-status[data-state="error"]{color:#a33425}#welcome-import{display:none}button:disabled{cursor:not-allowed}</style>')
    substitute(' Local workspace', ' Offline model')
    substitute('<button id="import" class="quiet">＋ Import .3dm</button>', '<button id="import" class="quiet" disabled title="This portable file contains one model and its paired preview.">Import unavailable</button>')
    substitute('<input id="file" type="file" accept=".3dm" hidden>', '<input id="file" type="file" accept=".3dm" hidden disabled>')
    substitute('<div class="eyebrow">CONTINUE DESIGNING</div>', '<div class="eyebrow">NATIVE MODEL</div><p id="portable-status" role="status" aria-live="polite">Verifying embedded files…</p>')
    substitute('<p>Open a generated model or drop a Rhino .3dm file here.</p>', '<p>Opening the model and paired preview stored in this file.</p>')
    substitute('<button id="welcome-import">Import a model ↗</button>', '<button id="welcome-import" disabled hidden>Import unavailable</button>')
    # Keep native buttons disabled with a visible scope note; no dispatch endpoint exists.
    substitute('<button id="download" class="download" disabled>', '<p class="muted" style="font-size:11px">Native app opening is unavailable here. Download the model to open it manually.</p><button id="download" class="download" disabled>')
    license_path = next((path for path in (viewer.parents[1] / "LICENSE", viewer.parents[3] / "LICENSE") if path.is_file()), None)
    if license_path is None:
        raise ValueError("The source skill or plugin license is required")
    notices = {"LICENSE": license_path.read_text(encoding="utf-8"),
        "THREE-LICENSE.txt": (dist / "vendor/THREE-LICENSE.txt").read_text(encoding="utf-8"),
        "THIRD-PARTY-NOTICES.md": (viewer / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")}
    substitute('<script type="module" src="./bootstrap.mjs"></script>', '<script type="application/json" id="portable-licenses">' + json_for_html(notices) + '</script>\n<script type="application/json" id="portable-package">' + json_for_html(bundle) + '</script>\n<script type="module">\n' + bootstrap + '\n</script>')

    args.output.mkdir(parents=True)
    artifact = args.output / "model-portable.html"
    artifact.write_text(template, encoding="utf-8", newline="\n")
    receipt = {
        "status": "packaged_requires_browser_review", "title": args.title,
        "artifact": artifact.name, "bytes": artifact.stat().st_size, "sha256": digest(artifact.read_bytes()),
        "native_preview_registration_reused": True, "native_preview_equivalence_scope": "Existing generator-report checks and artifact/component identity, not a new native-mesh equivalence certification.",
        "files": [{key: value for key, value in entry.items() if key != "base64"} for entry in payload["files"]],
        "source_paths": {"viewer": str(viewer), "model": str(args.model.resolve()), "preview": str(args.preview.resolve()), "validation": str(args.validation.resolve())},
        "source_modules_sha256": original_hashes, "embedded_modules_sha256": {name: digest(data) for name, data in modules.items()},
        "app_adaptations": edits, "rendering_controls_changed": False, "live_session_embedded": False, "snapshot_scope": "One validated checkpoint; no active live session, no polling or HTTP capability", "source_geometry_generated": False,
        "runtime": "Self-contained HTML using embedded Blob ESM, WebCrypto SHA-256 and WebGL; no server, WASM decoder, CDN or external requests.",
        "unsupported": ["Arbitrary 3dm import", "Native Rhino/Grasshopper dispatch", "Live generation/progress"],
        "awaiting": ["Actual file-origin module/CSP/WebCrypto execution", "Visual review of camera/layer/section controls", "Actual pan gesture", "Actual file-drop refusal", "WebGL-unavailable download fallback", "Browser-saved .3dm download identity", "Chat host HTML attachment delivery and opening"]}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt[key] for key in ("status", "artifact", "bytes", "sha256")}))


if __name__ == "__main__":
    main()
