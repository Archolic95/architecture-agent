// Reads display geometry already present in 3dm. Never substitutes a BRep control cage.
export function decodeDocument(rhino, bytes) {
  const doc=rhino.File3dm.fromByteArray(new Uint8Array(bytes));
  if(!doc) throw new Error('This file is not a readable Rhino 3dm archive.');
  const result={objects:[],layers:[],definitions:[],warnings:[],units:'Model units',sourceCount:doc.objects().count};
  try {
    for(const name of ['Millimeters','Centimeters','Meters','Inches','Feet','None']) if(doc.settings().modelUnitSystem===rhino.UnitSystem[name]) result.units=name;
    for(let i=0;i<doc.layers().count;i++) {const l=doc.layers().get(i);result.layers.push({index:l.index,name:l.fullPath||l.name,visible:l.visible,color:l.color});l.delete();}
    for(let i=0;i<doc.instanceDefinitions().count;i++) {const d=doc.instanceDefinitions().get(i);result.definitions.push({id:d.id,objectIds:d.getObjectIds()});d.delete();}
    for(let i=0;i<doc.objects().count;i++) {
      const item=doc.objects().get(i),g=item.geometry(),a=item.attributes();
      const row={id:a.id,name:a.name||`Object ${i+1}`,layer:a.layerIndex,visible:a.visible,definitionObject:a.isInstanceDefinitionObject,color:a.drawColor(doc),kind:'',data:null,opacity:1,materialFromParent:a.materialSource===rhino.ObjectMaterialSource.MaterialFromParent,userStrings:a.getUserStrings()};
      try {
        let materialIndex=a.materialIndex;
        if(a.materialSource===rhino.ObjectMaterialSource.MaterialFromLayer || row.materialFromParent){const layer=doc.layers().get(a.layerIndex);materialIndex=layer?.renderMaterialIndex ?? -1;layer?.delete();}
        if(materialIndex>=0 && materialIndex<doc.materials().count){const m=doc.materials().get(materialIndex);row.opacity=Math.max(.05,1-m.transparency); if(m.diffuseColor) row.color=m.diffuseColor;m.delete();}
        if(g.objectType===rhino.ObjectType.Mesh){row.kind='Mesh';row.data=g.toThreejsJSON();}
        else if(g.objectType===rhino.ObjectType.Brep){
          row.kind='Brep';const mesh=new rhino.Mesh(),faces=g.faces();let missing=0;
          for(let j=0;j<faces.count;j++){const face=faces.get(j),part=face.getMesh(rhino.MeshType.Any);if(part){mesh.append(part);part.delete();}else missing++;face.delete();}
          if(mesh.faces().count>0)row.data=mesh.toThreejsJSON();
          if(missing)result.warnings.push(`${row.name}: ${missing} BRep face(s) have no cached display mesh. Re-save with render meshes from Rhino.`);
          mesh.delete();faces.delete();
        } else if(g.objectType===rhino.ObjectType.Extrusion){row.kind='Extrusion';const mesh=g.getMesh(rhino.MeshType.Any);if(mesh){row.data=mesh.toThreejsJSON();mesh.delete();}else result.warnings.push(`${row.name}: extrusion has no cached display mesh.`);}
        else if(g.objectType===rhino.ObjectType.Curve){
          row.kind='Curve'; const pts=[],domain=g.domain;
          // Sampling is a display approximation; exact curves stay in the source 3dm.
          const poly=g.tryGetPolyline();
          if(poly){for(let j=0;j<poly.count;j++)pts.push(...poly.get(j));poly.delete();}
          else for(let j=0;j<=128;j++)pts.push(...g.pointAt(domain[0]+(domain[1]-domain[0])*j/128));
          row.data={data:{attributes:{position:{itemSize:3,type:'Float32Array',array:pts}}}};
        } else if(g.objectType===rhino.ObjectType.Point){row.kind='Point';row.data={data:{attributes:{position:{itemSize:3,type:'Float32Array',array:g.location}}}};}
        else if(g.objectType===rhino.ObjectType.InstanceReference){row.kind='Instance';row.definitionId=g.parentIdefId;row.transform=g.xform.toFloatArray(true);}
        else {row.kind='Unsupported';result.warnings.push(`${row.name}: unsupported display type (annotations, SubD and other non-mesh types are not approximated).`);}
        result.objects.push(row);
      } catch(error){result.warnings.push(`${row.name}: ${error.message}`);}
      finally{a.delete();g.delete();item.delete();}
    }
    return result;
  } finally{doc.delete();}
}
