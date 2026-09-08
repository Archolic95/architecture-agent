"""Deterministic CPU z-buffer previews from the retained mesh sidecar."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def clipped(triangles, axis, offset, sign=1):
    result=[]
    for tri in triangles:
        poly=list(tri)
        output=[]
        for i,a in enumerate(poly):
            b=poly[(i+1)%len(poly)];da=sign*(a[axis]-offset);db=sign*(b[axis]-offset)
            if da>=0:output.append(a)
            if (da>=0)!=(db>=0):output.append(a+(b-a)*da/(da-db))
        for i in range(1,len(output)-1):result.append([output[0],output[i],output[i+1]])
    return np.asarray(result).reshape((-1,3,3))


def render(directory, *, roof_layers=("Roof",), plan_hide_layers=("Roof", "Site"),
           plan_cut=None, section_axis="y", section_offset=None):
    directory=Path(directory)
    data=json.loads((directory/"model.preview.json").read_text())
    manifest=json.loads((directory/"scene.json").read_text())
    title=str(manifest.get("title", "Architecture model")).replace("—", "-").replace("–", "-")
    layers={item["index"]:item["name"] for item in data["layers"]}
    roof_layers={name.casefold() for name in roof_layers}
    plan_hide_layers={name.casefold() for name in plan_hide_layers}
    parts=[]
    for obj in data["objects"]:
        tris=np.asarray(obj["data"]["data"]["attributes"]["position"]["array"]).reshape(-1,3,3)
        parts.append((layers[obj["layer"]].casefold(),tris,np.array([obj["color"][x]/255 for x in "rgb"]),obj["opacity"]))
    if not parts:raise ValueError("There are no preview objects to render")
    bounds=np.vstack([t.reshape(-1,3) for n,t,c,a in parts]);lo=bounds.min(0);hi=bounds.max(0)
    axis_index="xyz".index(section_axis)
    plan_cut=float(lo[2]+1.5 if plan_cut is None else plan_cut)
    section_offset=float((lo[axis_index]+hi[axis_index])/2 if section_offset is None else section_offset)
    if not np.isfinite([plan_cut,section_offset]).all():raise ValueError("Cut coordinates must be finite")
    matched_roof_layers=roof_layers.intersection(layer.casefold() for layer in layers.values())
    views=["aerial","roof_off","section","plan"]
    report={"units":"metres", "projection":"orthographic", "section_caps":False,
            "plan_cut":plan_cut,"section_axis":section_axis,"section_offset":section_offset,
            "roof_layers":sorted(matched_roof_layers),"plan_hide_layers":sorted(plan_hide_layers),
            "views":{},"skipped":{}}
    if not matched_roof_layers:
        views.remove("roof_off")
        report["skipped"]["roof_off"]="No requested roof layer exists; supply --roof-layer to choose one."
    light=np.array([-.45,-.6,1]);light/=np.linalg.norm(light)
    for view in views:
        width,height=1280,1000
        canvas=np.ones((height,width,3))*np.array([.94,.933,.91]);depth=np.full((height,width),-np.inf)
        elev,azim=(np.radians(33),np.radians(-58)) if view!="section" else (np.radians(12),np.radians(-80))
        toward=np.array([np.cos(elev)*np.cos(azim),np.cos(elev)*np.sin(azim),np.sin(elev)])
        if view=="section" and section_axis in "xy":
            toward=np.zeros(3);toward[axis_index]=-1;toward[2]=.2;toward/=np.linalg.norm(toward)
        if view=="plan":toward=np.array([0.,0.,1.])
        right=np.array([-toward[1],toward[0],0.]) if view!="plan" else np.array([1.,0.,0.])
        right/=np.linalg.norm(right);up=np.cross(toward,right)
        basis=np.array([right,up,toward]);center=(lo+hi)/2;projected=(bounds-center)@basis.T
        span=projected.max(0)-projected.min(0);scale=min((width-100)/span[0],(height-170)/span[1])
        triangles=[]
        for layer,tris,color,alpha in parts:
            if view=="roof_off" and layer in roof_layers:continue
            if view=="section":tris=clipped(tris,axis_index,section_offset)
            if view=="plan":
                if layer in plan_hide_layers:continue
                tris=clipped(tris,2,plan_cut,-1)
            for tri in tris:
                normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);norm=np.linalg.norm(normal)
                if norm<1e-12:continue
                normal/=norm
                shade=.65+.35*max(0,float(normal@light))
                p=(tri-center)@basis.T;p[:,0]=p[:,0]*scale+width/2;p[:,1]=-p[:,1]*scale+height/2+40
                triangles.append((p,color*shade,alpha))
        if not triangles:raise ValueError(f"{view} has no geometry at the requested cut/layers")
        triangles.sort(key=lambda t:(t[2]<.999,float(t[0][:,2].mean())))
        for p,color,alpha in triangles:
            x0=max(0,int(np.floor(p[:,0].min())));x1=min(width-1,int(np.ceil(p[:,0].max())))
            y0=max(0,int(np.floor(p[:,1].min())));y1=min(height-1,int(np.ceil(p[:,1].max())))
            if x1<x0 or y1<y0:continue
            denominator=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
            if abs(denominator)<1e-9:continue
            yy,xx=np.mgrid[y0:y1+1,x0:x1+1];xx=xx+.5;yy=yy+.5
            a=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/denominator
            b=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/denominator;c=1-a-b
            z=a*p[0,2]+b*p[1,2]+c*p[2,2]
            region_depth=depth[y0:y1+1,x0:x1+1];region=canvas[y0:y1+1,x0:x1+1]
            visible=(a>=-1e-8)&(b>=-1e-8)&(c>=-1e-8)&(z>region_depth+1e-7)
            region[visible]=region[visible]*(1-alpha)+color*alpha
            if alpha>=.999:region_depth[visible]=z[visible]
        image=Image.fromarray((np.clip(canvas,0,1)*255).astype('uint8'));draw=ImageDraw.Draw(image)
        label={"aerial":"EXTERIOR / ORTHOGRAPHIC PREVIEW","roof_off":"ROOF REMOVED / INTERIOR PREVIEW","section":"SECTION / UNCAPPED DISPLAY CLIP","plan":f"PLAN CLIP / Z {plan_cut:g}m / UNCAPPED"}[view]
        draw.text((42,24),label,fill="#283a35",font_size=25)
        draw.text((42,63),f'{title[:55]}  |  {len(data["objects"])} native extrusions',fill="#62716c",font_size=19)
        image.save(directory/f"{view}.png")
        report["views"][view]={"file":f"{view}.png","triangles":len(triangles)}
    (directory/"preview-views.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("directory")
    p.add_argument("--roof-layer",action="append",help="Case-insensitive layer to hide in roof-off view; repeatable")
    p.add_argument("--plan-hide-layer",action="append",help="Layer to omit from plan; defaults Roof and Site")
    p.add_argument("--plan-cut",type=float,help="Absolute Z coordinate for plan clip; default model minimum Z + 1.5m")
    p.add_argument("--section-axis",choices=("x","y","z"),default="y")
    p.add_argument("--section-offset",type=float,help="Absolute clip coordinate; default centre of model bounds")
    args=p.parse_args()
    print(json.dumps(render(args.directory,roof_layers=args.roof_layer or ("Roof",),
          plan_hide_layers=args.plan_hide_layer or ("Roof","Site"),plan_cut=args.plan_cut,
          section_axis=args.section_axis,section_offset=args.section_offset)))
