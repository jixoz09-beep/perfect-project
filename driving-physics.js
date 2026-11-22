/* Training simulation: metres / seconds. No AI services or network calls. */
import {JONGNO_MAP} from 'jongno-map';
export const ROAD_X=[-280,0,280],ROAD_Z=[-220,0,220],ROAD_HALF=9;
export const MAP_BOUNDS=JONGNO_MAP.bounds,SPAWN=JONGNO_MAP.spawn,ROAD_SEGMENTS=[];
const roadBuckets=new Map();
for(const road of JONGNO_MAP.roads)for(let i=0;i<road.points.length-1;i++){const a=road.points[i],b=road.points[i+1],segment={a,b,width:road.width,name:road.name,kind:road.kind,oneway:road.oneway};ROAD_SEGMENTS.push(segment);for(let x=Math.floor((Math.min(a[0],b[0])-road.width)/40);x<=Math.floor((Math.max(a[0],b[0])+road.width)/40);x++)for(let z=Math.floor((Math.min(a[1],b[1])-road.width)/40);z<=Math.floor((Math.max(a[1],b[1])+road.width)/40);z++){const key=x+','+z;const list=roadBuckets.get(key)||[];list.push(segment);roadBuckets.set(key,list);}}
export function segmentDistance(x,z,a,b){const dx=b[0]-a[0],dz=b[1]-a[1],t=clamp(((x-a[0])*dx+(z-a[1])*dz)/Math.max(.00001,dx*dx+dz*dz),0,1);return Math.hypot(x-a[0]-t*dx,z-a[1]-t*dz);}
export function roadLocation(x,z){let best=null,distance=1e10;for(const s of roadBuckets.get(Math.floor(x/40)+','+Math.floor(z/40))||[]){const d=segmentDistance(x,z,s.a,s.b);if(d<distance){best=s;distance=d;}}return best?{...best,distance}:null;}
export const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
export function driveEligibility(project){
 const parts=(project?.parts||[]).filter(p=>!p.trainingExcluded);
 const power=parts.filter(p=>['engine','motor'].includes(p.role));
 const wheels=parts.filter(p=>p.role==='wheel');const seats=parts.filter(p=>p.role==='seat');
 const checks=[{id:'power',name:'기본 동력장치',count:power.length,ok:power.length>0},{id:'wheel',name:'바퀴·휠',count:wheels.length,ok:wheels.length>0},{id:'seat',name:'좌석 1개 이상',count:seats.length,ok:seats.length>0}];
 return {ready:checks.every(c=>c.ok),checks,parts};
}
export function driveParameters(project){
 const {parts}=driveEligibility(project),wheels=parts.filter(p=>p.role==='wheel'),sources=parts.filter(p=>['motor','engine'].includes(p.role));
 const power=sources.reduce((n,p)=>n+(p.perf?.power||((p.perf?.torque||180)*(p.perf?.peakRpm||4000)*Math.PI/30000)),0);
 const xs=wheels.map(p=>p.position?.[0]||0);
 return {mass:clamp(parts.reduce((n,p)=>n+(p.mass||0),0),250,6000),power:clamp(power,8,700),wheelbase:clamp(xs.length>1?Math.max(...xs)-Math.min(...xs):2.6,1.4,5),grip:clamp(wheels.reduce((n,p)=>n+(p.perf?.grip||1),0)/Math.max(1,wheels.length),.4,1.5),steerLimit:.55,length:4.6,width:1.85};
}
export function signalAt(time){const phase=((time%90)+90)%90;return{phase,ew:phase<27?'green':phase<30?'amber':'red',ns:phase>=45&&phase<72?'green':phase>=72&&phase<75?'amber':'red',pedestrian:phase>=30&&phase<45||phase>=75};}
export function drivable(x,z){const [left,top,right,bottom]=MAP_BOUNDS;if(x<left||x>right||z<top||z>bottom)return false;return (roadBuckets.get(Math.floor(x/40)+','+Math.floor(z/40))||[]).some(s=>segmentDistance(x,z,s.a,s.b)<=s.width/2+.25);}
export function corners(s,extra=0){const l=(s.length||4.6)/2+extra,w=(s.width||1.85)/2+extra,c=Math.cos(s.yaw),q=Math.sin(s.yaw);return[[-l,-w],[-l,w],[l,w],[l,-w]].map(([x,z])=>[s.x+c*x+q*z,s.z-q*x+c*z]);}
export function overlaps(a,b,margin=0){const pa=corners(a,margin),pb=corners(b);for(const yaw of [a.yaw,b.yaw])for(const [x,z]of [[Math.cos(yaw),-Math.sin(yaw)],[Math.sin(yaw),Math.cos(yaw)]]){const aa=pa.map(p=>p[0]*x+p[1]*z),bb=pb.map(p=>p[0]*x+p[1]*z);if(Math.max(...aa)<Math.min(...bb)||Math.max(...bb)<Math.min(...aa))return false;}return true;}
export function integrateVehicle(s,input,p,dt){
 dt=clamp(dt,0,1/60);const old={x:s.x,z:s.z,yaw:s.yaw,distance:s.distance};const direction=s.reverse?-1:1,v=s.speed;
 const throttle=clamp(input.throttle||0,0,1),brake=clamp(input.brake||0,0,1),steer=clamp(input.steer||0,-1,1);
 s.steer=(s.steer||0)+(steer-(s.steer||0))*(1-Math.exp(-dt*9));
 const drive=Math.min(p.power*1000/Math.max(Math.abs(v),3),p.mass*4.5)*throttle*direction;
 const resistance=Math.sign(v)*(p.mass*.014*9.81+.43*v*v),deceleration=(input.handbrake?8:6)*p.grip*brake;
 s.speed=clamp(v+(drive-resistance)/p.mass*dt-Math.sign(v)*deceleration*dt,-8.3,33.3);
 if(!throttle&&(v*s.speed<0||Math.abs(s.speed)<.025))s.speed=0;
 if(input.handbrake&&Math.abs(s.speed)<.1)s.speed=0;
 const angle=s.steer*p.steerLimit/(1+Math.abs(s.speed)*.025);s.yaw+=s.speed/p.wheelbase*Math.tan(angle)*dt;
 s.x+=Math.cos(s.yaw)*s.speed*dt;s.z-=Math.sin(s.yaw)*s.speed*dt;
 s.distance+=Math.abs(s.speed)*dt;return old;
}
export function obstacleContact(s,buildings,cars,pedestrians){
 if([...corners(s),[s.x,s.z]].some(([x,z])=>!drivable(x,z)))return '연석';
 for(const b of buildings)if(Math.abs(s.x-b.x)<(s.length+b.length)/2+3&&Math.abs(s.z-b.z)<(s.length+b.width)/2+3&&(b.points?polygonContact(s,b.points):overlaps(s,b)))return '건물';
 for(const c of cars)if(Math.hypot(s.x-c.x,s.z-c.z)<12&&overlaps(s,c))return '차량';
 for(const p of pedestrians)if(Math.hypot(s.x-p.x,s.z-p.z)<5&&overlaps(s,{...p,length:.65,width:.65,yaw:0},.1))return '보행자';
 return null;
}
export class FixedStepper{constructor(){this.accumulator=0;}advance(dt,fn){this.accumulator+=clamp(dt,0,.2);let n=0;while(this.accumulator>=1/120&&n<24){fn(1/120);this.accumulator-=1/120;n++;}return n;}reset(){this.accumulator=0;}}
export function pathRoute(nodes,radius=15){
 const out=[];for(let i=0;i<nodes.length;i++){
  const a=nodes[(i+nodes.length-1)%nodes.length],b=nodes[i],c=nodes[(i+1)%nodes.length],dist=(p,q)=>Math.hypot(q[0]-p[0],q[1]-p[1]);
  const r=Math.min(radius,dist(a,b)/4,dist(b,c)/4),u=[(b[0]-a[0])/dist(a,b),(b[1]-a[1])/dist(a,b)],v=[(c[0]-b[0])/dist(b,c),(c[1]-b[1])/dist(b,c)];
  const enter=[b[0]-u[0]*r,b[1]-u[1]*r],exit=[b[0]+v[0]*r,b[1]+v[1]*r];out.push(enter);
  for(let j=1;j<=12;j++){const t=j/12;out.push([(1-t)**2*enter[0]+2*(1-t)*t*b[0]+t*t*exit[0],(1-t)**2*enter[1]+2*(1-t)*t*b[1]+t*t*exit[1]]);}
 }
 const segments=out.map((p,i)=>{const q=out[(i+1)%out.length];return{a:p,b:q,length:Math.hypot(q[0]-p[0],q[1]-p[1])};});return{segments,length:segments.reduce((n,s)=>n+s.length,0)};
}
export function routePose(route,d,lane=3){let pos=((d%route.length)+route.length)%route.length;for(const s of route.segments){if(pos<=s.length){const ux=(s.b[0]-s.a[0])/s.length,uz=(s.b[1]-s.a[1])/s.length;return{x:s.a[0]+ux*pos-uz*lane,z:s.a[1]+uz*pos+ux*lane,yaw:Math.atan2(-uz,ux),length:4.5,width:1.85};}pos-=s.length;}return{x:0,z:3,yaw:0,length:4.5,width:1.85};}
export function mustStopAtSignal(car,time){const c=Math.cos(car.yaw),s=-Math.sin(car.yaw),axis=Math.abs(c)>Math.abs(s)?'ew':'ns';if(signalAt(time)[axis]==='green')return false;for(const {point:[x,z],width}of JONGNO_MAP.signals){const dx=x-car.x,dz=z-car.z,ahead=dx*c+dz*s,lateral=Math.abs(-dx*s+dz*c);const half=width/2;if(ahead>half+2&&ahead<half+15&&lateral<Math.max(4,half))return true;}return false;}
function pointInPolygon(point,polygon){let inside=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){const a=polygon[i],b=polygon[j];if((a[1]>point[1])!==(b[1]>point[1])&&point[0]<(b[0]-a[0])*(point[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;}return inside;}
function intersect(a,b,c,d){const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);return cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0;}
function polygonContact(car,polygon){const rectangle=corners(car);if(rectangle.some(p=>pointInPolygon(p,polygon))||polygon.some(p=>pointInPolygon(p,rectangle)))return true;for(let i=0;i<4;i++)for(let j=0;j<polygon.length-1;j++)if(intersect(rectangle[i],rectangle[(i+1)%4],polygon[j],polygon[j+1]))return true;return false;}
function laneOffset(s){const d=Math.max(.001,s.length);return [-(s.b[1]-s.a[1])/d*s.offset,(s.b[0]-s.a[0])/d*s.offset];}
export function mappedRoute(segments){return {segments:segments.map((s,i)=>{const v=laneOffset(s),previous=laneOffset(segments[(i+segments.length-1)%segments.length]),next=laneOffset(segments[(i+1)%segments.length]);return {...s,startOffset:[(v[0]+previous[0])/2,(v[1]+previous[1])/2],endOffset:[(v[0]+next[0])/2,(v[1]+next[1])/2]};}),length:segments.reduce((n,s)=>n+s.length,0)};}
function mappedPosition(route,d){let pos=((d%route.length)+route.length)%route.length;for(const s of route.segments){if(pos<=s.length){const ux=(s.b[0]-s.a[0])/s.length,uz=(s.b[1]-s.a[1])/s.length,offset=laneOffset(s),blend=Math.min(5,s.length/2);let [ox,oz]=offset;if(s.startOffset&&pos<blend){const t=pos/blend;ox=s.startOffset[0]*(1-t)+ox*t;oz=s.startOffset[1]*(1-t)+oz*t;}else if(s.endOffset&&pos>s.length-blend){const t=(pos-s.length+blend)/blend;ox=ox*(1-t)+s.endOffset[0]*t;oz=oz*(1-t)+s.endOffset[1]*t;}return{x:s.a[0]+ux*pos+ox,z:s.a[1]+uz*pos+oz};}pos-=s.length;}return{x:SPAWN.x,z:SPAWN.z};}
export function mappedRoutePose(route,d){const p=mappedPosition(route,d),a=mappedPosition(route,d-.25),b=mappedPosition(route,d+.25);return {...p,yaw:Math.atan2(-(b.z-a.z),b.x-a.x),length:4.4,width:1.78};}
