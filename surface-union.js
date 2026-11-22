/* Non-destructive BSP union of closed triangle solids; the project keeps both originals. */
import * as T from 'three';
const EPS=1e-6;
class Vertex{
 constructor(p,c,uv){this.p=p;this.c=c;this.uv=uv;}
 clone(){return new Vertex(this.p.clone(),this.c.clone(),this.uv.clone());}
 mix(v,t){return new Vertex(this.p.clone().lerp(v.p,t),this.c.clone().lerp(v.c,t),this.uv.clone().lerp(v.uv,t));}
}
class Polygon{
 constructor(v){this.v=v;this.n=v[1].p.clone().sub(v[0].p).cross(v[2].p.clone().sub(v[0].p)).normalize();this.w=this.n.dot(v[0].p);}
 clone(){return new Polygon(this.v.map(v=>v.clone()));}
 flip(){this.v.reverse();this.n.negate();this.w=-this.w;}
}
class Node{
 constructor(polygons=[],budget={count:0}){this.polygons=[];this.front=null;this.back=null;this.n=null;this.budget=budget;if(polygons.length)this.build(polygons);}
 split(p,cf,cb,f,b){let type=0;const types=p.v.map(v=>{const d=this.n.dot(v.p)-this.w,t=d < -EPS?2:d>EPS?1:0;type|=t;return t;});
  if(type===0)(this.n.dot(p.n)>0?cf:cb).push(p);else if(type===1)f.push(p);else if(type===2)b.push(p);else{const fv=[],bv=[];for(let i=0;i<p.v.length;i++){const j=(i+1)%p.v.length,ti=types[i],tj=types[j],vi=p.v[i],vj=p.v[j];if(ti!==2)fv.push(vi);if(ti!==1)bv.push(vi.clone());if((ti|tj)===3){const t=(this.w-this.n.dot(vi.p))/this.n.dot(vj.p.clone().sub(vi.p)),v=vi.mix(vj,t);fv.push(v);bv.push(v.clone());}}if(fv.length>=3)f.push(new Polygon(fv));if(bv.length>=3)b.push(new Polygon(bv));}
 }
 build(polygons,depth=0){if(depth>1200||this.budget.count+polygons.length>1500000)throw Error('형상 결합이 너무 복잡합니다. 간단한 패널 단위로 결합하세요.');this.budget.count+=polygons.length;if(!polygons.length)return;if(!this.n){this.n=polygons[0].n.clone();this.w=polygons[0].w;}const f=[],b=[];for(const p of polygons)this.split(p,this.polygons,this.polygons,f,b);if(f.length){this.front??=new Node([],this.budget);this.front.build(f,depth+1);}if(b.length){this.back??=new Node([],this.budget);this.back.build(b,depth+1);}}
 invert(){for(const p of this.polygons)p.flip();this.n?.negate();this.w=-this.w;this.front?.invert();this.back?.invert();[this.front,this.back]=[this.back,this.front];}
 clip(polygons){if(!this.n)return polygons.slice();let f=[],b=[];for(const p of polygons)this.split(p,f,b,f,b);if(this.front)f=this.front.clip(f);b=this.back?this.back.clip(b):[];return f.concat(b);}
 clipTo(other){this.polygons=other.clip(this.polygons);this.front?.clipTo(other);this.back?.clipTo(other);}
 all(){return this.polygons.concat(this.front?.all()||[],this.back?.all()||[]);}
}
function polygons(mesh){const g=mesh.geometry,a=g.attributes.position,c=g.attributes.color,uv=g.attributes.uv,ix=g.index?.array||Array.from({length:a.count},(_,i)=>i),polys=[],edges=new Map(),point=i=>new T.Vector3().fromBufferAttribute(a,i).applyMatrix4(mesh.matrixWorld),key=p=>p.toArray().map(v=>Math.round(v/EPS)).join(',');if(ix.length/3>16000)throw Error('형상 결합은 한 부품당 16,000 삼각형까지 지원합니다.');
 for(let i=0;i<ix.length;i+=3){const ps=[point(ix[i]),point(ix[i+1]),point(ix[i+2])];if(ps[1].clone().sub(ps[0]).cross(ps[2].clone().sub(ps[0])).lengthSq()<1e-20)continue;for(let k=0;k<3;k++){const e=[key(ps[k]),key(ps[(k+1)%3])].sort().join('|');edges.set(e,(edges.get(e)||0)+1);}polys.push(new Polygon(ps.map((p,k)=>{const j=ix[i+k],color=(mesh.material?.color||new T.Color('#ffffff')).clone();if(c)color.multiply(new T.Color(c.getX(j),c.getY(j),c.getZ(j)));return new Vertex(p,color,uv?new T.Vector2(uv.getX(j),uv.getY(j)):new T.Vector2());})));}
 if(!polys.length||[...edges.values()].some(n=>n!==2))throw Error('닫힌 입체끼리 형상 결합할 수 있습니다. 열린 면·겹친 삼각형을 먼저 정리하세요.');let volume=0;for(const p of polys)for(let i=1;i<p.v.length-1;i++)volume+=p.v[0].p.dot(p.v[i].p.clone().cross(p.v[i+1].p))/6;if(volume<0)for(const p of polys)p.flip();return mergeCoplanar(polys);
}
function mergeCoplanar(polys){const groups=new Map();for(const p of polys){const key=[...p.n.toArray(),p.w].map(v=>Math.round(v*1e5)).join(',')+':'+p.v[0].c.getHexString();if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p);}const result=[];for(const group of groups.values()){if(group.length<3){result.push(...group);continue;}const normal=group[0].n,axis=Math.abs(normal.x)>Math.abs(normal.y)?(Math.abs(normal.x)>Math.abs(normal.z)?0:2):(Math.abs(normal.y)>Math.abs(normal.z)?1:2),axes=[0,1,2].filter(a=>a!==axis),unique=new Map();for(const p of group)for(const v of p.v)unique.set(v.p.toArray().map(x=>Math.round(x/EPS)).join(','),v);const rows=[...unique.values()].map(v=>({v,x:v.p.getComponent(axes[0]),y:v.p.getComponent(axes[1])})).sort((a,b)=>a.x-b.x||a.y-b.y),cross=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x),hull=[];for(const p of rows){while(hull.length>=2&&cross(hull.at(-2),hull.at(-1),p)<=1e-12)hull.pop();hull.push(p);}const lower=hull.length;for(let i=rows.length-2;i>=0;i--){const p=rows[i];while(hull.length>lower&&cross(hull.at(-2),hull.at(-1),p)<=1e-12)hull.pop();hull.push(p);}hull.pop();if(hull.length<3){result.push(...group);continue;}const area=p=>{let sum=0;for(let i=1;i<p.v.length-1;i++)sum+=p.v[i].p.clone().sub(p.v[0].p).cross(p.v[i+1].p.clone().sub(p.v[0].p)).length()/2;return sum;},candidate=new Polygon(hull.map(p=>p.v.clone())),total=group.reduce((n,p)=>n+area(p),0);if(Math.abs(area(candidate)-total)>Math.max(1e-8,total*1e-5)){result.push(...group);continue;}if(candidate.n.dot(normal)<0)candidate.flip();result.push(candidate);}return result;}
export function unionGeometry(left,right,toLocal=new T.Matrix4()){
 left.updateMatrixWorld(true);right.updateMatrixWorld(true);const a=new Node(polygons(left)),b=new Node(polygons(right));a.clipTo(b);b.clipTo(a);b.invert();b.clipTo(a);b.invert();a.build(b.all());const pos=[],color=[],uv=[],index=[],lookup=new Map();
 for(const p of a.all())for(let i=1;i<p.v.length-1;i++){const tri=[p.v[0],p.v[i],p.v[i+1]];if(tri[1].p.clone().sub(tri[0].p).cross(tri[2].p.clone().sub(tri[0].p)).lengthSq()<1e-20)continue;for(const v of tri){const point=v.p.clone().applyMatrix4(toLocal),k=[...point.toArray(),v.c.r,v.c.g,v.c.b].map(x=>Math.round(x*1e6)).join(',');let j=lookup.get(k);if(j===undefined){j=pos.length/3;lookup.set(k,j);pos.push(...point.toArray());color.push(v.c.r,v.c.g,v.c.b);uv.push(v.uv.x,v.uv.y);}index.push(j);}}
 if(!pos.length)throw Error('형상 결합 결과가 비어 있습니다.');const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setAttribute('color',new T.Float32BufferAttribute(color,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(index);g.computeVertexNormals();g.computeBoundingBox();g.computeBoundingSphere();g.userData.surfaceUnion=true;return g;
}
export class SurfaceUnions{
 constructor(){this.proxies=new Map();this.precomputed=new Map();this.signature='';}
 clear(){for(const m of this.proxies.values()){m.parent?.remove(m);m.geometry.dispose();m.material.dispose();}this.proxies.clear();this.signature='';}
 sync(project,meshes,world,picking=false){
  const edges=project.parts.filter(p=>p.connection?.surfaceUnion&&p.parentId),signature=edges.map(p=>{const m=meshes.get(p.id),q=meshes.get(p.parentId);return p.id+':'+p.parentId+':'+m?.geometry.uuid+':'+m?.geometry.attributes.position.version+':'+q?.geometry.uuid+':'+q?.geometry.attributes.position.version+':'+(q&&m?q.matrixWorld.clone().invert().multiply(m.matrixWorld).elements.map(v=>Math.round(v*1e8)).join(','):'')+':'+m?.material?.uuid+':'+q?.material?.uuid;}).join('|');
  if(signature!==this.signature){this.clear();const byId=new Map(project.parts.map(p=>[p.id,p])),done=new Set();const build=id=>{if(done.has(id))return this.proxies.get(id)||meshes.get(id);done.add(id);const source=meshes.get(id);let base=source;for(const p of edges.filter(p=>p.parentId===id)){const child=build(p.id);const prepared=this.precomputed.get(id+'|'+p.id),geometry=prepared||unionGeometry(base,child,source.matrixWorld.clone().invert());this.precomputed.delete(id+'|'+p.id);if(base!==source){base.parent?.remove(base);base.geometry.dispose();base.material.dispose();}const material=source.material.clone();material.color.set('#ffffff');material.vertexColors=true;const proxy=new T.Mesh(geometry,material);proxy.userData.partId=id;proxy.matrixAutoUpdate=false;proxy.matrix.copy(source.matrixWorld);proxy.matrixWorld.copy(proxy.matrix);proxy.castShadow=proxy.receiveShadow=true;base=proxy;}
    if(base!==source){this.proxies.set(id,base);world.add(base);}return base;};
   try{for(const p of project.parts)if(!p.parentId||!byId.get(p.id)?.connection?.surfaceUnion)build(p.id);this.signature=signature;for(const g of this.precomputed.values())g.dispose();this.precomputed.clear();}catch(error){this.clear();throw error;}
  }
  const linked=new Map(project.parts.map(p=>[p.id,p]));for(const p of project.parts){const m=meshes.get(p.id);if(m){m.visible=p.visible!==false;delete m.userData.surfaceUnionRoot;let root=p;while(root.connection?.surfaceUnion&&linked.has(root.parentId))root=linked.get(root.parentId);if(root.id!==p.id||edges.some(q=>q.parentId===p.id))m.userData.surfaceUnionRoot=root.id;}}
  for(const [id,proxy]of this.proxies){const current=meshes.get(id);if(current){proxy.matrix.copy(current.matrixWorld);proxy.matrixWorld.copy(proxy.matrix);}proxy.visible=!picking&&byVisible(project,id);if(!picking){const source=meshes.get(id);if(source)source.visible=false;for(const p of edges.filter(p=>p.parentId===id)){const m=meshes.get(p.id);if(m)m.visible=false;const q=this.proxies.get(p.id);if(q)q.visible=false;}}}
 }
}
const byVisible=(project,id)=>project.parts.find(p=>p.id===id)?.visible!==false;
