"""Original compact courtyard house; run directly in ordinary CPython."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import time
import numpy as np
from shapely.geometry import box
from geometry_kit import Scene


def build(length=14.0, storey_height=3.2):
    if not 13 <= length <= 18 or not 3 <= storey_height <= 4:
        raise ValueError("Demo parameters: length13–18m, storey_height3–4m")
    s = Scene("Courtyard House — standalone original")
    depth = 11.0
    court = [length/2-2,4,length/2+2,8]
    concrete=(.86,.84,.79,1); white=(.94,.94,.91,1); timber=(.57,.34,.18,1)
    dark=(.20,.24,.23,1); glass=(.47,.68,.69,.25)
    courtyard = box(*court)
    stair_void = box(.80,.80,2.65,5.50)
    def region(cid, shape, z, h, layer, color, **kw):
        if shape.geom_type != "Polygon":
            raise ValueError("Demo requires a connected profile")
        return s.add_profile(cid, list(shape.exterior.coords), holes_xy=[list(r.coords) for r in shape.interiors],
                             z0=z,height=h,layer=layer,color=color,**kw)
    def solid(cid,b,layer,color,**kw):
        return s.add_box(cid,b,layer=layer,color=color,**kw)
    solid("site.ground",[-2,-3,-.30,length+2,depth+2,-.25],"Site",(.60,.63,.53,1))
    for level in range(2):
        shape=box(0,0,length,depth).difference(courtyard)
        if level==1: shape=shape.difference(stair_void)
        region(f"floor.{level}",shape,level*storey_height,.22,"Floor slabs",concrete,metadata={"role":"floor_slab","storey":level,"openings":["courtyard"]+(["stair"] if level else [])})
    region("roof",box(-.2,-.2,length+.2,depth+.2).difference(courtyard),2*storey_height,.20,"Roof",white,metadata={"role":"roof","designed_void":"open_courtyard"})
    solid("terrace.slab",[-.2,-2,.02,length+.2,0,.20],"Terrace",concrete)
    for i in range(30):
        x=i*length/30
        solid(f"terrace.board.{i:02}",[x,-1.94,.18,x+length/30-.025,-.06,.25],"Terrace",timber)
    # Exterior wall profiles have actual window/door holes in local elevation.
    def wall(label, span, matrix, level, entry=False):
        height=storey_height-.22
        shape=box(0,0,span,height)
        count=4 if span==length else 3
        openings=[]
        for i in range(count):
            a=(i+.17)*span/count; b=(i+.83)*span/count
            sill=0 if entry and i==1 else .66
            top=height-.40
            shape=shape.difference(box(a,sill-.01 if sill==0 else sill,b,top))
            openings.append((i,a,b,sill,top))
        region(f"wall.{label}.{level}",shape,0,.20,"Exterior walls",white,transform=matrix,
               metadata={"role":"exterior_wall","storey":level,"opening_count":count})
        for i,a,b,sill,top in openings:
            # Entry doors stand open: retain jambs and head, omit glazing.
            frame=box(a-.035,max(0,sill-.035),b+.035,top+.035).difference(box(a+.035,sill+.035,b-.035,top-.035))
            region(f"frame.{label}.{level}.{i}",frame,.045,.06,"Window frames",dark,transform=matrix)
            if sill>0:
                region(f"glass.{label}.{level}.{i}",box(a+.035,sill+.035,b-.035,top-.035),.08,.02,"Glazing",glass,transform=matrix)
    for level in range(2):
        z=level*storey_height+.22
        front=np.array([[1,0,0,0],[0,0,-1,0],[0,1,0,z],[0,0,0,1]],float)
        back=front.copy();back[1,3]=depth
        left=np.array([[0,0,1,0],[1,0,0,0],[0,1,0,z],[0,0,0,1]],float)
        right=left.copy();right[0,3]=length-.20
        for label,span,matrix in [("south",length,front),("north",length,back),("west",depth,left),("east",depth,right)]:
            wall(label,span,matrix,level,entry=(label=="south" and level==0))
    # Courtyard glazing, posts and headers; a south opening is intentionally open.
    x0,y0,x1,y1=court
    for level in range(2):
        low=level*storey_height+.22;high=(level+1)*storey_height
        for side,coords in [("west",[x0-.08,y0,x0,y1]),("east",[x1,y0,x1+.08,y1]),("north",[x0,y1,x1,y1+.08]),("south",[x0,y0-.08,x1,y0])]:
            a,b,c,d=coords
            if not(side=="south" and level==0):
                solid(f"court.glass.{side}.{level}",[a,b,low,c,d,high-.20],"Courtyard",glass,metadata={"role":"courtyard_glazing","storey":level})
            solid(f"court.header.{side}.{level}",[a,b,high-.20,c,d,high],"Courtyard",dark)
        for i,(x,y) in enumerate([(x0,y0),(x1,y0),(x1,y1),(x0,y1)]):
            solid(f"court.post.{level}.{i}",[x-.045,y-.045,low,x+.045,y+.045,high],"Courtyard",dark)
    # Courtyard gravel and a low planted bed are explicitly open to the sky.
    region("court.gravel",courtyard,-.05,.06,"Courtyard ground",(.68,.66,.60,1))
    solid("court.bed",[x0+.65,y0+.65,.01,x1-.65,y1-.65,.30],"Courtyard ground",(.28,.39,.24,1))
    # 18 risers connect floor finish .22 to storey_height+.22, within slab void.
    steps=18;going=.25;rise=storey_height/steps
    for i in range(steps):
        top=.22+(i+1)*rise;y=1+i*going
        solid(f"stair.tread.{i:02}",[1,y,top-.12,2.4,y+going,top],"Stairs",timber,metadata={"role":"stair_tread","index":i,"riser":rise,"going":going})
        for side,x in [("left",.94),("right",2.43)]:
            solid(f"stair.post.{side}.{i:02}",[x,y+.10,top,x+.035,y+.135,top+1.0],"Stairs",dark)
    # Inclined stringers/handrails exercise affine placements of native extrusions.
    slope=storey_height/(steps*going)
    placement=np.eye(4);placement[2,1]=slope
    for side,x in [("left",.93),("right",2.43)]:
        solid(f"stair.stringer.{side}",[x,1,.22-slope-.16,x+.06,5.5,.22-slope-.02],"Stairs",dark,transform=placement)
        solid(f"stair.rail.{side}",[x,1,1.22-slope,x+.06,5.5,1.26-slope],"Stairs",dark,transform=placement)
    # Glazed guard around first-floor stair opening, leaving a top arrival gap.
    solid("stair.guard.upper",[.80,.82,storey_height+.22,.84,5.55,storey_height+1.27],"Stairs",glass)
    return s


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--length",type=float,default=14)
    parser.add_argument("--storey-height",type=float,default=3.2)
    args=parser.parse_args()
    started=time.perf_counter();scene=build(args.length,args.storey_height)
    receipt=scene.export(args.output)
    params={"length":args.length,"storey_height":args.storey_height}
    (args.output/"parameters.json").write_text(json.dumps(params,indent=2)+"\n")
    for name in ["geometry_kit.py","build_demo.py"]:
        shutil.copyfile(Path(__file__).with_name(name),args.output/name)
    (args.output/"timing.json").write_text(json.dumps({"wall_seconds":time.perf_counter()-started,"native_rhino_used":False},indent=2)+"\n")
    print(json.dumps({"output":str(args.output.resolve()),"objects":receipt["objects"],"wall_seconds":time.perf_counter()-started}))


if __name__=="__main__":main()
