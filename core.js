import {MAX_PARTS,validateSurface,validateHinge} from 'precision';
/* AUTOVERSE Workshop — deterministic project and vehicle model. Units: m, kg, s, N. */
export const VERSION=2;
export const MATERIALS={
 copper:{name:'구리 · Copper',color:'#c9854b',metalness:.92,roughness:.28,density:8960,clearcoat:0},
 steel:{name:'강철 · Steel',color:'#647080',metalness:.88,roughness:.28,density:7850,clearcoat:.1},
 aluminum:{name:'알루미늄 · Aluminum',color:'#c3ccd4',metalness:.92,roughness:.22,density:2700,clearcoat:.1},
 paint:{name:'자동차 도장 · Paint',color:'#d45b35',metalness:.58,roughness:.23,density:2700,clearcoat:1},
 rubber:{name:'고무 · Rubber',color:'#202329',metalness:0,roughness:.88,density:1150,clearcoat:0},
 glass:{name:'유리 · Glass',color:'#b7d9df',metalness:0,roughness:.08,density:2500,transmission:.78,opacity:.42,clearcoat:1},
 carbon:{name:'탄소섬유 · Carbon',color:'#30353c',metalness:.28,roughness:.32,density:1600,clearcoat:.7},
 plastic:{name:'플라스틱 · Polymer',color:'#393d43',metalness:.05,roughness:.52,density:1050,clearcoat:.1},
 fabric:{name:'직물 · Fabric',color:'#45474a',metalness:0,roughness:1,density:400,clearcoat:0}
};
const P=(id,name,en,category,shape,size,material,mass,perf={})=>({id,name,en,category,shape,size,material,mass,perf});
export const PRESETS=[
 P('frame','래더 프레임','Ladder frame','구조','frame',[3.5,.22,1.45],'steel',105),
 P('spaceframe','스페이스 프레임','Space frame','구조','spaceframe',[3.4,1.05,1.5],'steel',95),
 P('shell','차체 기본 셸','Body shell','구조','body',[4.6,1.35,1.82],'steel',180),
 P('floor','바닥 패널','Floor pan','구조','box',[2.8,.05,1.4],'steel',45),
 P('panel','자유 곡면 패널','Sculpt panel','구조','panel',[1.2,.06,.8],'paint',6),
 P('beam','구조 빔','Structural beam','구조','box',[1.2,.08,.08],'steel',5),
 P('tube','빈 원형 파이프','Hollow tube','구조','tube',[.07,.8,.07],'steel',2),
 P('engine','내연기관','Combustion engine','동력','engine',[.65,.65,.62],'aluminum',145,{torque:260,peakRpm:4200,redline:6800,idle:850,displacement:2,cylinders:4,efficiency:.3}),
 P('motor','전기모터','Electric motor','동력','motor',[.48,.42,.48],'aluminum',55,{power:150,torque:320,peakRpm:4000,redline:14000,efficiency:.92}),
 P('transmission','변속기','Transmission','동력','transmission',[.55,.38,.38],'aluminum',48,{ratios:[3.55,2.15,1.45,1.05,.82,.67],finalDrive:3.9,efficiency:.92}),
 P('differential','차동장치','Differential','동력','differential',[.35,.28,.42],'steel',24,{finalDrive:3.9}),
 P('shaft','구동축','Drive shaft','동력','shaft',[1.2,.07,.07],'steel',9),
 P('turbo','터보차저','Turbocharger','동력','torus',[.23,.23,.18],'steel',7,{boost:1.3}),
 P('exhaust','배기 파이프','Exhaust','동력','tube',[.08,1.5,.08],'steel',8),
 P('battery','고전압 배터리','Traction battery','에너지','battery',[1.8,.18,1.2],'aluminum',350,{capacity:65,voltage:400,maxPower:220}),
 P('fuel','연료 탱크','Fuel tank','에너지','rounded',[.7,.28,.5],'plastic',12,{litres:50}),
 P('inverter','인버터','Inverter','에너지','fins',[.4,.15,.3],'aluminum',12,{maxPower:200,efficiency:.97}),
 P('radiator','라디에이터','Radiator','에너지','radiator',[.65,.48,.08],'aluminum',7,{cooling:100}),
 P('pump','냉각 펌프','Coolant pump','에너지','motor',[.15,.16,.15],'aluminum',2,{flow:45}),
 P('wheel','타이어·휠','Wheel & tyre','섀시','wheel',[.65,.65,.235],'rubber',19,{grip:1.05,rolling:.013}),
 P('brake','브레이크','Brake disc','섀시','brake',[.3,.3,.025],'steel',6,{brakeTorque:1600}),
 P('suspension','현가장치','Suspension','섀시','spring',[.15,.4,.15],'steel',7,{springRate:35,travel:.16}),
 P('steering','조향 랙','Steering rack','섀시','shaft',[1.2,.09,.09],'steel',9,{steerAngle:32}),
 P('controlarm','컨트롤 암','Control arm','섀시','arm',[.45,.06,.38],'steel',4),
 P('hub','허브','Hub','섀시','brake',[.15,.15,.09],'steel',3),
 P('seat','좌석','Seat','실내','seat',[.52,.95,.55],'fabric',16),
 P('steeringwheel','스티어링 휠','Steering wheel','실내','torus',[.36,.36,.06],'rubber',2),
 P('dashboard','대시보드','Dashboard','실내','rounded',[.35,.32,1.4],'plastic',9),
 P('pedal','페달','Pedal','실내','box',[.14,.025,.08],'aluminum',.4),
 P('glass','유리 패널','Glass panel','외장','panel',[.7,.018,1.35],'glass',8),
 P('lamp','조명','Lamp','외장','rounded',[.18,.13,.32],'glass',1.3,{lumens:1800}),
 P('wing','에어로 윙','Aero wing','외장','wing',[.28,.065,1.5],'carbon',4,{downforce:1}),
 P('door','도어 패널','Door panel','외장','panel',[1.1,.035,.75],'paint',15),
 P('custom','자유 부품','Custom part','자유','rounded',[.5,.5,.5],'aluminum',5)
];
export const SHAPES=['box','rounded','sphere','cylinder','tube','torus','panel','frame','spaceframe','body','engine','motor','transmission','differential','shaft','battery','fins','radiator','wheel','brake','spring','arm','seat','wing'];
export const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
export const clone=o=>JSON.parse(JSON.stringify(o));
export function emptyProject(){return {format:'AUTOVERSE_WORKSHOP',version:VERSION,name:'UNTITLED / 나의 첫 자동차',parts:[],rootId:null,aero:{cd:.32,area:2.1,airDensity:1.225},nextId:1,fitAllowances:{}};}
export function newPart(preset,project){
 const p=typeof preset==='string'?PRESETS.find(x=>x.id===preset):preset;
 if(!p)throw Error('알 수 없는 기본 부품입니다.');
 const id='part-'+project.nextId++;
 return {id,preset:p.id,name:p.name,role:p.id,shape:p.shape,size:[...p.size],position:[0,Math.max(p.size[1]/2,.06),0],rotation:[0,0,0],material:{...MATERIALS[p.material],key:p.material},mass:p.mass,massMode:'manual',fillFactor:.12,perf:clone(p.perf),parentId:null,anchors:[{id:'center',name:'중심',point:[0,0,0]},{id:'top',name:'상단',point:[0,.5,0]},{id:'bottom',name:'하단',point:[0,-.5,0]},{id:'front',name:'전방',point:[.5,0,0]},{id:'rear',name:'후방',point:[-.5,0,0]},{id:'left',name:'좌측',point:[0,0,.5]},{id:'right',name:'우측',point:[0,0,-.5]}],visible:true,locked:false,vertices:null,colors:null,resolution:16,bodyShellVersion:p.shape==='body'?2:undefined};
}
export function descendants(project,id){const out=[];const walk=k=>{for(const p of project.parts)if(p.parentId===k&&!out.includes(p.id)){out.push(p.id);walk(p.id);}};walk(id);return out;}
export function canAttach(project,child,parent){return child!==parent&&!descendants(project,child).includes(parent)&&project.parts.some(p=>p.id===child)&&project.parts.some(p=>p.id===parent);}
export function assembledParts(project){if(!project.rootId)return [];const ids=new Set([project.rootId,...descendants(project,project.rootId)]);return project.parts.filter(p=>ids.has(p.id));}
export function torqueAt(p,rpm){const v=p.perf||{};const peak=v.peakRpm||4000,redline=v.redline||7000,torque=v.torque||0;if(rpm<0||rpm>redline)return 0;if(p.role==='motor'){const power=(v.power||0)*1000;return Math.min(torque,power/Math.max(rpm*Math.PI/30,1));}const r=rpm/peak;return torque*clamp(1-.35*(r-1)**2,.3,1);}
export function vehicleStats(project){
 const parts=assembledParts(project),mass=Math.max(0,parts.reduce((s,p)=>s+Math.max(0,p.mass||0),0));
 const engines=parts.filter(p=>p.role==='engine'||p.role==='motor'),wheels=parts.filter(p=>p.role==='wheel');
 const transmission=parts.find(p=>p.role==='transmission'),diff=parts.find(p=>p.role==='differential');
 const ratios=transmission?.perf.ratios?.length?transmission.perf.ratios:[9];
 const finalDrive=transmission?Math.max(.1,diff?.perf.finalDrive||transmission.perf.finalDrive||3.9):1;
 const radius=wheels.length?wheels.reduce((s,p)=>s+(p.size[0]+p.size[1])/4,0)/wheels.length:.325;
 const grip=wheels.length?wheels.reduce((s,p)=>s+(p.perf.grip||1),0)/wheels.length:0;
 const rolling=wheels.length?wheels.reduce((s,p)=>s+(p.perf.rolling||.013),0)/wheels.length:.013;
 const batteries=parts.filter(p=>p.role==='battery'),inverter=parts.find(p=>p.role==='inverter');
 const batteryLimit=batteries.reduce((s,p)=>s+(p.perf.maxPower||0),0),invLimit=inverter?.perf.maxPower||Infinity;
 let power=0,torque=0,redline=0;
 for(const p of engines){let peak=0;for(let rpm=100;rpm<=(p.perf.redline||7000);rpm+=100)peak=Math.max(peak,torqueAt(p,rpm)*rpm*Math.PI/30000);if(p.role==='motor')peak=Math.min(peak,batteryLimit,invLimit);power+=peak;torque+=p.perf.torque||0;redline=Math.max(redline,p.perf.redline||7000);}
 const brakes=parts.filter(p=>p.role==='brake'),brakeForce=brakes.reduce((s,p)=>s+(p.perf.brakeTorque||0),0)/radius;
 const brakeDecel=Math.min(grip*9.81,brakeForce/Math.max(mass,1));
 const steering=parts.find(p=>p.role==='steering'),wheelXs=wheels.map(p=>p.position[0]);
 const wheelbase=wheels.length>1?Math.max(.8,Math.max(...wheelXs)-Math.min(...wheelXs)):2.5;
 const energy=batteries.reduce((s,p)=>s+(p.perf.capacity||0),0),fuel=parts.filter(p=>p.role==='fuel').reduce((s,p)=>s+(p.perf.litres||0),0);
 const checks=[['주구조 / Frame',!!project.rootId],['장착된 바퀴 4개 / Wheels',wheels.length>=4],['장착된 동력원 / Power unit',engines.length>0],['에너지 공급 / Energy',engines.some(p=>p.role==='motor')?energy>0:fuel>0],['장착된 조향장치 / Steering',!!steering],['장착된 브레이크 / Brakes',brakes.length>0],['내연기관 변속기 / Gearbox',!engines.some(p=>p.role==='engine')||!!transmission]];
 const area=Math.max(.1,project.aero.area),cd=Math.max(.01,project.aero.cd),rho=project.aero.airDensity||1.225;
 const rollingForce=mass*9.81*rolling;
 const driveEfficiency=transmission?.perf.efficiency||.94;
 const firstForce=Math.min(grip*mass*9.81,torque*ratios[0]*finalDrive*driveEfficiency/radius);
 const forceAt=(v,gear=0,throttle=1)=>{
   const ratio=ratios[clamp(gear,0,ratios.length-1)]*finalDrive;
   const rpmWheel=Math.abs(v)/radius*ratio*30/Math.PI;
   let t=0;for(const p of engines)t+=torqueAt(p,Math.max(p.role==='engine'?p.perf.idle||800:0,rpmWheel));
   const gearing=t*ratio*driveEfficiency/radius;
   const powerForce=power*1000*driveEfficiency/Math.max(Math.abs(v),1);
   return Math.min(gearing,powerForce,grip*mass*9.81)*throttle;
 };
 let speed=0,time100=null;for(let t=0;t<=90;t+=.05){const rpm=speed/radius*ratios[0]*finalDrive*30/Math.PI;let gear=0;while(gear<ratios.length-1&&speed/radius*ratios[gear]*finalDrive*30/Math.PI>redline*.88)gear++;const f=forceAt(speed,gear)-rollingForce-.5*rho*cd*area*speed*speed;speed=Math.max(0,speed+f/Math.max(mass,1)*.05);if(speed>=100/3.6&&time100===null)time100=t;}
 return {parts,mass,power,torque,radius,grip,rolling,ratios,finalDrive,redline,brakeDecel,wheelbase,steerAngle:steering?.perf.steerAngle||0,energy,fuel,checks,ready:checks.every(x=>x[1]),time100,topSpeed:speed*3.6,stopDistance:brakeDecel>0?(100/3.6)**2/(2*brakeDecel):Infinity,area,cd,rho,rollingForce,forceAt,driveEfficiency};
}
export function stepVehicle(state,stats,input,dt){
 dt=clamp(dt,0,.05);const m=Math.max(stats.mass,1),abs=Math.abs(state.speed);
 if(!state.gear)state.gear=1;
 if(input.auto){let rpm=abs/stats.radius*stats.ratios[state.gear-1]*stats.finalDrive*30/Math.PI;if(rpm>stats.redline*.88&&state.gear<stats.ratios.length)state.gear++;if(rpm<stats.redline*.28&&state.gear>1)state.gear--;}
 const drag=.5*stats.rho*stats.cd*stats.area*abs*abs+stats.rollingForce;
 const drive=stats.forceAt(abs,state.gear-1,input.throttle||0)*(input.reverse?-1:1);
 const brake=(input.brake||0)*stats.brakeDecel*m;
 let acceleration=(drive-(Math.sign(state.speed)||Math.sign(drive))*drag-Math.sign(state.speed)*brake)/m;
 if(abs<.02&&Math.abs(drive)<drag+brake)acceleration=0;
 let v=state.speed+acceleration*dt;if(state.speed&&Math.sign(v)!==Math.sign(state.speed)&&(input.throttle||0)===0)v=0;
 if(state.usedKWh>=stats.energy&&stats.energy>0)v=state.speed-Math.sign(state.speed)*Math.min(abs,drag/m*dt);
 state.speed=v;const steer=(input.steer||0)*stats.steerAngle*Math.PI/180;
 state.yaw-=v/stats.wheelbase*Math.tan(steer)*dt;
 state.x+=Math.cos(state.yaw)*v*dt;state.z-=Math.sin(state.yaw)*v*dt;
 state.distance+=abs*dt;state.time+=dt;state.accel=acceleration;
 state.rpm=abs/stats.radius*stats.ratios[state.gear-1]*stats.finalDrive*30/Math.PI;
 state.usedKWh+=(Math.max(0,drive*v)/Math.max(stats.driveEfficiency,.1)/3600000)*dt;
 return state;
}
export function validateProject(raw){
 if(!raw||raw.format!=='AUTOVERSE_WORKSHOP'||raw.version!==VERSION||!Array.isArray(raw.parts))throw Error('AUTOVERSE Workshop v2 프로젝트 JSON을 선택하세요.');
 if(raw.parts.length>MAX_PARTS)throw Error('한 프로젝트는 부품 '+MAX_PARTS+'개까지 사용할 수 있습니다.');
 if(raw.workshopLiftHeight!==undefined&&(!Number.isFinite(raw.workshopLiftHeight)||raw.workshopLiftHeight<0||raw.workshopLiftHeight>1.8))throw Error('리프트 높이 설정이 올바르지 않습니다.');
 const p=clone(raw),ids=new Set(),roles=new Set(PRESETS.map(x=>x.id));
 const finiteVec=(v,min,max)=>Array.isArray(v)&&v.length===3&&v.every(x=>Number.isFinite(x)&&x>=min&&x<=max);
 let vertices=0;
 for(const a of p.parts){
 if(typeof a.id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(a.id)||ids.has(a.id))throw Error('중복되거나 잘못된 부품 ID입니다.');ids.add(a.id);
 if(!roles.has(a.role)||!SHAPES.includes(a.shape))throw Error('지원하지 않는 부품 또는 형상입니다.');
 if(!finiteVec(a.size,.0001,100)||!finiteVec(a.position,-10000,10000)||!finiteVec(a.rotation,-10000,10000)||!Number.isFinite(a.mass)||a.mass<0||a.mass>1e6)throw Error('부품 수치가 올바르지 않습니다.');
 if(typeof a.name!=='string'||a.name.length>180||!a.material||!/^#[0-9a-f]{6}$/i.test(a.material.color))throw Error('부품 이름 또는 재질이 올바르지 않습니다.');
 for(const k of ['metalness','roughness','clearcoat'])if(!Number.isFinite(a.material[k])||a.material[k]<0||a.material[k]>1)throw Error('재질 수치가 올바르지 않습니다.');
 if(a.material.finish!==undefined&&!['none','paint','brushed','carbon','fabric'].includes(a.material.finish))throw Error('표면 마감 설정이 올바르지 않습니다.');for(const key of ['envMapIntensity','normalStrength'])if(a.material[key]!==undefined&&(!Number.isFinite(a.material[key])||a.material[key]<0||a.material[key]>3))throw Error('표면 반사·요철 설정이 올바르지 않습니다.');
 if(a.material.texture&&!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(a.material.texture))throw Error('재질 이미지는 PNG/JPEG/WebP만 지원합니다.');
 if(!Array.isArray(a.anchors)||a.anchors.length>200||a.anchors.some(v=>!finiteVec(v.point,-100,100)))throw Error('연결점 데이터가 올바르지 않습니다.');
 if(a.vertices){if(!Array.isArray(a.vertices)||a.vertices.length%3||a.vertices.length>300000||!a.vertices.every(x=>Number.isFinite(x)&&Math.abs(x)<100))throw Error('편집 형상이 올바르지 않습니다.');vertices+=a.vertices.length/3;}
 if(a.colors&&(!a.vertices||a.colors.length!==a.vertices.length||!a.colors.every(x=>Number.isFinite(x)&&x>=0&&x<=1)))throw Error('브러시 색상이 올바르지 않습니다.');
 a.perf=a.perf||{};for(const [k,v]of Object.entries(a.perf)){if(Array.isArray(v)){if(k!=='ratios'||!v.length||v.length>12||!v.every(x=>Number.isFinite(x)&&x>.01&&x<100))throw Error('기어비가 올바르지 않습니다.');}else if(!Number.isFinite(v)||v<0||v>1e7)throw Error('성능 수치가 올바르지 않습니다.');}
 if(a.shape==='body'){if(a.bodyShellVersion===undefined)a.bodyShellVersion=a.vertices?1:2;if(![1,2].includes(a.bodyShellVersion))throw Error('차체 형상 버전이 올바르지 않습니다.');}
 if(a.physicsFixed!==undefined&&typeof a.physicsFixed!=='boolean')throw Error('위치 고정 설정이 올바르지 않습니다.');
 if(a.surface)validateSurface(a.surface);if(a.hinge)validateHinge(a.hinge,a.parentId);
 if(a.connection!=null){const j=a.connection;if(!j||j.version!==1||!['weld','bolt','insert','hinge'].includes(j.kind)||j.parentId!==a.parentId||!a.parentId||!finiteVec(j.childPoint,-100,100)||!finiteVec(j.parentPoint,-100,100)||!finiteVec(j.parentNormal,-1,1)||j.parentNormal.reduce((sum,v)=>sum+v*v,0)<.01)throw Error('체결 관계가 올바르지 않습니다.');a.connection={version:1,kind:j.kind,parentId:j.parentId,childPoint:j.childPoint,parentPoint:j.parentPoint,parentNormal:j.parentNormal,...(j.surfaceUnion===true?{surfaceUnion:true}:{})};}
 a.resolution=clamp(Math.round(a.resolution||16),8,24);
 }
 if(vertices>10000000)throw Error('프로젝트 정점 수가 너무 많습니다.');
 if(p.rootId&&!ids.has(p.rootId))throw Error('주구조 연결이 올바르지 않습니다.');
 for(const a of p.parts){if(a.parentId&&!ids.has(a.parentId))throw Error('장착 대상이 없습니다.');let q=a,seen=new Set([a.id]);while(q.parentId){if(seen.has(q.parentId))throw Error('순환 장착 관계가 있습니다.');seen.add(q.parentId);q=p.parts.find(x=>x.id===q.parentId);}}
 if(!p.aero||!Number.isFinite(p.aero.cd)||p.aero.cd<.01||p.aero.cd>3||!Number.isFinite(p.aero.area)||p.aero.area<.1||p.aero.area>100)throw Error('공기역학 설정이 올바르지 않습니다.');
 if(p.fitAllowances!==undefined&&(!p.fitAllowances||Array.isArray(p.fitAllowances)||typeof p.fitAllowances!=='object'||Object.keys(p.fitAllowances).length>10000||Object.values(p.fitAllowances).some(v=>typeof v!=='string'||v.length>1000)))throw Error('간섭 허용 기록이 올바르지 않습니다.');
 p.fitAllowances=p.fitAllowances||{};
 p.nextId=Math.max(Number.isInteger(p.nextId)?p.nextId:1,...p.parts.map(x=>Number(x.id.split('-')[1])+1||1));return p;
}
