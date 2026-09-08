import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import rhino3dm from 'rhino3dm';
import {decodeDocument} from '../src/decode.mjs';import {orthographicHeight,perspectiveDistance,sectionCoordinate,rowMajorToColumnMajor} from '../src/camera-math.mjs';
import {buildSceneModel,visibleWorldBounds,deliveryActions} from '../src/model-state.mjs';
import {createRequire} from 'node:module';
const THREE=createRequire(import.meta.url)('three');
const r=await rhino3dm();
test('projection switches preserve target-plane vertical framing',()=>{for(const distance of [.01,1,19,1000])for(const fov of [25,38,70])assert(Math.abs(perspectiveDistance(orthographicHeight(distance,fov),fov)-distance)<1e-9);});
test('section slider maps into model coordinates including negative origins',()=>{assert.equal(sectionCoordinate(-10,30,25),0);assert.equal(sectionCoordinate(-10,30,-1),-10);assert.equal(sectionCoordinate(-10,30,150),30);});
test('real 3dm reads layers, units, all named objects and embedded BRep face meshes',async()=>{const d=decodeDocument(r,await readFile('fixtures/courtyard-study.3dm'));assert.equal(d.units,'Meters');assert.equal(d.layers.length,5);assert.equal(d.objects.length,d.sourceCount);assert(d.objects.length>100);assert.equal(d.warnings.length,0,d.warnings.join('\n'));const b=d.objects.find(o=>o.kind==='Brep');assert(b);assert.equal(b.data.data.index.array.length,36);assert(d.objects.filter(o=>o.kind==='Mesh').every(o=>o.data.data.attributes.position.array.length>0));});
test('BRep without a stored display mesh is reported and never synthesized',()=>{const d=new r.File3dm();const b=r.Brep.createFromBoundingBox(new r.BoundingBox(0,0,0,1,1,1));d.objects().addBrep(b,new r.ObjectAttributes());const result=decodeDocument(r,d.toByteArray());assert.equal(result.objects[0].data,null);assert(result.warnings[0].includes('no cached display mesh'));d.delete();b.delete();});
test('invalid archive fails clearly',()=>{assert.throws(()=>decodeDocument(r,new Uint8Array([1,2,3,4])),/not a readable/);});

test('block instances retain definition membership and row-major translations',()=>{const d=new r.File3dm(),m=new r.Mesh(),a=new r.ObjectAttributes();m.vertices().add(0,0,0);m.vertices().add(1,0,0);m.vertices().add(0,1,0);m.faces().addTriFace(0,1,2);const index=d.instanceDefinitions().add('block','','','',[0,0,0],[m],[a]);const definition=d.instanceDefinitions().get(index);const instance=new r.InstanceReference(definition.id,r.Transform.translationXYZ(5,6,7));d.objects().addInstanceObject(instance,a);const result=decodeDocument(r,d.toByteArray());assert.equal(result.definitions.length,1);const ref=result.objects.find(o=>o.kind==='Instance');assert.deepEqual(rowMajorToColumnMajor(ref.transform).slice(12,15),[5,6,7]);assert.equal(result.objects.filter(o=>o.definitionObject).length,1);assert.equal(result.definitions[0].objectIds[0],result.objects.find(o=>o.definitionObject).id);assert.equal(result.warnings.length,0);d.delete();m.delete();a.delete();instance.delete();definition.delete();});

test('valid native BRep without caches still offers registered download and native open',()=>{
 const d=new r.File3dm(),b=r.Brep.createFromBoundingBox(new r.BoundingBox(0,0,0,1,1,1));d.objects().addBrep(b,new r.ObjectAttributes());
 const decoded=decodeDocument(r,d.toByteArray()),built=buildSceneModel(decoded,THREE);
 assert.equal(built.pickables.length,0);assert(built.warnings[0].includes('no cached display mesh'));
 const meta={allow_open:true,artifacts:[{id:'model',kind:'3dm',filename:'valid.3dm'},{id:'grasshopper',kind:'gh'}]};
 assert.deepEqual(deliveryActions(meta),{download:true,rhino:true,grasshopper:true});
 assert.deepEqual(deliveryActions({...meta,allow_open:false}),{download:true,rhino:false,grasshopper:false});
 assert.deepEqual(deliveryActions(meta,new Blob([d.toByteArray()])),{download:true,rhino:false,grasshopper:false});
 d.delete();b.delete();
});

