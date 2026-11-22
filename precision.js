/* Local modelling and camera tools. Geometry is in metres; control points are local. */
import * as T from 'three';
import {geometryData} from 'collision';
export const MAX_PARTS=2000;
export function wheelZoom(camera,controls,event,height=800){
 const delta=Number(event.deltaY)*(event.deltaMode===1?16:event.deltaMode===2?height:1);if(!Number.isFinite(delta)||delta===0)return false;
 const offset=camera.position.clone().sub(controls.target),distance=Math.max(.002,offset.length()),speed=Number(controls.zoomSpeed)||2.8;
 const next=T.MathUtils.clamp(distance*Math.exp(T.MathUtils.clamp(delta,-600,600)*.0012*speed),.002,500);
 if(offset.lengthSq()<1e-16)offset.copy(camera.getWorldDirection(new T.Vector3())).negate();offset.normalize();camera.position.copy(controls.target).addScaledVector(offset,next);camera.lookAt(controls.target);camera.updateMatrixWorld();controls.update();return true;
}
const bern=t=>[(1-t)**3,3*t*(1-t)**2,3*t*t*(1-t),t**3];
export function defaultSurface(style='hood'){
 const points=[];for(let i=0;i<4;i++)for(let j=0;j<4;j++){const x=i/3-.5,z=j/3-.5;let y=(1-4*x*x)*(1-4*z*z)*.6;
 if(style==='roof')y=.12+(1-4*z*z)*.7-(x*x)*.2;if(style==='flat')y=0;if(style==='fender')y=Math.sin((j/3)*Math.PI)*.9;
 points.push([x,y,z]);}return {version:1,points,thickness:.01,segments:24};
}
export function validateSurface(s){if(!s||s.version!==1||!Array.isArray(s.points)||s.points.length!==16||s.points.some(p=>!Array.isArray(p)||p.length!==3||p.some(v=>!Number.isFinite(v)||Math.abs(v)>10))||!Number.isFinite(s.thickness)||s.thickness<.00001||s.thickness>1||!Number.isInteger(s.segments)||s.segments<4||s.segments>64)throw Error('곡면 제어점·두께·분할 수가 올바르지 않습니다.');return s;}
export function surfacePoint(s,u,v){const a=bern(u),b=bern(v),p=new T.Vector3();for(let i=0;i<4;i++)for(let j=0;j<4;j++)p.addScaledVector(new T.Vector3(...s.points[i*4+j]),a[i]*b[j]);return p;}
export function buildSurface(s){validateSurface(s);const n=s.segments,pos=[],uv=[],ix=[],side=(n+1)**2;
 for(let layer=0;layer<2;layer++)for(let i=0;i<=n;i++)for(let j=0;j<=n;j++){const p=surfacePoint(s,i/n,j/n);p.y-=layer*s.thickness;pos.push(...p.toArray());uv.push(i/n,j/n);}
 const face=(a,b,c,d)=>ix.push(a,b,c,a,c,d);
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){const a=i*(n+1)+j,b=a+n+1;face(a,a+1,b+1,b);face(a+side,b+side,b+side+1,a+side+1);}
 const boundary=[];for(let j=0;j<=n;j++)boundary.push(j);for(let i=1;i<=n;i++)boundary.push(i*(n+1)+n);for(let j=n-1;j>=0;j--)boundary.push(n*(n+1)+j);for(let i=n-1;i>0;i--)boundary.push(i*(n+1));
 for(let i=0;i<boundary.length;i++){const a=boundary[i],b=boundary[(i+1)%boundary.length];face(a,a+side,b+side,b);}
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(ix);g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();return g;
}
const edgeCache=new WeakMap();
export function nearestEdge(mesh,point){const data=geometryData(mesh.geometry);let cached=edgeCache.get(mesh.geometry);if(!cached||cached.version!==mesh.geometry.attributes.position.version){const edges=new Map(),key=p=>p.toArray().map(v=>Math.round(v*1e6)).join(',');for(const tri of data.triangles)for(const [a,b]of [[tri.a,tri.b],[tri.b,tri.c],[tri.c,tri.a]]){const k=[key(a),key(b)].sort().join('|');if(!edges.has(k))edges.set(k,{a,b,normals:[]});edges.get(k).normals.push(tri.normal);}cached={version:mesh.geometry.attributes.position.version,edges:[...edges.values()].filter(e=>e.normals.length===1||e.normals.some(n=>n.dot(e.normals[0])<.966))};edgeCache.set(mesh.geometry,cached);}const q=new T.Vector3();let best=null,d=Infinity;for(const edge of cached.edges){const a=edge.a.clone().applyMatrix4(mesh.matrixWorld),b=edge.b.clone().applyMatrix4(mesh.matrixWorld);new T.Line3(a,b).closestPointToPoint(point,true,q);const distance=q.distanceToSquared(point);if(distance<d){d=distance;best={point:q.clone(),direction:b.sub(a).normalize()};}}return best;}

