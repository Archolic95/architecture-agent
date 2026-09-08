import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from viewer_service import create_server


class PreviewPairingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'; self.assets.mkdir()
        (self.assets / 'index.html').write_text('viewer')
        self.native = self.root / 'model.3dm'; self.native.write_bytes(b'native-generation-one')
        self.preview = self.root / 'model.preview.json'
        self.document = {'previewKind': 'explicit_generated_mesh_sidecar', 'units': 'Meters',
                         'sourceCount': 1, 'objects': [{'id': 'native-component-1'}]}
        self.preview.write_text(json.dumps(self.document))
        self.validation = self.root / 'validation.json'
        self.report = {'objects': 1, 'files': {
            self.native.name: self.digest(self.native), self.preview.name: self.digest(self.preview)},
            'parts': [{'native_id': 'native-component-1', 'valid': True, 'solid': True,
                       'mesh_closed': True, 'outward_winding': True}]}
        self.validation.write_text(json.dumps(self.report))
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.shutdown(); self.server.server_close()
        self.temp.cleanup()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def start(self):
        self.server = create_server(assets_dir=self.assets, artifacts={
            'model': {'path': self.native, 'sha256': self.digest(self.native)}},
            preview={'path': self.preview, 'validation_path': self.validation,
                     'native_artifact_id': 'model'})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def get(self, path, authorized=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        headers = {'X-Viewer-Token': self.server.session_token} if authorized else {}
        connection.request('GET', path, headers=headers)
        response = connection.getresponse(); result = response.status, response.read()
        connection.close(); return result

    def test_explicit_preview_retains_native_download_and_authentication(self):
        self.start()
        status, payload = self.get('/api/model'); self.assertEqual(status, 200)
        metadata = json.loads(payload)
        self.assertEqual(metadata['preview']['native_sha256'], self.digest(self.native))
        self.assertEqual(metadata['artifacts'][0]['kind'], '3dm')
        self.assertNotIn(str(self.root), payload.decode())
        self.assertEqual(self.get('/api/preview'), (200, self.preview.read_bytes()))
        self.assertEqual(self.get('/api/artifacts/model'), (200, self.native.read_bytes()))
        self.assertEqual(self.get('/api/preview', False)[0], 401)

    def test_preview_from_another_generation_is_rejected(self):
        self.native.write_bytes(b'native-generation-two')
        with self.assertRaisesRegex(ValueError, 'do not match'):
            self.start()

    def test_missing_component_or_failed_geometry_check_is_rejected(self):
        self.document['objects'][0]['id'] = 'different-component'
        self.preview.write_text(json.dumps(self.document))
        self.report['files'][self.preview.name] = self.digest(self.preview)
        self.validation.write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError, 'components'):
            self.start()
        self.document['objects'][0]['id'] = 'native-component-1'
        self.preview.write_text(json.dumps(self.document))
        self.report['files'][self.preview.name] = self.digest(self.preview)
        self.report['parts'][0]['solid'] = False
        self.validation.write_text(json.dumps(self.report))
        with self.assertRaisesRegex(ValueError, 'geometry checks'):
            self.start()

    def test_editing_either_artifact_invalidates_the_pair(self):
        self.start()
        original = self.preview.read_bytes()
        self.preview.write_bytes(original + b' ')
        self.assertEqual(self.get('/api/preview')[0], 409)
        self.preview.write_bytes(original)
        self.native.write_bytes(b'changed after registration')
        self.assertEqual(self.get('/api/preview')[0], 409)


if __name__ == '__main__':
    unittest.main()