test('visible bounds ignore hidden distant geometry and hidden ancestor branches',()=>{
 const root=new THREE.Group(),visible=new THREE.Mesh(new THREE.BoxGeometry(2,2,2));root.add(visible);
 const hidden=new THREE.Mesh(new THREE.BoxGeometry(2,2,2));hidden.position.set(10000,0,0);hidden.visible=false;root.add(hidden);
 const group=new THREE.Group();group.position.set(0,20000,0);group.visible=false;
 const child=new THREE.Mesh(new THREE.BoxGeometry(2,2,2));child.position.set(4,5,6);group.add(child);root.add(group);
 assert(new THREE.Box3().setFromObject(root).max.x>10000); // Demonstrate the original failure.
 let box=visibleWorldBounds(root,THREE);assert.deepEqual(box.min.toArray(),[-1,-1,-1]);assert.deepEqual(box.max.toArray(),[1,1,1]);
 group.visible=true;box=visibleWorldBounds(root,THREE);assert.deepEqual(box.max.toArray(),[5,20006,7]);
 group.visible=false;hidden.visible=true;box=visibleWorldBounds(root,THREE);assert.equal(box.max.x,10001);
 hidden.visible=false;visible.visible=false;assert(visibleWorldBounds(root,THREE).isEmpty());
});

function triangle(offset=0){const m=new r.Mesh();m.vertices().add(offset,0,0);m.vertices().add(offset+1,0,0);m.vertices().add(offset,1,0);m.faces().addTriFace(0,1,2);return m;}
test('3dm layer visibility is applied before initial model bounds',()=>{
 const d=new r.File3dm(),shown=new r.Layer(),hidden=new r.Layer();shown.name='Shown';hidden.name='Hidden';hidden.visible=false;d.layers().add(shown);d.layers().add(hidden);
 const a=new r.ObjectAttributes();a.layerIndex=0;d.objects().addMesh(triangle(),a);a.layerIndex=1;d.objects().addMesh(triangle(10000),a);
 const decoded=decodeDocument(r,d.toByteArray()),built=buildSceneModel(decoded,THREE);assert.equal(built.pickables.length,2);
 let box=visibleWorldBounds(built.model,THREE);assert.equal(box.max.x,1);
 const distant=built.pickables.find(o=>o.userData.record.layer===1);distant.visible=true;box=visibleWorldBounds(built.model,THREE);assert.equal(box.max.x,10001);
 distant.visible=false;assert.equal(visibleWorldBounds(built.model,THREE).max.x,1);d.delete();
});

test('nested MaterialFromParent block geometry inherits the outer instance color and opacity',()=>{
 const d=new r.File3dm(),material=new r.Material();material.diffuseColor={r:230,g:70,b:120,a:255};material.transparency=.35;d.materials().add(material);
 const inherit=new r.ObjectAttributes();inherit.materialSource=r.ObjectMaterialSource.MaterialFromParent;
 const innerIndex=d.instanceDefinitions().add('inner','','','',[0,0,0],[triangle()],[inherit]);const inner=d.instanceDefinitions().get(innerIndex);
 const innerRef=new r.InstanceReference(inner.id,r.Transform.translationXYZ(1,0,0));
 const outerIndex=d.instanceDefinitions().add('outer','','','',[0,0,0],[innerRef],[inherit]);const outer=d.instanceDefinitions().get(outerIndex);
 const outerRef=new r.InstanceReference(outer.id,r.Transform.translationXYZ(5,6,7)),assigned=new r.ObjectAttributes();assigned.materialSource=r.ObjectMaterialSource.MaterialFromObject;assigned.materialIndex=0;d.objects().addInstanceObject(outerRef,assigned);
 const decoded=decodeDocument(r,d.toByteArray()),built=buildSceneModel(decoded,THREE);assert.equal(built.pickables.length,1);assert.equal(decoded.objects.filter(o=>o.materialFromParent).length,2);
 const appearance=built.pickables[0].material;assert(Math.abs(appearance.opacity-.65)<1e-8);const expected=new THREE.Color(230/255,70/255,120/255).convertSRGBToLinear();assert(appearance.color.distanceTo?appearance.color.distanceTo(expected)<1e-8:appearance.color.equals(expected));
 const box=visibleWorldBounds(built.model,THREE);assert.deepEqual(box.min.toArray(),[6,6,7]);assert.deepEqual(box.max.toArray(),[7,7,7]);d.delete();
});
