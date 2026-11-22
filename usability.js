import * as T from 'three';
export function findFreePosition(part,geometry,obstacles,gap=.03){
 const boxAt=position=>geometry.boundingBox.clone().applyMatrix4(new T.Matrix4().compose(new T.Vector3(...position),new T.Quaternion().setFromEuler(new T.Euler(...part.rotation)),new T.Vector3(...part.size)));
 geometry.computeBoundingBox();const free=pos=>{const box=boxAt(pos);return box.min.y>=.00015&&!obstacles.some(b=>b.clone().expandByScalar(gap).intersectsBox(box));};
 if(free(part.position))return [...part.position];const size=boxAt([0,0,0]).getSize(new T.Vector3()),floorY=-boxAt([0,0,0]).min.y+.0003;
 const edge=Math.max(0,...obstacles.map(b=>b.max.z))+size.z/2+gap;
 for(let row=0;row<100;row++)for(let col=0;col<9;col++){const p=[(col-4)*(size.x+gap),Math.max(part.position[1],floorY),edge+row*(size.z+gap)];if(free(p))return p;}
 throw Error('빈 배치 공간을 찾을 수 없습니다.');
}
export function engineeringAnchors(fab,dimensions,origin=[0,0,0]){
 const v=fab.params,rows=[],add=(id,name,p)=>rows.push({id:'fab-'+id,name,point:p.map((x,i)=>(x-origin[i])/dimensions[i])});
 if(fab.type==='block')for(let i=0;i<v.cylinders;i++){const x=(i-(v.cylinders-1)/2)*v.pitch;add('bore-'+i,'실린더 '+(i+1)+' 상단',[x,v.height/2,0]);add('bore-bottom-'+i,'실린더 '+(i+1)+' 하단',[x,-v.height/2,0]);}
 if(['liner','piston','brake_piston','damper_case'].includes(fab.type)){const h=v.length||v.height;add('axis-top','축 상단',[0,h/2,0]);add('axis-bottom','축 하단',[0,-h/2,0]);}
 if(['rim','tyre','hub','disc','gear','bevel','bearing','shaft','rotor','stator','tie_rod'].includes(fab.type)){const w=v.width||v.length;add('axis','회전축 중심',[0,0,0]);if(w){add('axis-front','축 앞 끝',[0,0,w/2]);add('axis-back','축 뒤 끝',[0,0,-w/2]);}}
 return rows;
}
export function simulationSteps(elapsed){let rest=Math.min(.5,Math.max(0,elapsed)),steps=[];while(rest>1e-8){const dt=Math.min(.025,rest);steps.push(dt);rest-=dt;}return steps;}

