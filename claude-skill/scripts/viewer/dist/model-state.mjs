import {rowMajorToColumnMajor} from './camera-math.mjs';

// Delivery belongs to the registered file, independently of browser mesh support.
export function deliveryActions(meta, localFile = null) {
  if (localFile) return {download: true, rhino: false, grasshopper: false};
  const artifacts = meta?.artifacts || [];
  const model = artifacts.some(a => a.kind === '3dm');
  return {
    download: model,
    rhino: model && !!meta?.allow_open,
    grasshopper: !!meta?.allow_open && artifacts.some(a => a.kind === 'gh'),
  };
}

export function inheritedAppearance(row, parent = null) {
  const inherit = row.materialFromParent && parent;
  return {
    color: inherit ? parent.color : row.color,
    opacity: inherit ? parent.opacity : row.opacity,
  };
}

// Box3.setFromObject includes hidden descendants. Walking visible branches here
// makes Fit and section limits describe only geometry the user can see.
export function visibleWorldBounds(root, THREE) {
  const result = new THREE.Box3();
  if (!root) return result;
  root.updateMatrixWorld(true);
  function visit(object) {
    if (!object.visible || object.userData.edge) return;
    if (object.geometry?.attributes.position?.count) {
      if (!object.geometry.boundingBox) object.geometry.computeBoundingBox();
      const box = object.geometry.boundingBox.clone().applyMatrix4(object.matrixWorld);
      if ([...box.min.toArray(), ...box.max.toArray()].every(Number.isFinite)) result.union(box);
    }
    for (const child of object.children) visit(child);
  }
  visit(root);
  return result;
}

export function buildSceneModel(data, THREE, edgesVisible = true) {
  const model = new THREE.Group(), pickables = [], warnings = [...data.warnings];
  const byId = new Map(data.objects.map(o => [o.id, o]));
  const definitions = new Map(data.definitions.map(d => [d.id, d]));
  const layers = new Map(data.layers.map(l => [l.index, l]));
  const parser = new THREE.BufferGeometryLoader();
  function create(row, ancestors = [], parentAppearance = null) {
    const appearance = inheritedAppearance(row, parentAppearance);
    let object;
    if (row.kind === 'Instance') {
      if (ancestors.includes(row.definitionId) || ancestors.length > 16) {
        warnings.push(`Cyclic or deeply nested block: ${row.name}`);
        return null;
      }
      const definition = definitions.get(row.definitionId);
      if (!definition) {warnings.push(`Missing block definition: ${row.name}`); return null;}
      object = new THREE.Group();
      for (const id of definition.objectIds) {
        const child = byId.get(id);
        if (child) {
          const built = create(child, [...ancestors, row.definitionId], appearance);
          if (built) object.add(built);
        }
      }
      object.applyMatrix4(new THREE.Matrix4().fromArray(rowMajorToColumnMajor(row.transform)));
    } else {
      if (!row.data) return null;
      const geometry = parser.parse(row.data);
      if (!geometry.attributes.position?.count) {geometry.dispose(); return null;}
      if (!geometry.attributes.normal && !['Curve','Point'].includes(row.kind)) geometry.computeVertexNormals();
      const color = new THREE.Color(appearance.color.r/255, appearance.color.g/255, appearance.color.b/255).convertSRGBToLinear();
      if (row.kind === 'Curve') object = new THREE.Line(geometry, new THREE.LineBasicMaterial({color}));
      else if (row.kind === 'Point') object = new THREE.Points(geometry, new THREE.PointsMaterial({color, size:3, sizeAttenuation:false}));
      else {
        const opacity = appearance.opacity;
        const material = new THREE.MeshLambertMaterial({color, side:THREE.DoubleSide, transparent:opacity<1, opacity, depthWrite:opacity>.95, vertexColors:!!geometry.attributes.color});
        object = new THREE.Mesh(geometry, material);
        const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geometry,28), new THREE.LineBasicMaterial({color:0x626b5b, transparent:true, opacity:opacity<1?.18:.24}));
        edge.userData.edge = true;
        edge.visible = edgesVisible;
        object.add(edge);
      }
      pickables.push(object);
    }
    object.name = row.name;
    object.userData.record = row;
    object.visible = row.visible !== false && layers.get(row.layer)?.visible !== false;
    return object;
  }
  for (const row of data.objects.filter(r => !r.definitionObject)) {
    const object = create(row);
    if (object) model.add(object);
  }
  return {model, pickables, warnings};
}

export function disposeSceneModel(model) {
  if(!model)return;
  const geometries=new Set(),materials=new Set();
  model.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)[].concat(o.material).forEach(m=>materials.add(m));});
  geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
}

export function layerIdentity(layer) {return `${layer.index}:${layer.name}`;}

export function prepareSceneCheckpoint(data,THREE,edgesVisible,layerVisibility=new Map()) {
  const built=buildSceneModel(data,THREE,edgesVisible);
  try {
    if(!built.pickables.length)throw new Error('No displayable geometry found in the checkpoint.');
    const layerRows=data.layers.map(layer=>{
      const objects=built.pickables.filter(o=>o.userData.record.layer===layer.index);
      const visible=layerVisibility.has(layerIdentity(layer))?layerVisibility.get(layerIdentity(layer)):layer.visible!==false;
      objects.forEach(o=>o.visible=visible&&o.userData.record.visible!==false);
      return {layer,objects,visible};
    }).filter(row=>row.objects.length);
    return {...built,layerRows};
  } catch(error){disposeSceneModel(built.model);throw error;}
}
