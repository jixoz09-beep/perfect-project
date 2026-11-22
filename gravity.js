/* Workshop gravity: fixed-orientation assemblies with continuous vertical contact. */
import * as T from 'three';
import {resolveTranslation,bottom} from 'motion';
export class WorkshopGravity{
 constructor(){this.states=new Map();this.acceleration=9.81;}
 wake(){this.states.clear();}
 step(project,meshes,elapsed,environment=[]){
  const rows=new Map(project.parts.map(p=>[p.id,p])),groups=new Map();
  for(const p of project.parts){let root=p;const seen=new Set();while(root.parentId&&rows.has(root.parentId)&&!seen.has(root.id)){seen.add(root.id);root=rows.get(root.parentId);}if(!groups.has(root.id))groups.set(root.id,[]);groups.get(root.id).push(p);}
  const work=[...groups.entries()].map(([id,parts])=>({id,parts,objects:parts.map(p=>meshes.get(p.id)).filter(Boolean)})).filter(g=>g.objects.length);
  if(work.every(g=>g.parts.some(p=>p.locked||p.physicsFixed)||this.states.get(g.id)?.sleeping))return {moved:false,awake:0};
  work.sort((a,b)=>Math.min(...a.objects.map(bottom))-Math.min(...b.objects.map(bottom)));
  let remaining=Math.min(.25,Math.max(0,elapsed)),moved=false,awake=0;
  while(remaining>1e-8){const dt=Math.min(.02,remaining);remaining-=dt;let stepMoved=false;const movedGroups=new Set();
   for(const group of work){if(group.parts.some(p=>p.locked||p.physicsFixed))continue;let state=this.states.get(group.id);if(!state){state={velocity:0,sleeping:false};this.states.set(group.id,state);}if(state.sleeping)continue;
    const low=Math.min(...group.objects.map(bottom));if(low<0){const lift=-low+.0002;for(const p of group.parts){p.position[1]+=lift;const mesh=meshes.get(p.id);if(mesh){mesh.position.fromArray(p.position);mesh.updateMatrixWorld(true);}}state.velocity=0;stepMoved=moved=true;movedGroups.add(group.id);}
    const ids=new Set(group.parts.map(p=>p.id)),others=[...meshes.values()].filter(m=>!ids.has(m.userData.partId)).concat(environment);
    const dy=state.velocity*dt-.5*this.acceleration*dt*dt;state.velocity-=this.acceleration*dt;
    const contact=resolveTranslation(group.objects,others,new T.Vector3(0,dy,0),{floor:true}),offset=contact.offset;
    if(offset.lengthSq()>1e-16){for(const p of group.parts){p.position=p.position.map((v,i)=>v+offset.getComponent(i));const mesh=meshes.get(p.id);if(mesh){mesh.position.fromArray(p.position);mesh.updateMatrixWorld(true);}}stepMoved=moved=true;movedGroups.add(group.id);}
    if(contact.blocked){state.velocity=0;state.sleeping=true;}
   }
   // Wake sleepers when another supporting object moves; keep accumulated velocities.
   if(stepMoved)for(const [id,s]of this.states)if(!movedGroups.has(id))s.sleeping=false;
  }
  for(const [id,s]of this.states)if(groups.has(id)&&!s.sleeping)awake++;
  return {moved,awake};
 }
}
