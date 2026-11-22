
import * as T from 'three';
const cache=new WeakMap(),recordCache=new WeakMap(),pairCache=new Map(),V=()=>new T.Vector3();
export function geometryData(g){
 const attr=g.attributes.position,old=cache.get(g);if(old?.version===attr.version)return old;
 const index=g.index?.array,triangles=[],n=index?index.length:attr.count;
 let hash=2166136261;for(let i=0;i<attr.array.length;i++){hash^=Math.round(attr.array[i]*1e6);hash=Math.imul(hash,16777619);}
 for(let i=0;i<n;i+=3){const a=V().fromBufferAttribute(attr,index?index[i]:i),b=V().fromBufferAttribute(attr,index?index[i+1]:i+1),c=V().fromBufferAttribute(attr,index?index[i+2]:i+2);
  const normal=b.clone().sub(a).cross(c.clone().sub(a));if(normal.lengthSq()<1e-20)continue;
  triangles.push({a,b,c,normal:normal.normalize(),box:new T.Box3().setFromPoints([a,b,c]),center:a.clone().add(b).add(c).multiplyScalar(1/3)});
 }
 function tree(ts){const box=new T.Box3();ts.forEach(t=>box.union(t.box));if(ts.length<=12)return {box,ts};
  const size=box.getSize(V()),axis=size.x>size.y?(size.x>size.z?'x':'z'):(size.y>size.z?'y':'z');
  ts.sort((a,b)=>a.center[axis]-b.center[axis]);const m=ts.length>>1;return {box,left:tree(ts.slice(0,m)),right:tree(ts.slice(m))};
 }
 const data={version:attr.version,triangles,root:tree([...triangles]),hash:(hash>>>0).toString(16)};cache.set(g,data);return data;
}
function record(mesh){const attr=mesh.geometry.attributes.position,previous=recordCache.get(mesh),elements=mesh.matrixWorld.elements;if(previous&&previous.geometry===mesh.geometry&&previous.version===attr.version&&previous.elements.every((v,i)=>v===elements[i])){previous.record.group=mesh.userData.rigidId;previous.record.fusion=mesh.userData.surfaceUnionRoot;return previous.record;}const data=geometryData(mesh.geometry),matrix=mesh.matrixWorld.clone(),r={id:mesh.userData.partId,group:mesh.userData.rigidId,fusion:mesh.userData.surfaceUnionRoot,data,matrix,inverse:matrix.clone().invert(),normal:new T.Matrix3().getNormalMatrix(matrix),box:data.root.box.clone().applyMatrix4(matrix)};recordCache.set(mesh,{geometry:mesh.geometry,version:attr.version,elements:[...elements],record:r});return r;}
const dirs=[new T.Vector3(.793,.371,.486).normalize(),new T.Vector3(-.283,.847,.45).normalize()];
export function inside(point,r,tolerance){
 if(!r.box.containsPoint(point))return false;
 const local=point.clone().applyMatrix4(r.inverse);
 for(const dir of dirs){
  const ray=new T.Ray(local,dir),hits=[],hit=V();
  const visit=node=>{if(!ray.intersectsBox(node.box))return;if(node.ts){for(const t of node.ts){if(ray.intersectTriangle(t.a,t.b,t.c,false,hit)){const d=hit.distanceTo(local);if(d<1e-9)continue;hits.push({d,sign:Math.sign(t.normal.dot(dir)),world:hit.clone().applyMatrix4(r.matrix).distanceTo(point)});}}}else{visit(node.left);visit(node.right);}};
  visit(r.data.root);hits.sort((a,b)=>a.d-b.d);
  let winding=0,last=-Infinity;
  for(const h of hits){if(h.world<tolerance)return false;if(h.d-last<1e-7)continue;winding++;last=h.d;}
  if(winding%2===0)return false;
 }
 return true;
}
function penetration(a,b,tolerance=.003){
 const overlap=a.box.clone().intersect(b.box);if(overlap.isEmpty())return null;
 const span=overlap.getSize(V());if(Math.min(span.x,span.y,span.z)<=tolerance)return null;
 const yes=p=>inside(p,a,tolerance)&&inside(p,b,tolerance);
 // Interior overlap catches containment and crossing thin solids.
 for(const u of [.15,.5,.85])for(const v of [.15,.5,.85])for(const w of [.15,.5,.85]){
  const p=new T.Vector3(overlap.min.x+span.x*u,overlap.min.y+span.y*v,overlap.min.z+span.z*w);if(yes(p))return p.toArray();
 }
 // Actual triangle centroids probe thin sills/pillars without treating a hollow shell as a box.
 for(const [r,other] of [[a,b],[b,a]]){
  const ts=r.data.triangles,stride=Math.max(1,Math.floor(ts.length/450));
  for(let i=0;i<ts.length;i+=stride){const t=ts[i],p=t.center.clone().applyMatrix4(r.matrix);
   if(!other.box.clone().expandByScalar(tolerance*2).containsPoint(p))continue;
   const normal=t.normal.clone().applyMatrix3(r.normal).normalize();
   for(const sign of [-1,1]){const q=p.clone().addScaledVector(normal,tolerance*1.6*sign);if(yes(q))return q.toArray();}
  }
 }
 return null;
}
const pairKey=(a,b)=>[a,b].sort().join('|');
function stamp(a,b){const rows=a.id<b.id?[a,b]:[b,a],relative=rows[0].inverse.clone().multiply(rows[1].matrix);
 return rows.map(r=>r.id+':'+r.data.hash).join('|')+':'+relative.elements.map(v=>Math.round(v*1e5)).join(',');
}
export function findInterferences(meshes,{focusIds=null,allowances={},tolerance=.003,contactGroups=false}={}){
 const records=meshes.map(record).sort((a,b)=>a.box.min.x-b.box.min.x),out=[];
 for(let i=0;i<records.length;i++)for(let j=i+1;j<records.length;j++){
  const a=records[i],b=records[j];if(b.box.min.x>a.box.max.x)break;if(focusIds&&!focusIds.has(a.id)&&!focusIds.has(b.id))continue;
  if(!a.box.intersectsBox(b.box))continue;const key=pairKey(a.id,b.id),signature=stamp(a,b);
  if(contactGroups&&a.fusion&&a.fusion===b.fusion){out.push({a:a.id,b:b.id,key,stamp:signature,acknowledged:true,intentionalUnion:true});continue;}if(allowances[key]===signature){out.push({a:a.id,b:b.id,key,stamp:signature,acknowledged:true});continue;}
  const overlap=new T.Box3().copy(a.box).intersect(b.box).getSize(V()),depth=Math.min(overlap.x,overlap.y,overlap.z),skin=contactGroups&&a.group&&a.group===b.group&&['x','y','z'].some(axis=>overlap[axis]<=tolerance&&Math.min(Math.abs(a.box.min[axis]-b.box.max[axis]),Math.abs(a.box.max[axis]-b.box.min[axis]))<=tolerance);if(skin){out.push({a:a.id,b:b.id,key,stamp:signature,depth,acknowledged:true,intentionalContact:true});continue;}const scaleKey=[a,b].map(r=>[0,4,8].map(i=>Math.hypot(r.matrix.elements[i],r.matrix.elements[i+1],r.matrix.elements[i+2]).toFixed(7)).join(',')).join('|'),cacheKey=a.id+':'+signature+':'+scaleKey+':'+tolerance;let point;if(pairCache.has(cacheKey)){const cached=pairCache.get(cacheKey);point=cached?new T.Vector3(...cached).applyMatrix4(a.matrix).toArray():null;}else{point=penetration(a,b,tolerance);if(pairCache.size>20000)pairCache.clear();pairCache.set(cacheKey,point?new T.Vector3(...point).applyMatrix4(a.inverse).toArray():null);}if(point)out.push({a:a.id,b:b.id,key,stamp:signature,point,depth,acknowledged:false});
 }
 return out;
}