export function fabricationStartRotation(type){return type==='panel'?[-Math.PI/2,0,0]:[0,0,0];}
export function positionOnSurface(part,geometry,point,clearance=.0003){
 if(Array.isArray(point.placement))return [...point.placement];geometry.computeBoundingBox();const box=geometry.boundingBox.clone().applyMatrix4(new T.Matrix4().compose(new T.Vector3(),new T.Quaternion().setFromEuler(new T.Euler(...part.rotation)),new T.Vector3(...part.size))),center=box.getCenter(new T.Vector3()),half=box.getSize(new T.Vector3()).multiplyScalar(.5),normal=point.normal?.clone().normalize()||new T.Vector3(0,1,0),radius=Math.abs(normal.x)*half.x+Math.abs(normal.y)*half.y+Math.abs(normal.z)*half.z;return point.clone().sub(center).addScaledVector(normal,radius+clearance).toArray();
}
export function dropPlanePoint(ray,camera,target){const ground=ray.intersectPlane(new T.Plane(new T.Vector3(0,1,0),0),new T.Vector3());if(ground&&ground.distanceTo(camera.position)<Math.max(1,camera.position.distanceTo(target))*10)return ground;const p=ray.intersectPlane(new T.Plane().setFromNormalAndCoplanarPoint(camera.getWorldDirection(new T.Vector3()),target),new T.Vector3());if(p)p.y=Math.max(0,p.y);return p;}
export function automaticJointKind(a,b){return [a,b].every(p=>['steel','aluminum','paint','copper'].includes(p.material?.key)||p.material?.metalness>=.5)?'weld':'bolt';}
export function nearestSurface(mesh,point){mesh.updateMatrixWorld(true);const g=mesh.geometry,a=g.attributes.position,index=g.index,n=index?index.count:a.count,triangle=new T.Triangle(),candidate=new T.Vector3();let best=null,distance=Infinity;for(let i=0;i<n;i+=3){for(let k=0;k<3;k++)[triangle.a,triangle.b,triangle.c][k].fromBufferAttribute(a,index?index.getX(i+k):i+k).applyMatrix4(mesh.matrixWorld);const normal=triangle.getNormal(new T.Vector3());if(normal.lengthSq()<.5)continue;triangle.closestPointToPoint(point,candidate);const d=candidate.distanceToSquared(point);if(d<distance){distance=d;best={point:candidate.clone(),normal};}}return best;}
export function closestJointPlacement(child,parent){const center=new T.Box3().setFromObject(child).getCenter(new T.Vector3()),target=nearestSurface(parent,center);if(!target)throw Error('체결할 표면을 찾을 수 없습니다.');const source=nearestSurface(child,target.point);if(!source)throw Error('부품 표면을 찾을 수 없습니다.');const outward=source.point.clone().sub(target.point);if(outward.lengthSq()<1e-12)outward.copy(target.normal);outward.normalize();return {delta:target.point.clone().addScaledVector(outward,.0002).sub(source.point),source:source.point,target:target.point,normal:target.normal};}
const INSERT_TARGETS={liner:['block'],piston:['liner','block'],rim:['tyre'],tyre:['rim'],bearing:['shaft','tie_rod','damper_rod'],shaft:['bearing','hub','gear','rotor'],gear:['shaft'],bevel:['shaft'],damper_rod:['damper_case'],rotor:['stator','bearing']};
export function insertionTargets(p){return INSERT_TARGETS[p.fabrication?.type]||[];}
export function insertionAxis(p){return ['block','liner','piston','damper_case'].includes(p.fabrication?.type)?new T.Vector3(0,1,0):new T.Vector3(0,0,1);}

export function alignedJointPlacement(child,parent,tolerance=Math.PI/9){
 const cq=child.getWorldQuaternion(new T.Quaternion()),pq=parent.getWorldQuaternion(new T.Quaternion()),axes=[new T.Vector3(1,0,0),new T.Vector3(0,1,0),new T.Vector3(0,0,1)];let best=cq.clone(),angle=Infinity;
 for(let i=0;i<3;i++)for(let j=0;j<3;j++)if(i!==j)for(const a of [-1,1])for(const b of [-1,1]){const x=axes[i].clone().multiplyScalar(a),y=axes[j].clone().multiplyScalar(b),z=x.clone().cross(y),q=pq.clone().multiply(new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(x,y,z))),d=q.angleTo(cq);if(d<angle){angle=d;best=q;}}
 if(angle>tolerance)best.copy(cq);const pos=new T.Vector3(),q=new T.Quaternion(),scale=new T.Vector3();child.matrixWorld.decompose(pos,q,scale);const matrix=new T.Matrix4().compose(pos,best,scale),preview=new T.Mesh(child.geometry);preview.matrixAutoUpdate=false;preview.matrix.copy(matrix);preview.matrixWorld.copy(matrix);
 parent.geometry.computeBoundingBox();const center=new T.Box3().setFromObject(preview).getCenter(new T.Vector3()),nearest=nearestSurface(parent,center);if(!nearest)throw Error('정렬할 표면을 찾을 수 없습니다.');const localNormal=nearest.normal.clone().applyMatrix3(new T.Matrix3().setFromMatrix4(parent.matrixWorld).transpose()).normalize(),components=localNormal.toArray().map(Math.abs),axis=components.indexOf(Math.max(...components)),local=parent.worldToLocal(center.clone()),targetCenter=parent.geometry.boundingBox.getCenter(new T.Vector3());for(let k=0;k<3;k++)if(k!==axis)local.setComponent(k,targetCenter.getComponent(k));const correction=parent.localToWorld(local).sub(center);matrix.setPosition(pos.add(correction));preview.matrix.copy(matrix);preview.matrixWorld.copy(matrix);const plan=closestJointPlacement(preview,parent);matrix.premultiply(new T.Matrix4().makeTranslation(...plan.delta.toArray()));return {...plan,matrix,correctedAngle:angle<=tolerance?angle:0};
}
