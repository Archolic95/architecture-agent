"""Loopback browser viewer. Import into the desktop binary; no separate install.

Only a trusted host registers artifacts. Browser callers never supply a path or
command. Native application opening is disabled unless the host enables it.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from urllib.parse import unquote, urlsplit

MAX_BYTES = 256 * 1024 * 1024
ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
ACTIVITY_STAGES = {"preparing", "building", "checking", "reviewing", "revising", "ready"}


def _activity_snapshot(value):
    """Public, bounded projection. Never forward raw trajectories/reasoning."""
    if value is None:
        return {"version": 1, "enabled": False, "events": []}
    if not isinstance(value, dict) or value.get("state") not in {"running", "ready", "failed", "idle"}:
        raise ValueError("Invalid public activity state")
    events = value.get("events")
    if not isinstance(events, list) or len(events) > 12:
        raise ValueError("Public activity accepts at most 12 events")
    public_events, seen = [], set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid activity event")
        key, message = event.get("id"), event.get("message", "")
        if not isinstance(key, str) or not 0 < len(key) <= 80 or key in seen:
            raise ValueError("Activity event IDs must be unique bounded strings")
        if event.get("stage") not in ACTIVITY_STAGES or event.get("status") not in {"active", "done", "failed"}:
            raise ValueError("Invalid public activity event status")
        if not isinstance(message, str) or len(message) > 240:
            raise ValueError("Public activity messages must be at most 240 characters")
        seen.add(key)
        public_events.append({"id": key, "stage": event["stage"], "status": event["status"], "message": message})
    result = {"version": 1, "enabled": True, "state": value["state"], "events": public_events}
    if len(json.dumps(result).encode()) > 32768:
        raise ValueError("Public activity snapshot is too large")
    return result


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _artifact_bytes(record):
    path = record["path"]
    # O_NOFOLLOW plus fstat avoid serving a substituted symlink. Compare the
    # entire registered content hash before handing bytes to the caller.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        import stat
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("Artifact is not a regular file within the size limit")
        with os.fdopen(os.dup(fd), "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES or not hmac.compare_digest(_digest(data), record["sha256"]):
        raise ValueError("Artifact changed; ask the agent to refresh this viewer")
    return data


def _default_opener(path, kind):
    # A trusted callback may instead route to a particular owned Rhino host.
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", "-a", "Rhino 8", str(path)], shell=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=15)
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        raise ValueError("Local Rhino opening is supported on macOS and Windows")


def register_preview(preview_path, validation_path, native_record):
    """Bind the explicit preview to a generator report and exact native bytes.

    This checks artifact correspondence, not the truth of an arbitrary report.
    The generator is responsible for geometry checks before producing the report.
    """
    path, report_path = Path(preview_path), Path(validation_path)
    if path.is_symlink() or report_path.is_symlink():
        raise ValueError("Preview and validation must be regular files")
    path, report_path = path.resolve(strict=True), report_path.resolve(strict=True)
    if path.stat().st_size > 32 * 1024 * 1024 or report_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Preview or validation exceeds its size limit")
    raw = path.read_bytes()
    report = json.loads(report_path.read_bytes())
    document = json.loads(raw)
    parts = report.get("parts", [])
    files = report.get("files", {})
    if (files.get(Path(native_record["path"]).name) != native_record["sha256"]
            or files.get(path.name) != _digest(raw)):
        raise ValueError("Native model and preview do not match the generation report")
    if (document.get("previewKind") != "explicit_generated_mesh_sidecar"
            or document.get("units") != "Meters"
            or document.get("sourceCount") != len(parts)
            or report.get("objects") != len(parts) or not parts):
        raise ValueError("Unsupported preview or inconsistent object count")
    native_ids = [part.get("native_id") for part in parts]
    object_ids = [item.get("id") for item in document.get("objects", [])]
    if (any(not isinstance(key, str) or not key for key in native_ids)
            or len(native_ids) != len(set(native_ids))
            or len(object_ids) != len(native_ids) or set(object_ids) != set(native_ids)):
        raise ValueError("Preview components do not match the native component manifest")
    if any(not all(part.get(check) is True for check in
                   ("valid", "solid", "mesh_closed", "outward_winding")) for part in parts):
        raise ValueError("Preview requires successful geometry checks in its report")
    return {"path": path, "sha256": _digest(raw),
            "native_sha256": native_record["sha256"], "component_count": len(parts)}


def create_server(*, assets_dir, artifacts=None, title="Architecture model",
                  subtitle="Generated architecture · explore, inspect, continue.",
                  allow_open=False, opener=None, activity_provider=None, preview=None, port=0):
    """Return unstarted ThreadingHTTPServer with .viewer_url and .session_token.

    artifacts: {opaque_id: {path: absolute_3dm_or_gh, sha256: digest}}.
    The host owns serve_forever()/shutdown()/server_close() lifecycle. It must
    separately start a thread and deliver viewer_url to the user. No OS UI or
    browser is launched by this factory.
    opener: optional trusted callable(Path, kind), kind is '3dm' or 'gh'.
    activity_provider: optional quick, read-only callable returning a public
    state/events snapshot or None. Never supply raw reasoning or private logs.
    """
    assets = Path(assets_dir).resolve(strict=True)
    if not (assets / "index.html").is_file():
        raise ValueError("Viewer assets are incomplete")
    records = {}
    for key, entry in (artifacts or {}).items():
        if not ID.fullmatch(key):
            raise ValueError("Invalid artifact ID")
        original = Path(entry["path"])
        if not original.is_absolute() or original.is_symlink():
            raise ValueError("Artifact path must be an absolute regular file")
        path = original.resolve(strict=True)
        if path.suffix.lower() not in (".3dm", ".gh", ".ghx"):
            raise ValueError("Only 3dm and Grasshopper artifacts are allowed")
        expected = entry.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("Artifact requires its expected SHA-256")
        record = {"path": path, "sha256": expected,
                  "kind": "3dm" if path.suffix.lower() == ".3dm" else "gh"}
        _artifact_bytes(record)
        records[key] = record
    preview_record = None
    if preview is not None:
        if not isinstance(preview, dict) or set(preview) != {"path", "validation_path", "native_artifact_id"}:
            raise ValueError("Preview requires a path, validation_path and native_artifact_id")
        native_record = records.get(preview["native_artifact_id"])
        if native_record is None or native_record["kind"] != "3dm":
            raise ValueError("Preview must refer to a registered native model")
        preview_record = register_preview(preview["path"], preview["validation_path"], native_record)
        preview_record["native_artifact_id"] = preview["native_artifact_id"]
    token = secrets.token_urlsafe(32)
    native_open = opener or _default_opener
    activity_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ArchitectureViewer/0.1"

        def log_message(self, *args):
            pass  # Never log request headers, fragment tokens or local paths.

        def _headers(self, status, length, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; worker-src 'self'; connect-src 'self'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()

        def _json(self, status, value):
            data = json.dumps(value).encode()
            self._headers(status, len(data))
            self.wfile.write(data)

        def _guard(self, api=False):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                self._json(403, {"error": "Unexpected viewer host"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected:
                self._json(403, {"error": "Cross-origin viewer request rejected"})
                return False
            if api and not hmac.compare_digest(self.headers.get("X-Viewer-Token", ""), token):
                self._json(401, {"error": "Open the complete viewer link supplied by the agent"})
                return False
            return True

        def do_GET(self):
            request_path = unquote(urlsplit(self.path).path)
            if not self._guard(request_path.startswith("/api/")):
                return
            try:
                if request_path == "/api/activity":
                    if activity_provider is None:
                        self._json(200, {**_activity_snapshot(None), "available": False})
                    elif not activity_lock.acquire(blocking=False):
                        self._json(503, {"error": "Progress updates are temporarily unavailable"})
                    else:
                        try:
                            payload = {**_activity_snapshot(activity_provider()), "available": True}
                            status = 200
                        except Exception:
                            payload = {"error": "Progress updates are temporarily unavailable"}
                            status = 503
                        finally:
                            activity_lock.release()
                        self._json(status, payload)
                    return
                if request_path == "/api/model":
                    self._json(200, {"version": "0.1.0", "title": title, "subtitle": subtitle,
                        "frame": {"up": "Z", "units": "from_3dm"}, "allow_open": bool(allow_open),
                        "preview": None if preview_record is None else {
                            "kind": "explicit_generated_mesh_sidecar", "url": "/api/preview",
                            "sha256": preview_record["sha256"],
                            "native_artifact_id": preview_record["native_artifact_id"],
                            "native_sha256": preview_record["native_sha256"],
                            "component_count": preview_record["component_count"]},
                        "artifacts": [{"id": key, "kind": r["kind"], "filename": r["path"].name,
                            "sha256": r["sha256"], "url": "/api/artifacts/" + key}
                            for key, r in records.items()]})
                    return
                if request_path == "/api/preview":
                    if preview_record is None:
                        self._json(404, {"error": "No paired preview is registered"})
                        return
                    _artifact_bytes(records[preview_record["native_artifact_id"]])
                    data = _artifact_bytes(preview_record)
                    self._headers(200, len(data), "application/json")
                    self.wfile.write(data)
                    return
                if request_path.startswith("/api/artifacts/"):
                    key = request_path.removeprefix("/api/artifacts/")
                    if key not in records:
                        self._json(404, {"error": "Unknown artifact"})
                        return
                    data = _artifact_bytes(records[key])
                    self._headers(200, len(data), "application/octet-stream")
                    self.wfile.write(data)
                    return
                if request_path.startswith("/api/"):
                    self._json(404, {"error": "Unknown endpoint"})
                    return
                relative = request_path.lstrip("/") or "index.html"
                path = (assets / relative).resolve()
                if not path.is_relative_to(assets) or not path.is_file():
                    self._json(404, {"error": "Unknown viewer asset"})
                    return
                mime = {".mjs": "text/javascript", ".js": "text/javascript", ".wasm": "application/wasm"}.get(path.suffix)
                mime = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                data = path.read_bytes()
                self._headers(200, len(data), mime)
                self.wfile.write(data)
            except (OSError, ValueError) as error:
                self._json(409, {"error": str(error) if isinstance(error, ValueError) else "Artifact is unavailable"})

        def do_POST(self):
            if not self._guard(True):
                return
            if self.path != "/api/open":
                self._json(404, {"error": "Unknown endpoint"})
                return
            if not allow_open:
                self._json(403, {"error": "Opening local applications is disabled for this viewer session"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Expected a small JSON artifact request")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {"artifact_id"} or not isinstance(body["artifact_id"], str):
                    raise ValueError("Supply only an artifact_id")
                record = records.get(body["artifact_id"])
                if record is None:
                    raise ValueError("Unknown artifact")
                _artifact_bytes(record)
                native_open(record["path"], record["kind"])
                self._json(200, {"open_requested": True, "artifact_id": body["artifact_id"]})
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                self._json(400, {"error": str(error) if isinstance(error, ValueError) else "Local application could not be opened"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.session_token = token
    server.viewer_url = f"http://127.0.0.1:{server.server_port}/#token={token}"
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--gh", type=Path)
    parser.add_argument("--preview", type=Path, help="Matching generated model.preview.json")
    parser.add_argument("--validation", type=Path, help="Generator validation.json binding native and preview hashes")
    parser.add_argument("--assets-dir", type=Path, default=Path(__file__).parent / "dist")
    parser.add_argument("--title", default="Architecture model")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--allow-open", action="store_true")
    args = parser.parse_args()
    if bool(args.preview) != bool(args.validation) or (args.preview and not args.model):
        parser.error("--preview and --validation require each other and --model")
    registered = {}
    for key, path in (("model", args.model), ("grasshopper", args.gh)):
        if path:
            registered[key] = {"path": str(path.resolve()), "sha256": _digest(path.read_bytes())}
    server = create_server(assets_dir=args.assets_dir, artifacts=registered, title=args.title,
                           port=args.port, allow_open=args.allow_open,
                           preview=None if not args.preview else {"path": args.preview,
                               "validation_path": args.validation, "native_artifact_id": "model"})
    print(json.dumps({"viewer_url": server.viewer_url, "port": server.server_port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
