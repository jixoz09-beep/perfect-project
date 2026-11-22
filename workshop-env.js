import * as T from 'three';
import {resolveTranslation,bottom} from 'motion';
let sequence=0;
const material=(color,metalness=.4)=>new T.MeshStandardMaterial({color,metalness,roughness:.42});
function part(group,geometry,mat,position,id=null){const m=new T.Mesh(geometry,mat);m.position.fromArray(position);m.userData.partId=id||'equipment-'+(++sequence);m.castShadow=m.receiveShadow=true;group.add(m);return m;}
const box=(g,size,pos,mat,id)=>part(g,new T.BoxGeometry(...size),mat,pos,id);
function groupsOf(project){const byId=new Map(project.parts.map(p=>[p.id,p])),groups=new Map();for(const p of project.parts){let root=p;const seen=new Set();while(root.parentId&&byId.has(root.parentId)&&!seen.has(root.id)){seen.add(root.id);root=byId.get(root.parentId);}if(!groups.has(root.id))groups.set(root.id,[]);groups.get(root.id).push(p);}return [...groups.values()];}
export class CarLift{
 constructor(garage){this.group=new T.Group();this.group.name='Four-post vehicle lift';garage.add(this.group);this.moving=new T.Group();this.group.add(this.moving);this.height=0;this.maxHeight=1.8;this.mode=null;this.blocked=false;this.supports=[];this.fixed=[];
  const blue=material('#28688d'),dark=material('#34434a'),yellow=material('#ecc24c'),rubber=material('#252c30',.1);
  for(const x of [-3.25,3.25])for(const z of [-1.55,1.55]){this.fixed.push(box(this.group,[.27,4,.27],[x,2,z],blue));this.fixed.push(box(this.group,[.55,.08,.55],[x,.04,z],dark));box(this.group,[.29,.23,.29],[x,3.7,z],yellow);box(this.group,[.285,3.2,.025],[x,1.8,z+.15],rubber);}
  for(const z of [-.84,.84])this.supports.push(box(this.moving,[6,.12,.62],[0,-.06,z],dark,'lift-runway-'+z));
  for(const x of [-3.07,3.07])this.supports.push(box(this.moving,[.18,.18,3.05],[x,-.12,0],blue,'lift-cross-'+x));
  for(const x of [-2.85,2.85])for(const z of [-.84,.84])box(this.moving,[.08,.006,.62],[x,.004,z],yellow);
  for(const z of [-.84,.84])for(const x of [-2,-1,0,1,2])box(this.moving,[.5,.003,.02],[x,.002,z],rubber);
  box(this.group,[.18,.42,.22],[3.43,1.25,1.55],dark);for(const [y,color]of [[1.36,'#7bd299'],[1.21,'#e69b5b'],[1.07,'#dd5959']])part(this.group,new T.SphereGeometry(.035,8,6),material(color,0),[3.54,y,1.67]);
  this.group.updateMatrixWorld(true);
 }
 setHeight(value){this.height=T.MathUtils.clamp(value,0,this.maxHeight);this.moving.position.y=this.height;this.group.updateMatrixWorld(true);}
 start(direction){this.mode=direction;this.blocked=false;}
 stop(){this.mode=null;}
 colliders(){return [...this.fixed,...this.supports];}
 riders(project,meshes){const groups=groupsOf(project).map(parts=>({parts,objects:parts.map(p=>meshes.get(p.id)).filter(Boolean)})),riders=[];let supports=[...this.supports],changed=true;
  while(changed){changed=false;for(const g of groups){if(riders.includes(g)||!g.objects.length||g.parts.some(p=>p.locked||p.physicsFixed))continue;const hit=resolveTranslation(g.objects,supports,new T.Vector3(0,-.006,0),{floor:false});if(hit.blocked){riders.push(g);supports.push(...g.objects);changed=true;}}}return riders;
 }
 step(project,meshes,elapsed,obstacles=[]){if(!this.mode||elapsed<=0)return {moved:false};const requested=(this.mode==='up'?1:-1)*.45*Math.min(.1,Math.max(0,elapsed)),dy=T.MathUtils.clamp(this.height+requested,0,this.maxHeight)-this.height;if(Math.abs(dy)<1e-8){this.stop();return {moved:false};}
  const riders=this.riders(project,meshes),ids=new Set(riders.flatMap(g=>g.parts.map(p=>p.id))),other=[...meshes.values()].filter(m=>!ids.has(m.userData.partId)),delta=new T.Vector3(0,dy,0);let allowed=dy;
  const limit=(rows,guided=false)=>{const r=resolveTranslation(rows,[...other,...obstacles,...(guided?[]:this.fixed)],delta,{floor:false});if(Math.abs(r.offset.y)<Math.abs(allowed))allowed=r.offset.y;};
  limit(this.supports,true);for(const g of riders)limit(g.objects);
  const blocked=Math.abs(allowed-dy)>1e-5;if(Math.abs(allowed)>1e-8){this.setHeight(this.height+allowed);for(const g of riders)for(const p of g.parts){p.position[1]+=allowed;const m=meshes.get(p.id);m.position.fromArray(p.position);m.updateMatrixWorld(true);}}
  if(blocked){this.blocked=true;this.stop();}if(this.height>=this.maxHeight-1e-6||this.height<=1e-6)this.stop();return {moved:Math.abs(allowed)>1e-8,blocked,carriedIds:[...ids],delta:allowed};
 }
}
export function createWorkshopEnvironment(garage,{labels=true}={}){
 const group=new T.Group();group.name='Workshop equipment';garage.add(group);const colliders=[],blue=material('#28667d'),steel=material('#75878d'),dark=material('#26343b'),wood=material('#9f8059',.05),red=material('#a4483c'),yellow=material('#d7ad3e');
 const fixed=(size,pos,mat)=>{const m=box(group,size,pos,mat);colliders.push(m);return m;};
 // Workbench, drawers and a wall-mounted tool board.
 fixed([4.2,.12,.95],[-5,1.02,-6.8],wood);for(const x of [-6.8,-3.2])fixed([.12,1,.12],[x,.5,-6.8],dark);
 fixed([1.35,.85,.8],[-6.8,.425,-5.6],red);for(let i=0;i<5;i++){box(group,[1.21,.12,.025],[-6.8,.13+i*.15,-5.185],steel);box(group,[.55,.02,.025],[-6.8,.16+i*.15,-5.16],dark);}
 fixed([3.9,1.45,.08],[-5,2.2,-7.75],dark);for(let i=0;i<8;i++){const x=-6.5+i*.42;box(group,[.045,.55,.035],[x,2.2,-7.68],steel);part(group,new T.TorusGeometry(.08,.018,6,16),steel,[x,2.5,-7.66]);}
 // Rolling tool cart and a diagnostic station.
 fixed([1,.65,.6],[5,.55,4.3],blue);for(let i=0;i<3;i++)box(group,[.86,.13,.035],[5,.4+i*.17,4.62],steel);
 for(const x of [4.62,5.38])for(const z of [4.1,4.5]){const wheel=part(group,new T.CylinderGeometry(.09,.09,.07,12),dark,[x,.12,z]);wheel.rotation.x=Math.PI/2;}
 fixed([.9,.08,.7],[5.5,1.05,-5.8],steel);fixed([.08,1,.08],[5.5,.5,-5.8],dark);fixed([.9,.55,.08],[5.5,1.55,-5.9],dark);box(group,[.76,.39,.012],[5.5,1.55,-5.85],new T.MeshBasicMaterial({color:'#5bafac'}));
 // Compressor, hose, spare tyres and an engine hoist.
 const tank=part(group,new T.CylinderGeometry(.32,.32,1.15,20),blue,[7.4,.5,-4.9]);tank.rotation.z=Math.PI/2;colliders.push(tank);for(const x of [7,7.8])fixed([.15,.2,.5],[x,.1,-4.9],dark);fixed([.5,.35,.45],[7.4,.99,-4.9],steel);
 for(let i=0;i<4;i++){const hose=part(group,new T.TorusGeometry(.35+i*.045,.018,6,30),dark,[7.4,.04,-3.7]);hose.rotation.x=Math.PI/2;}
 for(let i=0;i<3;i++){const tyre=part(group,new T.TorusGeometry(.3,.11,10,24),dark,[-9,.42,.1+i*.9]);tyre.rotation.y=Math.PI/2;colliders.push(tyre);}
 for(const z of [-4,-2.8])fixed([2,.12,.13],[7,.09,z],yellow);fixed([.18,1.8,.18],[6.4,.95,-3.4],yellow);const boom=fixed([1.7,.14,.14],[7.05,1.9,-3.4],yellow);boom.rotation.z=.15;part(group,new T.CylinderGeometry(.012,.012,.65,6),dark,[7.8,1.65,-3.4]);part(group,new T.TorusGeometry(.07,.015,6,14,Math.PI),steel,[7.8,1.32,-3.4]);
 if(labels&&typeof document!=='undefined'){const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=160;const ctx=canvas.getContext('2d');ctx.fillStyle='#183b4c';ctx.fillRect(0,0,1024,160);ctx.fillStyle='#e9d6ab';ctx.font='bold 74px sans-serif';ctx.fillText('AUTOVERSE  /  WORK BAY 01',30,105);const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;part(group,new T.PlaneGeometry(5.2,.8),new T.MeshBasicMaterial({map:texture}),[-4.5,4.4,-7.7]);}
 const lift=new CarLift(garage);garage.updateMatrixWorld(true);return {group,colliders,lift};
}
