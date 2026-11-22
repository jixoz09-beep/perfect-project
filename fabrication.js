import {buildSurface} from 'precision';
import * as T from 'three';
import {buildGeometry} from 'geometry';
import {validateFabrication} from 'manufacturing';
const colorMat={steel:'#81909c',aluminum:'#c5cbd0',copper:'#cb874f',rubber:'#25282c',carbon:'#45464a',plastic:'#45515b'};
export function mergePieces(pieces,{normalize=true}={}){
 const pos=[],colors=[],index=[];for(const {g,matrix=new T.Matrix4(),color='#ffffff',tint=null}of pieces){const a=g.attributes.position,ix=g.index?.array||Array.from({length:a.count},(_,i)=>i),offset=pos.length/3,c=new T.Color(color),v=new T.Vector3();for(let i=0;i<a.count;i++){v.fromBufferAttribute(a,i).applyMatrix4(matrix);pos.push(v.x,v.y,v.z);const cc=tint?new T.Color(tint[i*3],tint[i*3+1],tint[i*3+2]).multiply(c):c;colors.push(cc.r,cc.g,cc.b);}for(const i of ix)index.push(offset+i);g.dispose();}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('color',new T.Float32BufferAttribute(colors,3));g.setIndex(index);g.computeVertexNormals();g.computeBoundingBox();const box=g.boundingBox,size=box.getSize(new T.Vector3()),center=box.getCenter(new T.Vector3());
 if(size.toArray().some(v=>!Number.isFinite(v)||v<=0)||pos.length>900000)throw Error('형상의 크기 또는 정점 수를 확인하세요.');
 g.userData.dimensions=size.toArray();g.userData.origin=center.toArray();if(normalize){g.translate(-center.x,-center.y,-center.z);g.scale(1/size.x,1/size.y,1/size.z);}const uv=[];const points=g.attributes.position;for(let i=0;i<points.count;i++)uv.push(points.getX(i)+.5,points.getY(i)+.5);g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.computeBoundingBox();g.computeBoundingSphere();return g;
}
function shape(poly,holes=[]){const s=new T.Shape();poly.forEach(([x,y],i)=>i?s.lineTo(x,y):s.moveTo(x,y));s.closePath();for(const h of holes){const p=new T.Path();if(h.kind==='rect'){const w=h.size/2,hh=(h.height??h.size)/2;p.moveTo(h.x-w,h.y-hh);p.lineTo(h.x-w,h.y+hh);p.lineTo(h.x+w,h.y+hh);p.lineTo(h.x+w,h.y-hh);p.closePath();}else p.absarc(h.x,h.y,h.size/2,0,Math.PI*2,true);s.holes.push(p);}return s;}
const rect=(w,h)=>[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]];
function extrude(s,depth,bevel=0){const g=new T.ExtrudeGeometry(s,{depth,bevelEnabled:bevel>0,bevelThickness:bevel,bevelSize:bevel,bevelSegments:2,curveSegments:24,steps:1});g.translate(0,0,-depth/2);return g;}
function ring(outer,inner,width){const s=new T.Shape();s.absarc(0,0,outer/2,0,Math.PI*2,false);if(inner>0){const p=new T.Path();p.absarc(0,0,inner/2,0,Math.PI*2,true);s.holes.push(p);}return extrude(s,width);}
export function buildFabricatedGeometry(raw){
 const f=validateFabrication(raw),p=f.params,items=[],add=(g,pos=[0,0,0],rot=[0,0,0],color='#ffffff')=>{g.rotateX(rot[0]);g.rotateY(rot[1]);g.rotateZ(rot[2]);g.translate(...pos);items.push({g,color});},box=(w,h,d,pos=[0,0,0],color='#ffffff')=>add(new T.BoxGeometry(w,h,d,2,2,2),pos,undefined,color),cyl=(d,len,pos=[0,0,0],axis='Y',color='#ffffff')=>add(new T.CylinderGeometry(d/2,d/2,len,32,2),pos,axis==='X'?[0,0,Math.PI/2]:axis==='Z'?[Math.PI/2,0,0]:[0,0,0],color);
 const tube=(od,id,len,pos=[0,0,0],axis='Y')=>add(ring(od,id,len),pos,axis==='Y'?[Math.PI/2,0,0]:axis==='X'?[0,Math.PI/2,0]:[0,0,0]);
 const type=f.type;
 if(type==='profile'){
  if(f.operation==='revolve'){const pts=f.profile.map(([r,y])=>new T.Vector2(r,y));pts.push(pts[0].clone());add(new T.LatheGeometry(pts,64));}
  else add(extrude(shape(f.profile,f.holes),p.depth,p.bevel));
 }else if(['liner','pipe','damper_case'].includes(type))tube(p.outerD,p.innerD,p.length);
 else if(type==='block'||type==='head'){
  const count=p.cylinders,len=(count-1)*p.pitch+(p.bore||90)+(p.wall||25)*2,w=type==='block'?p.bore+p.wall*2:p.width,holes=[];
  for(let i=0;i<count;i++){const x=(i-(count-1)/2)*p.pitch;if(type==='block')holes.push({x,y:0,size:p.bore});else for(const z of [-25,25])holes.push({x,y:z,size:p.valveD});}
  add(extrude(shape(rect(len,w),holes),p.height),[0,0,0],[Math.PI/2,0,0]);
 }else if(['piston','brake_piston'].includes(type)){
  const r=p.diameter/2,h=p.height,profile=[[0,h/2],[r,h/2]];for(let i=0;i<p.grooves;i++){const y=h/2-7-i*5;profile.push([r,y],[r-1.2,y],[r-1.2,y-1.7],[r,y-1.7]);}profile.push([r,-h/2],[Math.max(.2,r-p.wall),-h/2],[Math.max(.2,r-p.wall),h/2-p.crown],[0,h/2-p.crown],[0,h/2]);add(new T.LatheGeometry(profile.map(v=>new T.Vector2(...v)),48));
 }else if(['ring','bearing'].includes(type)){
  if(type==='ring')add(ring(p.outerD,p.innerD,p.width));else{const span=(p.outerD-p.innerD)/2,band=span*.25;add(ring(p.outerD,p.outerD-band*2,p.width));add(ring(p.innerD+band*2,p.innerD,p.width));for(let i=0;i<p.balls;i++){const a=i*2*Math.PI/p.balls,r=(p.outerD+p.innerD)/4;add(new T.SphereGeometry(span*.28,10,8),[r*Math.cos(a),r*Math.sin(a),0]);}}
 }else if(type==='conrod'){
  add(ring(p.bigD+20,p.bigD,p.depth),[0,-p.length/2,0]);add(ring(p.smallD+16,p.smallD,p.depth),[0,p.length/2,0]);const low=-p.length/2+(p.bigD/2+10)*.8,high=p.length/2-(p.smallD/2+8)*.8;box(p.width,Math.max(1,high-low),p.depth*.65,[0,(low+high)/2,0]);
 }else if(type==='crank'){
  const n=p.cylinders;for(let i=0;i<=n;i++)cyl(p.journalD,p.pitch*.35,[(i-n/2)*p.pitch,0,0],'X');
  for(let i=0;i<n;i++){const x=(i-(n-1)/2)*p.pitch,a=(i%4===0||i%4===3)?0:Math.PI,y=Math.cos(a)*p.stroke/2,z=Math.sin(a)*p.stroke/2;cyl(p.pinD,p.pitch*.4,[x,y,z],'X');for(const side of [-1,1])box(p.pitch*.14,p.stroke/2+p.journalD,p.journalD*1.05,[x+side*p.pitch*.27,y/2,z/2]);}
 }else if(type==='cam'){
  cyl(p.diameter,p.length,[0,0,0],'X');for(let i=0;i<p.lobes;i++){const g=new T.CylinderGeometry(p.diameter*.65,p.diameter*.65,12,24);g.scale(1,1,1+p.lift/p.diameter);add(g,[(i-(p.lobes-1)/2)*(p.length-30)/Math.max(1,p.lobes-1),p.lift*.4,0],[0,0,Math.PI/2]);}
 }else if(type==='valve'){
  cyl(p.stemD,p.length);cyl(p.headD,4,[0,-p.length/2,0]);add(new T.ConeGeometry(p.headD/2,7,32),[0,-p.length/2+5,0]);
 }else if(type==='spring'){
  const pts=[];for(let i=0;i<=Math.ceil(p.coils*32);i++){const t=i/Math.ceil(p.coils*32),a=t*p.coils*2*Math.PI;pts.push(new T.Vector3(p.diameter/2*Math.cos(a),(t-.5)*(p.length-p.wire),p.diameter/2*Math.sin(a)));}add(new T.TubeGeometry(new T.CatmullRomCurve3(pts),Math.ceil(p.coils*40),p.wire/2,8,false));
 }else if(['shaft','damper_rod','tie_rod'].includes(type)){
  cyl(p.diameter,Math.max(.1,p.length-2*p.journalLength),[0,0,0],'Z');for(const side of [-1,1])cyl(p.journalD,p.journalLength,[0,0,side*(p.length-p.journalLength)/2],'Z');
 }else if(type==='gear'||type==='bevel'){
  const root=(p.teeth-2.5)*p.module/2,tip=(p.teeth+2)*p.module/2,poly=[];for(let i=0;i<p.teeth;i++)for(const [phase,r]of [[0,root],[.22,root],[.3,tip],[.7,tip],[.78,root]]){const a=(i+phase)*2*Math.PI/p.teeth;poly.push([r*Math.cos(a),r*Math.sin(a)]);}const g=extrude(shape(poly,[{x:0,y:0,size:p.bore}]),p.width);if(type==='bevel'){const a=g.attributes.position;for(let i=0;i<a.count;i++){const scale=1-(1-p.taper)*(a.getZ(i)/p.width+.5);a.setXY(i,a.getX(i)*scale,a.getY(i)*scale);}}add(g);
 }else if(type==='housing'||type==='tank_shell'){
  const w=p.width,h=p.height,d=p.depth,t=p.wall;box(w,t,d,[0,-h/2+t/2,0]);for(const sign of [-1,1]){box(t,h,d,[sign*(w-t)/2,0,0]);box(w-2*t,h,t,[0,0,sign*(d-t)/2]);}
 }else if(type==='rim'){
  add(ring(p.diameter,p.diameter-p.wall*2,p.width));add(ring(p.hubD+45,p.hubD,p.wall*2));for(let i=0;i<p.spokes;i++){const a=i*2*Math.PI/p.spokes,r0=(p.hubD+45)/2,r1=p.diameter/2-p.wall,len=r1-r0,g=new T.BoxGeometry(len,Math.max(12,p.diameter*.055),p.wall*2.5);g.rotateZ(a);add(g,[(r0+len/2)*Math.cos(a),(r0+len/2)*Math.sin(a),0]);}
 }else if(type==='tyre'){
  const r=(p.outerD+p.innerD)/4,t=(p.outerD-p.innerD)/4,g=new T.TorusGeometry(r,t,16,64);g.scale(1,1,p.width/(2*t));add(g);
 }else if(type==='hub'||type==='disc'){
  const od=type==='hub'?p.diameter:p.outerD,id=type==='hub'?p.bore:p.innerD,s=new T.Shape();s.absarc(0,0,od/2,0,Math.PI*2,false);const holes=[{x:0,y:0,size:id}];const n=type==='hub'?p.holes:p.vents,r=type==='hub'?p.boltCircle/2:od*.37;for(let i=0;i<n;i++){const a=i*2*Math.PI/n;holes.push({x:r*Math.cos(a),y:r*Math.sin(a),size:type==='hub'?12:7});}for(const h of holes){const hole=new T.Path();hole.absarc(h.x,h.y,h.size/2,0,Math.PI*2,true);s.holes.push(hole);}add(extrude(s,p.width));
 }else if(type==='caliper'){
  const w=p.width,h=p.height,d=p.depth,t=p.wall;box(w,t,d,[0,h/2-t/2,0]);for(const sign of [-1,1])box(w,h,t,[0,0,sign*(p.gap+t)/2]);
 }else if(type==='pad'||type==='panel'||type==='busbar')box(p.width,p.height,p.depth);
 else if(type==='arm'){
  const poly=[[-p.width/2,-p.length/2],[p.width/2,-p.length/2],[0,p.length/2]],holes=[[-p.width*.32,-p.length*.32],[p.width*.32,-p.length*.32],[0,p.length*.28]].map(([x,y])=>({x,y,size:p.hole}));add(extrude(shape(poly,holes),p.depth));
 }else if(type==='rack'){
  cyl(p.diameter,p.length,[0,0,0],'X');for(let i=0;i<p.teeth;i++)box(p.length/p.teeth*.45,p.diameter*.3,p.diameter*.75,[(i-(p.teeth-1)/2)*p.length/p.teeth,p.diameter*.5,0]);
 }else if(type==='stator'){
  add(ring(p.outerD,p.innerD+14,p.length));for(let i=0;i<p.slots;i++){const a=i*2*Math.PI/p.slots,g=new T.BoxGeometry(10,14,p.length);g.rotateZ(a);add(g,[(p.innerD/2+7)*Math.cos(a),(p.innerD/2+7)*Math.sin(a),0]);}
 }else if(type==='rotor'){
  cyl(p.diameter,p.length,[0,0,0],'Z');cyl(p.shaftD,p.length+80,[0,0,0],'Z');for(let i=0;i<p.magnets;i++){const a=i*2*Math.PI/p.magnets,g=new T.BoxGeometry(8,Math.PI*p.diameter/p.magnets*.6,p.length*.9);g.rotateZ(a);add(g,[(p.diameter/2-4)*Math.cos(a),(p.diameter/2-4)*Math.sin(a),0],[0,0,0],i%2?'#6085a5':'#ab6d62');}
 }else if(type==='winding'){
  for(let i=0;i<p.slots;i++){const a=i*2*Math.PI/p.slots,g=new T.TorusGeometry(p.wire,p.wire*.28,8,20);g.rotateX(Math.PI/2);g.scale(1,1,p.length/(p.wire*2*1.28));g.rotateZ(a);add(g,[p.diameter/2*Math.cos(a),p.diameter/2*Math.sin(a),0],[0,0,0],colorMat.copper);}
 }else if(type==='cell'){
  cyl(p.diameter,p.length);cyl(p.diameter*.65,2,[0,p.length/2+1,0],'Y','#bc6860');
 }else if(type==='bend_pipe'){
  const angle=p.angle*Math.PI/180,steps=48,pos=[],ix=[],ro=p.diameter/2,ri=ro-p.wall;for(let side=0;side<2;side++)for(let j=0;j<=steps;j++)for(let i=0;i<=24;i++){const t=j/steps*angle,a=i/24*2*Math.PI,r=side?ri:ro;pos.push((p.radius+r*Math.cos(a))*Math.cos(t),(p.radius+r*Math.cos(a))*Math.sin(t),r*Math.sin(a));}
  const layer=(steps+1)*25;for(let side=0;side<2;side++)for(let j=0;j<steps;j++)for(let i=0;i<24;i++){const a=side*layer+j*25+i,b=a+25;side?ix.push(a,a+1,b,a+1,b+1,b):ix.push(a,b,a+1,a+1,b,b+1);}for(const end of [0,steps])for(let i=0;i<24;i++){const a=end*25+i,b=a+layer;ix.push(a,a+1,b,a+1,b+1,b);}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setIndex(ix);add(g);
 }else if(type==='radiator_core'){
  for(let i=0;i<p.fins;i++)box(p.width,p.height/p.fins*.12,p.depth,[0,(i-(p.fins-1)/2)*p.height/p.fins,0]);for(const sign of [-1,1])box(20,p.height,p.depth,[sign*p.width/2,0,0]);
 }else if(type==='impeller'){
  add(ring(p.diameter,p.bore,4));for(let i=0;i<p.blades;i++){const a=i*2*Math.PI/p.blades,g=new T.BoxGeometry(p.diameter*.3,4,p.width);g.rotateZ(a+.35);add(g,[p.diameter*.3*Math.cos(a),p.diameter*.3*Math.sin(a),p.width/2]);}
 }else if(type==='beam'){
  const outer=rect(p.width,p.height),hole=new T.Path();hole.moveTo(-p.width/2+p.wall,-p.height/2+p.wall);hole.lineTo(-p.width/2+p.wall,p.height/2-p.wall);hole.lineTo(p.width/2-p.wall,p.height/2-p.wall);hole.lineTo(p.width/2-p.wall,-p.height/2+p.wall);hole.closePath();const s=shape(outer);s.holes.push(hole);add(extrude(s,p.length),[0,0,0],[0,Math.PI/2,0]);
 }else if(type==='plug'){cyl(p.diameter,p.length*.4,[0,-p.length*.3,0]);cyl(p.diameter*.7,p.length*.6,[0,p.length*.2,0],'Y','#ebe6db');}
 else throw Error('이 소요소의 형상 생성기가 없습니다.');
 const g=mergePieces(items);g.userData.dimensions=g.userData.dimensions.map(v=>v/1000);g.userData.fabricationType=f.type;return g;
}
export function buildPartGeometry(p,depth=0){
 if(depth>4)throw Error('중첩 조립 단계가 너무 깊습니다.');let g;
 if(p.surface)g=buildSurface(p.surface);
 else if(p.subassembly){const items=[];for(const a of p.subassembly.parts){const child=buildPartGeometry(a,depth+1),matrix=new T.Matrix4().compose(new T.Vector3(...a.position),new T.Quaternion().setFromEuler(new T.Euler(...a.rotation)),new T.Vector3(...a.size));items.push({g:child,matrix,color:a.material.color,tint:a.colors||child.attributes.color?.array});}g=mergePieces(items);}
 else if(p.fabrication)g=buildFabricatedGeometry(p.fabrication);
 else g=buildGeometry(p.shape,p.resolution,p.bodyShellVersion);
 if(p.vertices){if(p.vertices.length!==g.attributes.position.array.length)throw Error('저장된 조형 정점 수가 설계와 다릅니다.');g.attributes.position.array.set(p.vertices);g.attributes.position.needsUpdate=true;g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();}
 return g;
}
