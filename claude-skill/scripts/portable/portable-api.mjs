// Read-only, in-memory transport for one generated native/preview pair.
import {validatePairedPreview} from './preview.mjs';

export function decodeBase64(value) {
  return Uint8Array.from(atob(value), character => character.charCodeAt(0));
}

export async function sha256(bytes, cryptoProvider = globalThis.crypto) {
  if (!cryptoProvider?.subtle) throw new Error('This browser cannot verify the portable files. Open the downloaded HTML in a current desktop browser.');
  return [...new Uint8Array(await cryptoProvider.subtle.digest('SHA-256', bytes))]
    .map(value => value.toString(16).padStart(2, '0')).join('');
}

export async function createPortableAPI(payload, cryptoProvider = globalThis.crypto) {
  if (payload?.version !== 1 || !Array.isArray(payload.files) || payload.files.length !== 3)
    throw new Error('Invalid portable model package.');
  const files = new Map();
  for (const entry of payload.files) {
    if (!['native', 'preview', 'validation'].includes(entry.role) || files.has(entry.role) ||
        typeof entry.filename !== 'string' || !entry.filename || /[/\\]/.test(entry.filename) ||
        !/^[a-f0-9]{64}$/.test(entry.sha256) || typeof entry.base64 !== 'string')
      throw new Error('Invalid portable file descriptor.');
    const bytes = decodeBase64(entry.base64);
    if (bytes.byteLength !== entry.bytes || await sha256(bytes, cryptoProvider) !== entry.sha256)
      throw new Error(`Portable file integrity check failed: ${entry.filename}`);
    files.set(entry.role, {...entry, bytes});
  }
  const native = files.get('native'), preview = files.get('preview'), validation = files.get('validation');
  if (!native || !preview || !validation || !/\.3dm$/i.test(native.filename))
    throw new Error('The portable package requires a native Rhino file and its paired preview.');
  const text = entry => new TextDecoder('utf-8', {fatal:true}).decode(entry.bytes);
  const report = JSON.parse(text(validation)), document = JSON.parse(text(preview));
  const parts = report.parts;
  if (!Array.isArray(parts) || !parts.length || parts.length > 20000 || report.objects !== parts.length ||
      report.files?.[native.filename] !== native.sha256 || report.files?.[preview.filename] !== preview.sha256)
    throw new Error('Native model and preview do not match the generation report.');
  const nativeIds = parts.map(part => part.native_id);
  if (nativeIds.some(id => typeof id !== 'string' || !id) || new Set(nativeIds).size !== nativeIds.length ||
      parts.some(part => ['valid','solid','mesh_closed','outward_winding'].some(check => part[check] !== true)))
    throw new Error('Preview requires successful, identifiable geometry checks in its report.');
  const artifact = {id:'model', kind:'3dm', filename:native.filename, sha256:native.sha256, url:'/api/artifacts/model'};
  const descriptor = {kind:'explicit_generated_mesh_sidecar', url:'/api/preview', sha256:preview.sha256,
    native_artifact_id:artifact.id, native_sha256:native.sha256, component_count:parts.length};
  validatePairedPreview(document, descriptor, artifact);
  const previewIds = new Set(document.objects.map(row => row.id));
  if (previewIds.size !== nativeIds.length || nativeIds.some(id => !previewIds.has(id)))
    throw new Error('Preview components do not match the native component manifest.');
  const meta = {version:'0.1.0', title:payload.title, subtitle:'Portable model · stored in this file',
    frame:{up:'Z', units:'from_3dm'}, allow_open:false, preview:descriptor, artifacts:[artifact]};
  const json = value => new Response(JSON.stringify(value), {headers:{'Content-Type':'application/json'}});
  return async function portableAPI(path, options = {}) {
    if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    if ((options.method || 'GET').toUpperCase() !== 'GET')
      throw new Error('Native application dispatch is unavailable in this portable viewer.');
    if (path === '/api/model') return json(meta);
    if (path === '/api/activity') return json({version:1, enabled:false, available:false, events:[]});
    if (path === '/api/preview') return new Response(preview.bytes, {headers:{'Content-Type':'application/json'}});
    if (path === '/api/artifacts/model') return new Response(native.bytes, {headers:{'Content-Type':'application/octet-stream'}});
    throw new Error('This portable viewer only serves its embedded model and preview.');
  };
}

let sessionAPI;
export async function initializePortable(payload) {
  if (sessionAPI) throw new Error('The portable model is already initialized.');
  sessionAPI = await createPortableAPI(payload);
}
export async function api(path, options) {
  if (!sessionAPI) throw new Error('Portable model verification has not completed.');
  return sessionAPI(path, options);
}
