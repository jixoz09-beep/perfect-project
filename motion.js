/* Editing contacts: swept triangle tests, not just endpoint overlap warnings. SI units. */
import * as T from 'three';
import {geometryData,inside,findInterferences} from 'collision';
const SKIN=.00015, EPS=1e-10, Y=new T.Vector3(0,1,0),bottomCache=new WeakMap();
const shifted=(box,d)=>box.clone().union(box.clone().translate(d));
export function bottom(mesh){const a=mesh.geometry.attributes.position,e=mesh.matrixWorld.elements,key=[a.version,e[1],e[5],e[9]].join(','),g=mesh.geometry;let cache=bottomCache.get(g);if(!cache){cache=new Map();bottomCache.set(g,cache);}if(cache.has(key))return cache.get(key)+e[13];let y=Infinity;for(let i=0;i<a.count;i++)y=Math.min(y,e[1]*a.getX(i)+e[5]*a.getY(i)+e[9]*a.getZ(i));if(cache.size>32)cache.clear();cache.set(key,y);return y+e[13];}
function rec(mesh){const data=geometryData(mesh.geometry),matrix=mesh.matrixWorld.clone();return {id:mesh.userData.partId,data,matrix,inverse:matrix.clone().invert(),box:data.root.box.clone().applyMatrix4(matrix)};}
function worldTri(t,m){return {a:t.a.clone().applyMatrix4(m),b:t.b.clone().applyMatrix4(m),c:t.c.clone().applyMatrix4(m)};}
function triangleBox(t){return new T.Box3().setFromPoints([t.a,t.b,t.c]);}
// A translating triangle against a stationary triangle, including coplanar edges.
export function sweepTriangles(a,b,delta,centers=new T.Vector3(),skin=SKIN){
 const ae=[a.b.clone().sub(a.a),a.c.clone().sub(a.b),a.a.clone().sub(a.c)],be=[b.b.clone().sub(b.a),b.c.clone().sub(b.b),b.a.clone().sub(b.c)];
 const na=ae[0].clone().cross(ae[1]),nb=be[0].clone().cross(be[1]);
 const axes=[na,nb,...ae.map(e=>e.clone().cross(na)),...be.map(e=>e.clone().cross(nb))];
 for(const e of ae)for(const f of be)axes.push(e.clone().cross(f));
 let entry=-Infinity,exit=Infinity,normal=null;
 for(const axis of axes){const len=axis.length();if(len<1e-12)continue;axis.multiplyScalar(1/len);
  const ap=[a.a.dot(axis),a.b.dot(axis),a.c.dot(axis)],bp=[b.a.dot(axis),b.b.dot(axis),b.c.dot(axis)];
  const amin=Math.min(...ap),amax=Math.max(...ap),bmin=Math.min(...bp),bmax=Math.max(...bp),v=delta.dot(axis);
  if(Math.abs(v)<EPS){if(amax+skin<bmin||bmax+skin<amin)return null;continue;}
  let enter=(bmin-amax-skin)/v,leave=(bmax-amin+skin)/v;if(enter>leave)[enter,leave]=[leave,enter];
  if(enter>entry){entry=enter;normal=axis.clone();let side=(amin+amax-bmin-bmax)/2+v*Math.max(0,enter);if(Math.abs(side)<1e-7)side=centers.dot(axis);if(Math.abs(side)<1e-8)side=-v;normal.multiplyScalar(Math.sign(side)||1);}
  exit=Math.min(exit,leave);if(entry>exit)return null;
 }
 if(!normal||entry>1||exit<0)return null;
 if(entry<=1e-7&&delta.dot(normal)>=-1e-9)return null; // slide along or leave an existing contact
 return {time:Math.max(0,entry),normal};
}
function pairSweep(a,b,delta,bestTime=1){
 if(!shifted(a.box,delta).expandByScalar(SKIN).intersectsBox(b.box))return null;
 const ac=a.box.getCenter(new T.Vector3()),bc=b.box.getCenter(new T.Vector3()),centers=ac.clone().sub(bc);
 // Existing imported containment can be pulled out; it must not trap the editor.
 if(delta.dot(centers)>=0&&inside(ac,b,SKIN))return null;
 const inverse=b.inverse,localDelta=delta.clone().applyMatrix3(new T.Matrix3().setFromMatrix4(inverse));
 let best=null;
 for(const t of a.data.triangles){
  const tri=worldTri(t,a.matrix),query=triangleBox({a:tri.a.clone().applyMatrix4(inverse),b:tri.b.clone().applyMatrix4(inverse),c:tri.c.clone().applyMatrix4(inverse)});
  query.union(query.clone().translate(localDelta)).expandByScalar(.001);
  const visit=node=>{if(!query.intersectsBox(node.box))return;
   if(node.ts){for(const other of node.ts){if(!query.intersectsBox(other.box))continue;
    const hit=sweepTriangles(tri,worldTri(other,b.matrix),delta,centers);if(hit&&hit.time<bestTime){bestTime=hit.time;best={...hit,a:a.id,b:b.id};if(bestTime===0)return;}
   }}else{visit(node.left);if(bestTime!==0)visit(node.right);}
  };visit(b.data.root);if(bestTime===0)break;
 }
 return best;
}
export function sweepGroup(moving,obstacles,delta,{floor=true}={}){
 if(delta.lengthSq()<1e-18)return null;
 const a=moving.map(rec),b=obstacles.map(rec);let best=null,bestTime=1+1e-9;
 if(floor&&delta.y<0){for(let i=0;i<a.length;i++){const time=Math.max(0,(bottom(moving[i])-SKIN)/(-delta.y));if(time>=-1e-7&&time<bestTime){bestTime=Math.max(0,time);best={time:bestTime,normal:Y.clone(),a:a[i].id,b:'floor'};}}}
 if(bestTime===0)return best;
 for(const r of a)for(const s of b){const hit=pairSweep(r,s,delta,Math.min(bestTime,1+1e-9));if(hit&&hit.time<bestTime){best=hit;bestTime=hit.time;}}
 return best;
}
export function resolveTranslation(moving,obstacles,requested,{floor=true,slide=false}={}){
 const offset=new T.Vector3(),remaining=requested.clone(),hits=[];
 for(let pass=0;pass<(slide?3:1);pass++){
  const shift=new T.Matrix4().makeTranslation(...offset.toArray()),preview=moving.map(m=>{const p=new T.Mesh(m.geometry);p.userData.partId=m.userData.partId;p.matrixWorld.copy(shift).multiply(m.matrixWorld);return p;});
  const hit=sweepGroup(preview,obstacles,remaining,{floor});if(!hit){offset.add(remaining);break;}
  hits.push(hit);const fraction=Math.max(0,hit.time-1e-6/Math.max(remaining.length(),1e-6));offset.addScaledVector(remaining,fraction);
  if(!slide)break;remaining.multiplyScalar(1-fraction);const into=remaining.dot(hit.normal);if(into<0)remaining.addScaledVector(hit.normal,-into);if(remaining.lengthSq()<1e-12)break;
 }
 return {offset,hits,blocked:hits.length>0};
}
export function interpolateRoot(start,end,t){const pa=new T.Vector3(),pb=new T.Vector3(),qa=new T.Quaternion(),qb=new T.Quaternion(),sa=new T.Vector3(),sb=new T.Vector3();start.decompose(pa,qa,sa);end.decompose(pb,qb,sb);return new T.Matrix4().compose(pa.lerp(pb,t),qa.slerp(qb,t),sa.lerp(sb,t));}
export function constrainAffine(moving,obstacles,startRoot,endRoot,{floor=true}={}){
 const pa=new T.Vector3(),pb=new T.Vector3(),qa=new T.Quaternion(),qb=new T.Quaternion(),sa=new T.Vector3(),sb=new T.Vector3();startRoot.decompose(pa,qa,sa);endRoot.decompose(pb,qb,sb);
 const angle=qa.angleTo(qb),scale=Math.max(...sa.toArray().map((v,i)=>Math.abs(sb.getComponent(i)/Math.max(v,1e-9)-1)));
 let radius=0;for(const m of moving){const b=rec(m).box;radius=Math.max(radius,b.getCenter(new T.Vector3()).distanceTo(pa)+b.getSize(new T.Vector3()).length()/2);}
 // Conservative envelope: rotation cannot move any vertex beyond this sphere.
 // Empty space needs no thickness-sized sampling (which truncated large typed angles).
 const envelope=new T.Box3().setFromPoints([pa,pb]).expandByScalar(radius*(1+scale)+SKIN);
 obstacles=obstacles.filter(m=>envelope.intersectsBox(rec(m).box));
 const verticalInvariant=sa.distanceTo(sb)<1e-9&&new T.Vector3(0,1,0).applyQuaternion(qb.clone().multiply(qa.clone().invert())).distanceTo(Y)<1e-9;
 const clearFloor=!floor||envelope.min.y>=0||(verticalInvariant&&moving.every(m=>bottom(m)+pb.y-pa.y>=-SKIN));
 if(!obstacles.length&&clearFloor)return {matrix:endRoot.clone(),fraction:1,blocked:false,reason:null};
 const distance=pa.distanceTo(pb)+angle*radius+scale*radius;
 const features=[...moving,...obstacles].map(m=>rec(m).box.getSize(new T.Vector3())).flatMap(v=>v.toArray()).filter(v=>v>1e-6);
 const step=Math.max(.0005,Math.min(.01,...features.map(x=>x*.2))),needed=Math.max(1,Math.ceil(distance/step),Math.ceil(angle/(Math.PI/360)),Math.ceil(scale/.005));
 const count=Math.min(8192,needed),inverse=startRoot.clone().invert();let previous=0,blocked=false,reason=null;
 const at=t=>{const delta=interpolateRoot(startRoot,endRoot,t).multiply(inverse);return moving.map(m=>{const p=new T.Mesh(m.geometry);p.userData.partId=m.userData.partId;p.matrixWorld.copy(delta).multiply(m.matrixWorld);return p;});};
 const unsafe=t=>{const rows=at(t);if(floor&&rows.some(m=>bottom(m)<-SKIN))return true;const ids=new Set(rows.map(m=>m.userData.partId));return findInterferences([...rows,...obstacles],{focusIds:ids,tolerance:.0001}).some(r=>ids.has(r.a)!==ids.has(r.b));};
 for(let i=1;i<=count;i++){const t=i/needed;if(unsafe(t)){let lo=previous,hi=t;for(let j=0;j<12;j++){const mid=(lo+hi)/2;if(unsafe(mid))hi=mid;else lo=mid;}previous=lo;blocked=true;reason='contact';break;}previous=t;}
 if(count<needed&&!blocked){blocked=true;reason='step-limit';}
 return {matrix:interpolateRoot(startRoot,endRoot,previous),fraction:previous,blocked,reason};
}
