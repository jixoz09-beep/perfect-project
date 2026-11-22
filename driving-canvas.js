/* Perspective triangle fallback for browsers without WebGL. Physics is unchanged.
 * Texture faces participate in depth sorting, so dashboard displays cannot show
 * through a roof or another opaque surface. */
import * as T from 'three';
const fog=new T.Color('#b1cacc');
export class DriveCanvasRenderer{
 constructor(){this.domElement=document.createElement('canvas');this.ctx=this.domElement.getContext('2d');this.shadowMap={};this.isSoftware=true;this.ratio=1;this.last=0;this.patterns=new WeakMap();this.textureCanvases=new WeakMap();}
 setPixelRatio(n){this.ratio=Math.min(1,n);}
 setSize(w,h){this.w=w;this.h=h;this.domElement.width=w*this.ratio;this.domElement.height=h*this.ratio;this.domElement.style.width=w+'px';this.domElement.style.height=h+'px';}
 dispose(){this.domElement.width=1;this.domElement.height=1;}
 proxyGeometry(g){
  if(g.userData.driveCanvasProxy)return g.userData.driveCanvasProxy;
  if(g.userData.driveKeepDetail||g.userData.driveCityBatch)return {position:g.attributes.position,index:g.index?.array};
  if(g.userData.driveCanvasProxy)return g.userData.driveCanvasProxy;
  const pos=g.attributes.position,ix=g.index?.array;
  if((ix?ix.length:pos.count)<2400)return{position:pos,index:ix};
  g.computeBoundingBox();const b=g.boundingBox,size=b.getSize(new T.Vector3()),clusters=new Map(),remap=[],nodes=[];
  for(let i=0;i<pos.count;i++){const v=new T.Vector3().fromBufferAttribute(pos,i),key=[v.x,v.y,v.z].map((n,k)=>Math.round((n-b.min.getComponent(k))/Math.max(.00001,size.getComponent(k))*2)).join(',');let n=clusters.get(key);if(!n){n={index:nodes.length,sum:new T.Vector3(),count:0};nodes.push(n);clusters.set(key,n);}n.sum.add(v);n.count++;remap[i]=n.index;}
  const positions=nodes.flatMap(n=>n.sum.divideScalar(n.count).toArray()),indices=[],seen=new Set();const count=ix?ix.length:pos.count;
  for(let i=0;i<count;i+=3){const a=remap[ix?ix[i]:i],b=remap[ix?ix[i+1]:i+1],c=remap[ix?ix[i+2]:i+2];if(a===b||b===c||c===a)continue;const key=[a,b,c].sort((a,b)=>a-b).join(',');if(seen.has(key))continue;seen.add(key);indices.push(a,b,c);}
  return g.userData.driveCanvasProxy={position:new T.Float32BufferAttribute(positions,3),index:indices};
 }
 render(scene,camera){
  const now=performance.now();if(!this.w||(!this.preview&&now-this.last<70))return;this.last=now;
  const ctx=this.ctx,w=this.w,h=this.h;ctx.setTransform(this.ratio,0,0,this.ratio,0,0);const sky=ctx.createLinearGradient(0,0,0,h);sky.addColorStop(0,'#b2d0d6');sky.addColorStop(.55,'#cbdcda');sky.addColorStop(1,'#74928a');ctx.fillStyle=sky;ctx.fillRect(0,0,w,h);
  scene.updateMatrixWorld();camera.updateMatrixWorld();const view=camera.matrixWorldInverse,focal=h/(2*Math.tan(camera.fov*Math.PI/360)),triangles=[],draws=[];const near=Math.max(.035,camera.near),far=this.preview?50:230;
  const distanceTo=m=>new T.Vector3().setFromMatrixPosition(m).distanceTo(camera.position);
  scene.traverseVisible(o=>{if(o.userData.driveInterior&&(this.preview||this.driveExternalView))return;if(!o.isMesh||!o.geometry?.attributes.position)return;if(o.isInstancedMesh){const instance=new T.Matrix4();for(let i=0;i<o.count;i++){o.getMatrixAt(i,instance);const matrix=new T.Matrix4().multiplyMatrices(o.matrixWorld,instance),d=distanceTo(matrix),scale=new T.Vector3().setFromMatrixScale(matrix);if(d<far+scale.length())draws.push({o,matrix,d});}}else{const d=distanceTo(o.matrixWorld);if(d<far||o.geometry.type==='PlaneGeometry')draws.push({o,matrix:o.matrixWorld,d});}});
  draws.sort((a,b)=>(b.o.userData.driveVehicle?3:0)-(a.o.userData.driveVehicle?3:0)||a.d-b.d);let budget=0;
  for(const {o,matrix,d}of draws){
   if(budget>40000)break;const material=Array.isArray(o.material)?o.material[0]:o.material;if(material?.visible===false||material?.opacity===0)continue;
   const proxy=this.proxyGeometry(o.geometry),pos=proxy.position,index=proxy.index,uv=o.geometry.attributes.uv;
   const textureImage=this.textureImage(material?.map),image=textureImage&&uv&&(o.geometry.type==='PlaneGeometry'||o.geometry.userData.driveCityBatch&&d<150)?textureImage:null;
   const count=index?index.length:pos.count,mv=new T.Matrix4().multiplyMatrices(view,matrix),points=[];
   for(let i=0;i<pos.count;i++)points.push(new T.Vector3().fromBufferAttribute(pos,i).applyMatrix4(mv));
   for(let i=0;i<count;i+=3){
    const ids=[index?index[i]:i,index?index[i+1]:i+1,index?index[i+2]:i+2],vs=ids.map(n=>points[n]);
    if(vs.every(p=>p.z>=-near)||vs.every(p=>p.z< -far))continue;
    let clipped=[];for(let k=0;k<3;k++){const a=vs[k],b=vs[(k+1)%3],ia=ids[k],ib=ids[(k+1)%3],inside=a.z<=-near,bi=b.z<=-near,ua=image?[uv.getX(ia),1-uv.getY(ia)]:null,ub=image?[uv.getX(ib),1-uv.getY(ib)]:null;if(inside)clipped.push({p:a,uv:ua});if(inside!==bi){const t=(-near-a.z)/(b.z-a.z);clipped.push({p:a.clone().lerp(b,t),uv:image?[ua[0]+(ub[0]-ua[0])*t,ua[1]+(ub[1]-ua[1])*t]:null});}}
    if(clipped.length<3)continue;const screen=clipped.map(({p})=>[w/2+p.x*focal/-p.z,h/2-p.y*focal/-p.z]);if(screen.every(p=>p[0]<0)||screen.every(p=>p[0]>w)||screen.every(p=>p[1]<0)||screen.every(p=>p[1]>h))continue;
    const color=(material?.color||new T.Color('#a2b0af')).clone(),normal=vs[1].clone().sub(vs[0]).cross(vs[2].clone().sub(vs[0])).normalize();color.multiplyScalar(.66+.34*Math.abs(normal.y));const depth=-clipped.reduce((n,v)=>n+v.p.z,0)/clipped.length;color.lerp(fog,Math.min(.85,Math.max(0,(depth-70)/200)));
    const data={screen,depth:depth-(material.userData?.driveDepthBias||0),layer:material.userData?.driveLayer||0,color:'#'+color.getHexString(),opacity:material.opacity??1,repeat:material.map?.wrapS===T.RepeatWrapping};
    if(image){for(let n=1;n<clipped.length-1;n++)triangles.push({...data,screen:[screen[0],screen[n],screen[n+1]],uv:[clipped[0].uv,clipped[n].uv,clipped[n+1].uv],image});}else triangles.push(data);budget++;
   }
  }
  triangles.sort((a,b)=>a.layer-b.layer||b.depth-a.depth);
  for(const t of triangles){ctx.globalAlpha=t.opacity;ctx.fillStyle=t.image?'#192b36':t.color;ctx.beginPath();t.screen.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill();if(t.opacity>=.98&&!t.image){ctx.strokeStyle=t.color;ctx.lineWidth=.45;ctx.stroke();}if(t.image)this.drawTexture(ctx,t);}
  ctx.globalAlpha=1;
  if(!this.preview){ctx.fillStyle='#173b43bb';ctx.fillRect(w/2-110,6,220,20);ctx.fillStyle='#d5e5df';ctx.textAlign='center';ctx.font='11px sans-serif';ctx.fillText('3D 호환 모드 · 그림자 간소화',w/2,20);}this.renderCost=performance.now()-now;
 }
 textureImage(map){if(!map)return null;const image=map.image;if(image?.getContext)return image;if(!image?.data)return null;let canvas=this.textureCanvases.get(map);if(canvas)return canvas;canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;const ctx=canvas.getContext('2d');if(!ctx?.createImageData||!ctx?.putImageData)return null;const pixels=ctx.createImageData(image.width,image.height);pixels.data.set(image.data);ctx.putImageData(pixels,0,0);this.textureCanvases.set(map,canvas);return canvas;}
 drawTexture(ctx,t){const uv=t.uv.map(([u,v])=>[u*t.image.width,v*t.image.height]),[[u0,v0],[u1,v1],[u2,v2]]=uv,[[x0,y0],[x1,y1],[x2,y2]]=t.screen,det=u0*(v1-v2)+u1*(v2-v0)+u2*(v0-v1);if(Math.abs(det)<1e-6)return;const a=(x0*(v1-v2)+x1*(v2-v0)+x2*(v0-v1))/det,b=(y0*(v1-v2)+y1*(v2-v0)+y2*(v0-v1))/det,c=(x0*(u2-u1)+x1*(u0-u2)+x2*(u1-u0))/det,d=(y0*(u2-u1)+y1*(u0-u2)+y2*(u1-u0))/det,e=(x0*(u1*v2-u2*v1)+x1*(u2*v0-u0*v2)+x2*(u0*v1-u1*v0))/det,f=(y0*(u1*v2-u2*v1)+y1*(u2*v0-u0*v2)+y2*(u0*v1-u1*v0))/det;ctx.save();ctx.clip();ctx.transform(a,b,c,d,e,f);if(t.repeat){let pattern=this.patterns.get(t.image);if(!pattern){pattern=ctx.createPattern(t.image,'repeat');this.patterns.set(t.image,pattern);}ctx.fillStyle=pattern;const us=uv.map(p=>p[0]),vs=uv.map(p=>p[1]);ctx.fillRect(Math.min(...us)-1,Math.min(...vs)-1,Math.max(...us)-Math.min(...us)+2,Math.max(...vs)-Math.min(...vs)+2);}else ctx.drawImage(t.image,0,0);ctx.restore();}
}
