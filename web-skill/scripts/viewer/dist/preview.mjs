// The sidecar is a declared display artifact, never a replacement native model.
export function validatePairedPreview(data, descriptor, artifact) {
  if (!descriptor || descriptor.kind !== 'explicit_generated_mesh_sidecar' ||
      descriptor.native_artifact_id !== artifact?.id || descriptor.native_sha256 !== artifact.sha256)
    throw new Error('Preview does not match the registered native model.');
  if (!data || data.previewKind !== descriptor.kind || data.units !== 'Meters' ||
      !Array.isArray(data.objects) || data.objects.length < 1 || data.objects.length > 20000 ||
      data.sourceCount !== data.objects.length || data.objects.length !== descriptor.component_count ||
      !Array.isArray(data.layers) || data.layers.length > 2000 || !Array.isArray(data.definitions) ||
      data.definitions.length !== 0 || !Array.isArray(data.warnings))
    throw new Error('Invalid or unsupported generated preview.');
  const ids = new Set(), layers = new Set();
  for (const layer of data.layers) {
    if (!Number.isInteger(layer.index) || layers.has(layer.index) || typeof layer.name !== 'string' ||
        !layer.color || !['r','g','b'].every(k=>Number.isFinite(layer.color[k])&&layer.color[k]>=0&&layer.color[k]<=255))
      throw new Error('Invalid preview layer.');
    layers.add(layer.index);
  }
  let coordinates = 0;
  for (const row of data.objects) {
    if (typeof row.id !== 'string' || ids.has(row.id) || row.kind !== 'Mesh' ||
        typeof row.name !== 'string' || !layers.has(row.layer) || row.definitionObject ||
        !Number.isFinite(row.opacity) || row.opacity < 0 || row.opacity > 1)
      throw new Error('Invalid preview component.');
    ids.add(row.id);
    if (!row.color || !['r', 'g', 'b'].every(k => Number.isFinite(row.color[k]) && row.color[k] >= 0 && row.color[k] <= 255))
      throw new Error('Invalid preview appearance.');
    const attributes = row.data?.data?.attributes, position = attributes?.position;
    if (position?.itemSize !== 3 || position.type !== 'Float32Array' ||
        !Array.isArray(position.array) || position.array.length < 9 || position.array.length % 9 ||
        !position.array.every(Number.isFinite) || row.data.data.index)
      throw new Error('Invalid preview triangle geometry.');
    for (const [key, attribute] of Object.entries(attributes)) {
      if (!['position', 'normal'].includes(key) || attribute.itemSize !== 3 || attribute.type !== 'Float32Array' ||
          !Array.isArray(attribute.array) || attribute.array.length !== position.array.length || !attribute.array.every(Number.isFinite))
        throw new Error('Unsupported preview attribute.');
    }
    coordinates += position.array.length;
    if (coordinates > 6000000) throw new Error('Generated preview is too large.');
  }
  return data;
}
