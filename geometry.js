import * as THREE from 'three';
const T=THREE;
function merge(gs){const pos=[],uv=[],ix=[],lookup=new Map();for(let g of gs){const a=g.getAttribute('position'),idx=g.index?.array||Array.from({length:a.count},(_,i)=>i);for(const i of idx){const x=a.getX(i),y=a.getY(i),z=a.getZ(i),key=[x,y,z].map(v=>Math.round(v*1e6)).join(',');let k=lookup.get(key);if(k===undefined){k=pos.length/3;lookup.set(key,k);pos.push(x,y,z);uv.push(x+.5,z+.5);}ix.push(k);}g.dispose();}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(ix);g.computeVertexNormals();g.computeBoundingBox();const b=g.boundingBox,center=b.getCenter(new T.Vector3()),size=b.getSize(new T.Vector3());g.translate(-center.x,-center.y,-center.z);g.scale(1/Math.max(size.x,.001),1/Math.max(size.y,.001),1/Math.max(size.z,.001));g.computeVertexNormals();return g;}
export function buildGeometry(shape,res=16,bodyVersion=2){
 if(shape==="body"&&bodyVersion!==1)return buildBodyShell(res);
 const gs=[];const add=(g,s=[1,1,1],p=[0,0,0],r=[0,0,0])=>{g.applyMatrix4(new T.Matrix4().compose(new T.Vector3(...p),new T.Quaternion().setFromEuler(new T.Euler(...r)),new T.Vector3(...s)));gs.push(g);};
 const box=(s,p=[0,0,0],r=[0,0,0],n=5)=>add(new T.BoxGeometry(1,1,1,n,n,n),s,p,r);
 const cyl=(radius,height,p=[0,0,0],r=[0,0,0],inner=null)=>add(inner?new T.CylinderGeometry(radius,inner,height,32,8):new T.CylinderGeometry(radius,radius,height,32,8),[1,1,1],p,r);
 const tor=(r,t,p=[0,0,0],rot=[0,0,0])=>add(new T.TorusGeometry(r,t,16,48),[1,1,1],p,rot);
 if(['box','rounded','body','panel','wing'].includes(shape)){
  const g=new T.BoxGeometry(1,1,1,res,res,res),a=g.getAttribute('position');
  for(let i=0;i<a.count;i++){let x=a.getX(i),y=a.getY(i),z=a.getZ(i);
   if(shape==='rounded'||shape==='body'){const radius=shape==='body'?.065:.13;const q=new T.Vector3(x,y,z),v=new T.Vector3(Math.max(-.5+radius,Math.min(.5-radius,x)),Math.max(-.5+radius,Math.min(.5-radius,y)),Math.max(-.5+radius,Math.min(.5-radius,z)));q.sub(v).normalize().multiplyScalar(radius).add(v);x=q.x;y=q.y;z=q.z;}
   if(shape==='body'){const roof=x<-.3?.57+(x+.5)*1.25:x<.12?.95:x<.32?.95-(x-.12)*2.3:.49-(x-.32)*.2;const h=y+.5;y=h*roof-.5;z*=1-.19*Math.max(0,h-.35);}
   if(shape==='panel'){y+=.15*(1-4*x*x)*(1-4*z*z);}
   if(shape==='wing'){y=y*.15+(1-4*x*x)*.07;x+=.06*z;}
   a.setXYZ(i,x,y,z);
  }gs.push(g);
 }else if(shape==='sphere')add(new T.SphereGeometry(.5,32,24));
 else if(shape==='cylinder')cyl(.5,1);
 else if(shape==='tube'){
  const points=[];for(let i=0;i<=24;i++)points.push(new T.Vector2(.5,-.5+i/24));for(let i=24;i>=0;i--)points.push(new T.Vector2(.37,-.5+i/24));points.push(points[0].clone());add(new T.LatheGeometry(points,40));
 }else if(shape==='torus')tor(.37,.13);
 else if(shape==='frame'||shape==='spaceframe'){
  box([1,.1,.07],[0,0,.45]);box([1,.1,.07],[0,0,-.45]);for(let x of [-.44,-.15,.16,.44])box([.06,.08,.9],[x,0,0]);
  if(shape==='spaceframe'){for(let z of [-.45,.45]){box([.04,.5,.05],[-.23,.24,z]);box([.04,.5,.05],[.23,.24,z]);box([.52,.04,.05],[0,.48,z]);box([.7,.04,.05],[0,.25,z],[0,0,.68]);}box([.05,.05,.9],[-.23,.48,0]);box([.05,.05,.9],[.23,.48,0]);}
 }else if(shape==='engine'){
  box([.85,.65,.8],[0,-.08,0]);box([.95,.18,.86],[0,.34,0]);for(let x of [-.33,-.11,.11,.33]){box([.15,.055,.9],[x,.45,0]);cyl(.09,.25,[x,.1,.48],[Math.PI/2,0,0]);}box([.65,.15,.6],[0,-.46,0]);cyl(.22,.12,[.48,-.06,0],[0,0,Math.PI/2]);
 }else if(shape==='motor'||shape==='transmission'||shape==='differential'){
  cyl(.4,.75,[0,0,0],[0,0,Math.PI/2]);cyl(.25,.2,[.43,0,0],[0,0,Math.PI/2]);cyl(.075,.3,[.56,0,0],[0,0,Math.PI/2]);for(let x=-.3;x<=.3;x+=.1){cyl(.43,.02,[x,0,0],[0,0,Math.PI/2]);}box([.35,.18,.3],[0,.43,0]);
 }else if(shape==='shaft'){cyl(.07,1,[0,0,0],[0,0,Math.PI/2]);for(let x of [-.45,.45])cyl(.12,.09,[x,0,0],[0,0,Math.PI/2]);}
 else if(shape==='battery'){box([1,.3,1]);for(let z=-.4;z<=.41;z+=.16)box([.94,.03,.045],[0,.18,z]);box([.12,.08,.14],[.35,.19,.28]);box([.12,.08,.14],[.35,.19,-.28]);}
 else if(shape==='fins'||shape==='radiator'){box([1,.8,.65]);for(let x=-.46;x<=.47;x+=.05)box([.015,1,1],[x,0,0],undefined,2);box([1.04,.06,1],[0,-.47,0]);box([1.04,.06,1],[0,.47,0]);}
 else if(shape==='wheel'){tor(.36,.14);cyl(.245,.23,[0,0,0],[Math.PI/2,0,0]);for(let i=0;i<10;i++){const a=i*Math.PI/5;box([.045,.43,.06],[0,0,.14],[0,0,a],3);}cyl(.08,.3,[0,0,0],[Math.PI/2,0,0]);}
 else if(shape==='brake'){cyl(.5,.075,[0,0,0],[Math.PI/2,0,0]);cyl(.2,.2,[0,0,0],[Math.PI/2,0,0]);box([.2,.37,.17],[.36,0,.04]);}
 else if(shape==='spring'){
  const pts=[];for(let i=0;i<=256;i++){let t=i/256;pts.push(new T.Vector3(.35*Math.cos(t*Math.PI*16),t-.5,.35*Math.sin(t*Math.PI*16)));}add(new T.TubeGeometry(new T.CatmullRomCurve3(pts),256,.045,8,false));cyl(.1,1.15);cyl(.44,.045,[0,-.5,0]);cyl(.44,.045,[0,.5,0]);
 }else if(shape==='arm'){box([.08,.05,1],[-.33,0,0]);box([.8,.05,.07],[0,0,.24],[0,.55,0]);box([.8,.05,.07],[0,0,-.24],[0,-.55,0]);}
 else if(shape==='seat'){box([.9,.22,.85],[.05,-.39,0]);box([.23,.85,.85],[-.34,.05,0],[0,0,-.15]);box([.22,.2,.5],[-.43,.6,0]);}
 else box([1,1,1],[0,0,0],undefined,res);
 const g=merge(gs);g.computeBoundingSphere();return g;
}
export function prepareAdjacency(g){const n=g.attributes.position.count,a=Array.from({length:n},()=>new Set()),ix=g.index.array;for(let i=0;i<ix.length;i+=3){const x=ix[i],y=ix[i+1],z=ix[i+2];a[x].add(y).add(z);a[y].add(x).add(z);a[z].add(x).add(y);}return a.map(x=>[...x]);}
export function meshVolume(g){const a=g.attributes.position,ix=g.index.array;let v=0;const b=new T.Vector3(),c=new T.Vector3(),d=new T.Vector3();for(let i=0;i<ix.length;i+=3){b.fromBufferAttribute(a,ix[i]);c.fromBufferAttribute(a,ix[i+1]);d.fromBufferAttribute(a,ix[i+2]);v+=b.dot(c.cross(d))/6;}return Math.abs(v);}
export function applyBrush(mesh,hit,{mode='push',radius=.25,strength=.02,symmetry=true,color='#ed8b51',shift=false},stroke){
 const g=mesh.geometry,a=g.attributes.position,n=g.attributes.normal,col=g.attributes.color,adj=g.userData.adjacency||(g.userData.adjacency=prepareAdjacency(g));
 const inv=mesh.matrixWorld.clone().invert(),local=mesh.worldToLocal(hit.point.clone()),normal=hit.face.normal.clone().applyMatrix3(new T.Matrix3().getNormalMatrix(mesh.matrixWorld)).normalize(),centers=[{local,world:hit.point.clone(),normal}];
 if(symmetry&&Math.abs(local.z)>.00001){const l=local.clone();l.z*=-1;const nm=normal.clone();nm.z*=-1;centers.push({local:l,world:mesh.localToWorld(l.clone()),normal:nm});}
 const source=Float32Array.from(a.array),world=new T.Vector3(),p=new T.Vector3(),next=new T.Vector3(),delta=new T.Vector3(),avg=new T.Vector3(),brushColor=new T.Color(color);let touched=0;
 for(let i=0;i<a.count;i++){p.fromArray(source,i*3);world.copy(p).applyMatrix4(mesh.matrixWorld);let center=null,weight=0;for(const c of centers){const d=world.distanceTo(c.world);const w=d<radius?(1-d*d/(radius*radius))**2:0;if(w>weight){weight=w;center=c;}}if(!center||!weight)continue;touched++;
  if(mode==='paint'){col.setXYZ(i,T.MathUtils.lerp(col.getX(i),brushColor.r,weight*.3),T.MathUtils.lerp(col.getY(i),brushColor.g,weight*.3),T.MathUtils.lerp(col.getZ(i),brushColor.b,weight*.3));continue;}
  next.copy(world);
  if(mode==='smooth'){avg.set(0,0,0);for(const j of adj[i])avg.add(new T.Vector3().fromArray(source,j*3));if(adj[i].length){avg.divideScalar(adj[i].length).applyMatrix4(mesh.matrixWorld);next.lerp(avg,Math.min(.65,strength*10)*weight);}}
  else if(mode==='flatten'){const planePoint=stroke?.point||center.world,planeNormal=stroke?.normal||center.normal;const d=next.clone().sub(planePoint).dot(planeNormal);next.addScaledVector(planeNormal,-d*Math.min(.5,strength*10)*weight);}
  else if(mode==='pinch'){delta.copy(center.world).sub(world);delta.addScaledVector(center.normal,-delta.dot(center.normal));next.addScaledVector(delta,strength*4*weight);}
  else{delta.fromBufferAttribute(n,i).applyMatrix3(new T.Matrix3().getNormalMatrix(mesh.matrixWorld)).normalize();next.addScaledVector(delta,strength*weight*(mode==='pull'?-1:1)*(shift?-1:1));}
  next.applyMatrix4(inv);if([next.x,next.y,next.z].every(Number.isFinite))a.setXYZ(i,next.x,next.y,next.z);
 }
 if(mode==='paint')col.needsUpdate=true;else{a.needsUpdate=true;g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();}return touched;
}

