import * as T from 'three';
export function vehicleProxy(g){
 if(g.userData.driveCanvasProxy)return;const p=g.parameters;let lo;
 if(g.type==='BoxGeometry')lo=new T.BoxGeometry(p.width,p.height,p.depth);
 else if(g.type==='CylinderGeometry')lo=new T.CylinderGeometry(p.radiusTop,p.radiusBottom,p.height,12);
 else if(g.type==='TubeGeometry')lo=new T.TubeGeometry(p.path,Math.min(8,p.tubularSegments),p.radius,4,p.closed);
 else if(g.type==='TorusGeometry')lo=new T.TorusGeometry(p.radius,p.tube,5,22);
 else if(g.type==='SphereGeometry')lo=new T.SphereGeometry(p.radius,12,7);
 if(lo)g.userData.driveCanvasProxy={position:lo.attributes.position,index:lo.index?.array};
}
export function batchVehicleGroup(parent){
 for(const ch of [...parent.children])if(ch.isGroup)batchVehicleGroup(ch);
 const groups=new Map();for(const ch of [...parent.children]){if(!ch.isMesh||ch.material.map)continue;const list=groups.get(ch.material)||[];list.push(ch);groups.set(ch.material,list);}
 for(const[material,list]of groups){if(list.length<2)continue;const p=[],n=[],ix=[],lp=[],li=[];let off=0,lo=0;
  for(const ch of list){ch.updateMatrix();const a=ch.geometry.clone().applyMatrix4(ch.matrix),pos=a.attributes.position,norm=a.attributes.normal,index=a.index?.array??Array.from({length:pos.count},(_,i)=>i);p.push(...pos.array);n.push(...norm.array);for(const i of index)ix.push(off+i);off+=pos.count;const proxy=ch.geometry.userData.driveCanvasProxy||{position:ch.geometry.attributes.position,index:ch.geometry.index?.array},v=proxy.position;for(let i=0;i<v.count;i++){const q=new T.Vector3().fromBufferAttribute(v,i).applyMatrix4(ch.matrix);lp.push(q.x,q.y,q.z);}for(const i of(proxy.index??Array.from({length:v.count},(_,i)=>i)))li.push(lo+i);lo+=v.count;parent.remove(ch);ch.geometry.dispose();a.dispose();}
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setAttribute('normal',new T.Float32BufferAttribute(n,3));g.setIndex(ix);g.userData.driveKeepDetail=true;g.userData.driveCanvasProxy={position:new T.Float32BufferAttribute(lp,3),index:li};const o=new T.Mesh(g,material);o.castShadow=true;o.receiveShadow=true;parent.add(o);
 }
}
