import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePairedPreview} from '../src/preview.mjs';
import {deliveryActions, buildSceneModel} from '../src/model-state.mjs';
import * as THREE from '../dist/vendor/three.module.js';

const artifact = {id: 'model', kind: '3dm', sha256: 'native-hash'};
const descriptor = {kind: 'explicit_generated_mesh_sidecar', native_artifact_id: 'model', native_sha256: artifact.sha256, component_count: 1};
function preview() { return {previewKind: descriptor.kind, units: 'Meters', sourceCount: 1, warnings: [], definitions: [],
  layers: [{index: 0, name: 'Floor', color: {r: 220, g: 220, b: 220}}],
  objects: [{id: 'part-1', name: 'Floor panel', kind: 'Mesh', layer: 0, opacity: 1, color: {r: 220, g: 220, b: 220}, data: {
    metadata: {type: 'BufferGeometry'}, data: {attributes: {position: {itemSize: 3, type: 'Float32Array', array: [0, 0, 0, 1, 0, 0, 0, 1, 0]}}}}}]}; }

test('paired sidecar builds display geometry while native delivery remains a 3dm', () => {
  const data = validatePairedPreview(preview(), descriptor, artifact);
  const built = buildSceneModel(data, THREE);
  assert.equal(built.pickables.length, 1);
  assert.equal(built.pickables[0].geometry.attributes.position.count, 3);
  assert.deepEqual(deliveryActions({artifacts: [artifact], allow_open: true}), {download: true, rhino: true, grasshopper: false});
});

test('a sidecar cannot target another native artifact or component count', () => {
  assert.throws(() => validatePairedPreview(preview(), descriptor, {...artifact, sha256: 'other'}), /does not match/);
  assert.throws(() => validatePairedPreview(preview(), {...descriptor, component_count: 2}, artifact), /Invalid/);
});

test('invalid positions, foreign typed arrays and broken layers are refused before allocation', () => {
  let data = preview(); data.objects[0].data.data.attributes.position.array[0] = Infinity;
  assert.throws(() => validatePairedPreview(data, descriptor, artifact), /triangle geometry/);
  data = preview(); data.objects[0].data.data.attributes.position.type = 'Function';
  assert.throws(() => validatePairedPreview(data, descriptor, artifact), /triangle geometry/);
  data = preview(); data.objects[0].layer = 5;
  assert.throws(() => validatePairedPreview(data, descriptor, artifact), /component/);
});

import {modelClipRange} from '../src/camera-math.mjs';
test('fitted architectural camera retains submillimetre depth precision and zooms close', () => {
  const {near, far} = modelClipRange(25, 45);
  const depthStep = 45 * 45 * (far - near) / (far * near * (2 ** 24));
  assert(depthStep < 0.002);
  assert(far > 45 + 25);
  const close = modelClipRange(25, .03);
  assert(close.near < .03);
});
