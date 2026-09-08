import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from viewer_service import create_server


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / "dist"
        self.assets.mkdir()
        (self.assets / "index.html").write_text("viewer")
        self.model = self.root / "model with spaces.3dm"
        self.model.write_bytes(b"test registered 3dm bytes")
        self.gh = self.root / "definition.gh"
        self.gh.write_bytes(b"test registered gh bytes")
        self.calls = []
        self.server = self.make_server(allow_open=True)

    def make_server(self, **kwargs):
        server = create_server(assets_dir=self.assets, artifacts={
            "model": {"path": self.model, "sha256": hashlib.sha256(self.model.read_bytes()).hexdigest()},
            "grasshopper": {"path": self.gh, "sha256": hashlib.sha256(self.gh.read_bytes()).hexdigest()}},
            opener=lambda path, kind: self.calls.append((path, kind)), **kwargs)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None, headers=None, token=True):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        supplied = {"X-Viewer-Token": self.server.session_token} if token else {}
        supplied.update(headers or {})
        data = None if payload is None else json.dumps(payload)
        if data:
            supplied.setdefault("Content-Type", "application/json")
        client.request(method, path, body=data, headers=supplied)
        response = client.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        client.close()
        return result

    def test_static_and_metadata(self):
        self.assertEqual(self.request("/", token=False)[:2], (200, b"viewer"))
        status, body, _ = self.request("/api/model")
        self.assertEqual(status, 200)
        value = json.loads(body)
        self.assertEqual(value["frame"]["up"], "Z")
        self.assertEqual(value["artifacts"][0]["id"], "model")
        self.assertNotIn(str(self.root), body.decode())
        self.assertEqual(self.request("/api/artifacts/model")[1], self.model.read_bytes())

    def test_token_host_and_origin_boundaries(self):
        self.assertEqual(self.request("/api/model", token=False)[0], 401)
        self.assertEqual(self.request("/api/model", headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/model", headers={"Origin": "https://attacker.example"})[0], 403)
        self.assertEqual(self.request("/api/model", headers={"Origin": "null"})[0], 403)

    def test_traversal_cannot_serve_files(self):
        for path in ("/../model%20with%20spaces.3dm", "/%2e%2e/model%20with%20spaces.3dm", "/api/artifacts/../model", "/api/artifacts/unknown"):
            self.assertEqual(self.request(path)[0], 404)

    def test_only_exact_allowlisted_artifact_opens(self):
        for key in ("model", "grasshopper"):
            self.assertEqual(self.request("/api/open", "POST", {"artifact_id": key})[0], 200)
        self.assertEqual(self.calls, [(self.model.resolve(), "3dm"), (self.gh.resolve(), "gh")])
        self.assertEqual(self.request("/api/open", "POST", {"artifact_id": "model", "path": "/tmp/evil"})[0], 400)
        self.assertEqual(self.request("/api/open", "POST", {"artifact_id": "../../evil"})[0], 400)
        self.assertEqual(len(self.calls), 2)

    def test_modified_or_symlink_artifacts_are_refused(self):
        self.model.write_bytes(b"changed")
        self.assertEqual(self.request("/api/artifacts/model")[0], 409)
        self.assertEqual(self.request("/api/open", "POST", {"artifact_id": "model"})[0], 400)
        self.assertEqual(self.calls, [])
        self.model.unlink()
        self.model.symlink_to(self.gh)
        self.assertEqual(self.request("/api/artifacts/model")[0], 409)

    def test_open_disabled_by_default(self):
        self.server.shutdown()
        self.server.server_close()
        self.server = self.make_server()
        self.assertEqual(self.request("/api/open", "POST", {"artifact_id": "model"})[0], 403)
        self.assertEqual(self.calls, [])

    def test_cross_origin_post_never_opens(self):
        self.assertEqual(self.request("/api/open", "POST", {"artifact_id": "model"}, headers={"Origin": "https://external.test"})[0], 403)
        self.assertEqual(self.calls, [])

    def replace_provider(self, provider=None):
        self.server.shutdown()
        self.server.server_close()
        self.server = self.make_server(activity_provider=provider)

    def test_activity_disabled_without_provider_and_requires_auth(self):
        status, body, _ = self.request("/api/activity")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"version": 1, "enabled": False, "available": False, "events": []})
        self.assertEqual(self.request("/api/activity", token=False)[0], 401)
        self.assertEqual(self.request("/api/activity", headers={"Origin": "https://external.test"})[0], 403)

    def test_activity_projects_only_bounded_public_fields(self):
        self.replace_provider(lambda: {"state": "running", "private_reasoning": "not public", "events": [
            {"id": "build-1", "stage": "building", "status": "active", "message": "Creating the structural frame.", "thoughts": "not public"}]})
        status, body, _ = self.request("/api/activity")
        self.assertEqual(status, 200)
        value = json.loads(body)
        self.assertTrue(value["available"])
        self.assertEqual(value["events"], [{"id": "build-1", "stage": "building", "status": "active", "message": "Creating the structural frame."}])
        self.assertNotIn("not public", body.decode())
        self.assertEqual(self.request("/api/model")[0], 200)

    def test_activity_none_temporarily_hides_panel_without_disabling_provider(self):
        self.replace_provider(lambda: None)
        status, body, _ = self.request("/api/activity")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"version": 1, "enabled": False, "available": True, "events": []})

    def test_bad_or_failed_provider_cannot_break_model_delivery_or_leak_errors(self):
        value = {"state": "running", "events": [{"id": "x", "stage": "building", "status": "active", "message": "x" * 241}]}
        self.replace_provider(lambda: value)
        self.assertEqual(self.request("/api/activity")[0], 503)
        self.assertEqual(self.request("/api/artifacts/model")[1], self.model.read_bytes())
        def failed():
            raise RuntimeError("private path /private/workspace/secrets")
        self.replace_provider(failed)
        status, body, _ = self.request("/api/activity")
        self.assertEqual(status, 503)
        self.assertNotIn(b"private", body)
        self.assertEqual(self.request("/api/model")[0], 200)

    def test_activity_provider_calls_do_not_overlap(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def provider():
            calls.append(1)
            entered.set()
            release.wait(2)
            return {"state": "ready", "events": [{"id": "result", "stage": "ready", "status": "done", "message": "Model and Grasshopper files are available."}]}
        self.replace_provider(provider)
        responses = []
        thread = threading.Thread(target=lambda: responses.append(self.request("/api/activity")))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.request("/api/activity")[0], 503)
            self.assertEqual(self.request("/api/model")[0], 200)
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            thread.join(2)
        self.assertEqual(responses[0][0], 200)


if __name__ == "__main__":
    unittest.main()