/* Open body-in-white. X forward, Y up, Z left. No doors, glass, hood or trunk lid. */
export function buildBodyShell(res=16){
 const gs=[],push=g=>gs.push(g);
 const box=(s,p,n=3)=>{const g=new T.BoxGeometry(...s,n,n,n);g.translate(...p);push(g);};
 const beam=(a,b,w=.022)=>{const start=new T.Vector3(...a),end=new T.Vector3(...b),v=end.clone().sub(start),g=new T.BoxGeometry(w,v.length(),w,2,8,2);g.applyQuaternion(new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0),v.normalize()));g.translate(...start.add(end).multiplyScalar(.5).toArray());push(g);};
 const panel=(poly,z,thick=.006)=>{const s=new T.Shape();poly.forEach(([x,y],i)=>i?s.lineTo(x,y):s.moveTo(x,y));s.closePath();const g=new T.ExtrudeGeometry(s,{depth:thick,bevelEnabled:false,steps:1,curveSegments:16});g.translate(0,0,z-thick/2);push(g);};
 // Cabin floor, tunnel, rear load floor, firewall; cavities above remain open.
 const floorShape=new T.Shape(),outline=[[-.315,-.32],[-.245,-.32],[-.245,-.405],[.175,-.405],[.175,-.32],[.245,-.32],[.245,.32],[.175,.32],[.175,.405],[-.245,.405],[-.245,.32],[-.315,.32]];
 outline.forEach(([x,z],i)=>i?floorShape.lineTo(x,z):floorShape.moveTo(x,z));floorShape.closePath();
 const floor=new T.ExtrudeGeometry(floorShape,{depth:.009,bevelEnabled:false,steps:1});floor.rotateX(Math.PI/2);floor.translate(0,-.4005,0);push(floor);
 box([.42,.055,.07],[-.015,-.377,0],6);
 box([.19,.009,.64],[-.392,-.28,0],5);
 box([.012,.33,.81],[.246,-.24,0],7);
 box([.012,.24,.74],[-.245,-.255,0],6);
 for(const z of [-.447,.447]){
  box([.44,.061,.043],[-.025,-.384,z],8);
  beam([.225,-.355,z],[.086,.435,z*.85],.027); // A
  beam([-.055,-.355,z],[-.055,.455,z*.85],.026); // B
  beam([-.25,-.34,z],[-.224,.435,z*.85],.034); // C
  beam([-.224,.435,z*.85],[.086,.435,z*.85],.021);
  // Longitudinal engine and rear rails.
  box([.245,.054,.034],[.365,-.39,z*.57],5);
  box([.19,.055,.036],[-.399,-.37,z*.62],5);
  // Outer quarter/fender panels with open-bottom wheel arches.
  for(const [lo,hi,cx] of [[.259,.493,.325],[-.493,-.33,-.325]]){
   const poly=[[lo,-.075],[hi,-.075]];
   for(let j=24;j>=0;j--){const x=lo+(hi-lo)*j/24,u=(x-cx)/.087,y=Math.abs(u)<1?-.525+.287*Math.sqrt(1-u*u):-.422;poly.push([x,y]);}
   panel(poly,z,.006);
  }
  // Wheelhouse skins are semicircular tunnels, leaving the wheel cavity empty.
  for(const cx of [-.325,.325]){
   const positions=[],indices=[],seg=32;
   for(let j=0;j<=seg;j++){const t=Math.PI*j/seg,x=cx+.087*Math.cos(t),y=-.525+.287*Math.sin(t);for(const zz of [z*.72,z*1.055])positions.push(x,y,zz);}
   for(let j=0;j<seg;j++){const a=j*2;indices.push(a,a+2,a+1,a+1,a+2,a+3);}
   const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(positions,3));g.setIndex(indices);
   // Give the skin actual thickness using closed ribs; surface alone is decorative.
   const arc=[];for(let j=0;j<=32;j++){const t=Math.PI*j/32;arc.push([cx+.087*Math.cos(t),-.525+.287*Math.sin(t)]);}for(let j=32;j>=0;j--){const t=Math.PI*j/32;arc.push([cx+.085*Math.cos(t),-.525+.281*Math.sin(t)]);}panel(arc,z*.8875,Math.abs(z*.335));g.dispose();
   for(let j=0;j<seg;j++){const t=(j+.5)*Math.PI/seg,dt=Math.PI/seg;
    const a=[cx+.087*Math.cos(t-dt/2),-.525+.287*Math.sin(t-dt/2),z],
          b=[cx+.087*Math.cos(t+dt/2),-.525+.287*Math.sin(t+dt/2),z];
    beam(a,b,.009);
   }
  }
 }
 box([.035,.06,.91],[.482,-.36,0],6);
 box([.034,.075,.9],[-.482,-.34,0],6);
 // Roof is a thin crowned panel. Front and rear windscreens are openings.
 const nx=12,nz=16,pos=[],ix=[];
 for(let layer=0;layer<2;layer++)for(let i=0;i<=nx;i++)for(let j=0;j<=nz;j++){
  const x=-.224+.31*i/nx,z=-.386+.772*j/nz;
  const y=.438+.045*Math.sin(Math.PI*i/nx)*Math.sin(Math.PI*j/nz)-layer*.005;
  pos.push(x,y,z);
 }
 const row=nz+1,layerN=(nx+1)*row;
 for(let i=0;i<nx;i++)for(let j=0;j<nz;j++){const a=i*row+j,b=a+row;
  ix.push(a,b,a+1,a+1,b,b+1,a+layerN,a+1+layerN,b+layerN,a+1+layerN,b+1+layerN,b+layerN);
 }
 const wall=(a,b)=>ix.push(a,a+layerN,b,b,b+layerN,a+layerN);
 for(let i=0;i<nx;i++){wall(i*row,(i+1)*row);wall(i*row+nz,(i+1)*row+nz);}
 for(let j=0;j<nz;j++){wall(j,j+1);wall(nx*row+j,nx*row+j+1);}
 const roof=new T.BufferGeometry();roof.setAttribute('position',new T.Float32BufferAttribute(pos,3));roof.setIndex(ix);push(roof);
 beam([.086,.435,-.38],[.086,.435,.38],.021);
 beam([-.224,.435,-.38],[-.224,.435,.38],.022);
 // Cowl and rear deck surround the two windscreen openings.
 box([.036,.022,.85],[.247,-.065,0],8);
 box([.045,.022,.84],[-.33,-.055,0],8);
 // Suspension tower rings, not solid blocks across the engine bay.
 for(const x of [-.325,.325])for(const z of [-.29,.29]){
  const g=new T.TorusGeometry(.038,.006,8,24);g.rotateX(Math.PI/2);g.scale(1,1,1.7);g.translate(x,-.16,z);push(g);
 }
 const g=merge(gs);g.userData.bodyShellVersion=2;g.computeBoundingSphere();return g;
}