export function precisePlacement(child,parent,mode='anchor',sourceHint=null,targetHint=null,gap=0){
 const cm=child.mesh,pm=parent.mesh;cm.updateMatrixWorld();pm.updateMatrixWorld();let a,b,normal=new T.Vector3(1,0,0),q=cm.getWorldQuaternion(new T.Quaternion());
 if(mode==='anchor'){
  let score=Infinity;for(const ca of child.part.anchors)for(const pa of parent.part.anchors){const av=cm.localToWorld(new T.Vector3(...ca.point)),bv=pm.localToWorld(new T.Vector3(...pa.point));const d=av.distanceToSquared(sourceHint||bv)+bv.distanceToSquared(targetHint||av);if(d<score){score=d;a=av;b=bv;}}
  if(!a)throw Error('두 부품에 연결점을 먼저 지정하세요.');normal.copy(a).sub(b).normalize();
 }else if(mode==='edge'){
  const ae=nearestEdge(cm,sourceHint||new T.Box3().setFromObject(pm).getCenter(new T.Vector3())),be=nearestEdge(pm,targetHint||ae?.point||new T.Vector3());if(!ae||!be)throw Error('스냅 모서리를 찾지 못했습니다.');a=ae.point;b=be.point;const dir=be.direction.clone();if(ae.direction.dot(dir)<0)dir.negate();q.premultiply(new T.Quaternion().setFromUnitVectors(ae.direction,dir));normal.copy(a).sub(b).normalize();
 }else{
  const nearest=(m,point)=>{const g=geometryData(m.geometry),tri=new T.Triangle(),v=new T.Vector3();let best=null,d=Infinity;for(const t of g.triangles){tri.set(t.a.clone().applyMatrix4(m.matrixWorld),t.b.clone().applyMatrix4(m.matrixWorld),t.c.clone().applyMatrix4(m.matrixWorld));tri.closestPointToPoint(point,v);const ds=v.distanceToSquared(point);if(ds<d){d=ds;best={point:v.clone(),normal:tri.getNormal(new T.Vector3())};}}return best;};
  const target=nearest(pm,targetHint||new T.Box3().setFromObject(cm).getCenter(new T.Vector3())),source=nearest(cm,sourceHint||target.point);a=source.point;b=target.point;normal=target.normal;if(normal.dot(a.clone().sub(b))<0)normal.negate();q.premultiply(new T.Quaternion().setFromUnitVectors(source.normal,normal.clone().negate()));
 }
 const position=new T.Vector3(...child.part.position),scale=new T.Vector3(...child.part.size),matrix=new T.Matrix4().compose(position,q,scale),local=a.clone().applyMatrix4(cm.matrixWorld.clone().invert()),after=local.applyMatrix4(matrix);matrix.setPosition(position.add(b.clone().addScaledVector(normal,gap).sub(after)));
 return {matrix,source:a,target:b,normal,delta:b.clone().sub(a)};
}
export function hingeTransform(parentMatrix,hinge,angle){const pivot=new T.Vector3(...hinge.pivot).applyMatrix4(parentMatrix),axis=new T.Vector3(...hinge.axis).transformDirection(parentMatrix);return new T.Matrix4().makeTranslation(...pivot.toArray()).multiply(new T.Matrix4().makeRotationAxis(axis,angle*Math.PI/180)).multiply(new T.Matrix4().makeTranslation(...pivot.toArray().map(v=>-v))).multiply(parentMatrix).multiply(new T.Matrix4().fromArray(hinge.closed));}
export function validateHinge(h,parentId){const vec=(p,n)=>Array.isArray(p)&&p.length===n&&p.every(Number.isFinite);if(!h||h.version!==1||h.parentId!==parentId||!parentId||!vec(h.pivot,3)||h.pivot.some(v=>Math.abs(v)>100)||!vec(h.axis,3)||Math.hypot(...h.axis)<.5||h.axis.some(v=>Math.abs(v)>1.001)||!vec(h.closed,16)||h.closed.some(v=>Math.abs(v)>10000)||Math.abs(new T.Matrix4().fromArray(h.closed).determinant())<1e-12||Math.abs(h.closed[3])+Math.abs(h.closed[7])+Math.abs(h.closed[11])+Math.abs(h.closed[15]-1)>1e-8||![h.angle,h.min,h.max].every(Number.isFinite)||h.min < -180||h.max>180||h.min>h.max||h.angle<h.min||h.angle>h.max)throw Error('힌지 회전축·각도 정보가 올바르지 않습니다.');return h;}
const noiseMaps=new Map();
export function finishMaps(kind='paint'){
 if(noiseMaps.has(kind))return noiseMaps.get(kind);const n=64,data=new Uint8Array(n*n*4),normal=new Uint8Array(n*n*4);let seed=8161;
 for(let y=0;y<n;y++)for(let x=0;x<n;x++){seed=(seed*1664525+1013904223)>>>0;const random=(seed>>>24)/255,grain=kind==='brushed'?Math.sin(y*2.4)*.13:kind==='carbon'?((Math.floor(x/4)+Math.floor(y/4))%2)*.22:kind==='fabric'?Math.sin(x*1.57)*Math.sin(y*1.57)*.2:random*.08,k=(x+y*n)*4,v=Math.round(T.MathUtils.clamp((kind==='paint'?.88:kind==='fabric'?.8:kind==='brushed'?.78:.65)+grain+random*.06,0,1)*255);data.set([v,v,v,255],k);normal.set([128+Math.round((random-.5)*4),128+Math.round(Math.sin(y)*2),255,255],k);}
 const make=d=>{const t=new T.DataTexture(d,n,n,T.RGBAFormat);t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(5,5);t.needsUpdate=true;return t;};const maps={roughnessMap:make(data),normalMap:make(normal)};noiseMaps.set(kind,maps);return maps;
}
