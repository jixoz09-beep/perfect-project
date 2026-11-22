import {MAX_PARTS} from 'precision';
/* Engineering building blocks. Dimensions are mm; forces/performance explicitly labelled. */
const n=(label,value,min=.1,max=2000,step=.1)=>({label,value,min,max,step});
const f=(name,en,shape,params,material='aluminum',mass=1)=>({name,en,shape,params,material,mass});
export const FEATURES={
 profile:f('단면 스케치','Profile sketch','profile',{depth:n('돌출 깊이 mm',8),bevel:n('모서리 가공 mm',0,0,5)},'steel',1),
 block:f('실린더 블록','Cylinder block','block',{cylinders:n('실린더 수',4,1,12,1),bore:n('라이너 자리 지름 mm',90.5),pitch:n('실린더 간격 mm',106),height:n('블록 높이 mm',180),wall:n('외벽 여유 mm',18)},'aluminum',24),
 liner:f('실린더 라이너','Cylinder liner','tube',{outerD:n('외경 mm',90),innerD:n('보어 mm',86),length:n('길이 mm',140)},'steel',1.5),
 piston:f('피스톤','Piston','piston',{diameter:n('지름 mm',85.4),height:n('높이 mm',55),wall:n('스커트 두께 mm',3),crown:n('크라운 두께 mm',6),grooves:n('링 홈 개수',3,0,5,1)},'aluminum',.45),
 ring:f('피스톤 링','Piston ring','ring',{outerD:n('외경 mm',85.5),innerD:n('내경 mm',80),width:n('두께 mm',1.5)},'steel',.03),
 conrod:f('커넥팅 로드','Connecting rod','conrod',{length:n('중심 간 거리 mm',140),bigD:n('빅엔드 구멍 mm',52),smallD:n('스몰엔드 구멍 mm',22),width:n('몸통 폭 mm',22),depth:n('두께 mm',18)},'steel',.6),
 crank:f('크랭크축','Crankshaft','crank',{cylinders:n('크랭크 핀 개수',4,1,12,1),stroke:n('행정 mm',86),pitch:n('핀 간격 mm',106),journalD:n('메인 저널 지름 mm',55),pinD:n('크랭크 핀 지름 mm',48)},'steel',13),
 head:f('실린더 헤드','Cylinder head','head',{cylinders:n('연소실 개수',4,1,12,1),pitch:n('연소실 간격 mm',106),width:n('헤드 폭 mm',140),height:n('높이 mm',65),valveD:n('밸브 통로 지름 mm',28)},'aluminum',12),
 cam:f('캠축','Camshaft','cam',{length:n('길이 mm',420),diameter:n('저널 지름 mm',25),lobes:n('캠 개수',8,1,32,1),lift:n('캠 리프트 mm',8)},'steel',2.5),
 valve:f('흡배기 밸브','Valve','valve',{headD:n('밸브 헤드 지름 mm',28),stemD:n('스템 지름 mm',6),length:n('길이 mm',100)},'steel',.08),
 spring:f('코일 스프링','Coil spring','spring',{diameter:n('평균 코일 지름 mm',70),wire:n('와이어 지름 mm',9),length:n('자유 길이 mm',280),coils:n('유효 권수',7,2,24,.5),shear:n('전단 탄성계수 N/mm²',79000,1000,100000,100)},'steel',3),
 plug:f('점화 플러그','Spark plug','plug',{diameter:n('나사부 지름 mm',14),length:n('길이 mm',65)},'steel',.06),
 shaft:f('단차 축','Stepped shaft','shaft',{length:n('길이 mm',300),diameter:n('몸통 지름 mm',30),journalD:n('끝단 지름 mm',22),journalLength:n('끝단 길이 mm',45)},'steel',2),
 gear:f('평기어','Spur gear','gear',{teeth:n('잇수',32,8,128,1),module:n('모듈 mm',2,.3,8,.1),width:n('치폭 mm',18),bore:n('축 구멍 mm',22),stage:n('기어단 번호',1,1,8,1),driven:n('구동측 0 / 종동측 1',0,0,1,1)},'steel',.6),
 bevel:f('베벨 기어','Bevel gear','bevel',{teeth:n('잇수',24,8,96,1),module:n('모듈 mm',2,.3,8),width:n('치폭 mm',20),bore:n('축 구멍 mm',22),taper:n('끝단 지름 비율',.65,.2,1,.05)},'steel',.6),
 bearing:f('베어링','Bearing','bearing',{outerD:n('외경 mm',62),innerD:n('내경 mm',30),width:n('폭 mm',16),balls:n('볼 개수',12,6,32,1)},'steel',.2),
 housing:f('열린 하우징','Open housing','housing',{width:n('폭 mm',220),height:n('높이 mm',180),depth:n('깊이 mm',200),wall:n('벽 두께 mm',6)},'aluminum',4),
 rim:f('휠 림','Wheel rim','rim',{diameter:n('비드 지름 mm',381),width:n('림 폭 mm',180),spokes:n('스포크 수',7,3,20,1),hubD:n('중심 구멍 mm',65),wall:n('림 두께 mm',5)},'aluminum',7),
 tyre:f('타이어','Tyre','tyre',{outerD:n('외경 mm',630),innerD:n('비드 내경 mm',381.5),width:n('폭 mm',205),grip:n('노면 마찰계수',1.05,.1,3,.01),rolling:n('구름저항계수',.013,.001,.1,.001)},'rubber',9),
 hub:f('허브 플랜지','Hub flange','hub',{diameter:n('플랜지 지름 mm',125),bore:n('중심 구멍 mm',30),width:n('폭 mm',25),boltCircle:n('볼트 원 지름 mm',100),holes:n('체결 구멍 수',5,3,12,1)},'steel',2),
 disc:f('브레이크 디스크','Brake disc','disc',{outerD:n('외경 mm',300),innerD:n('중심 구멍 mm',65),width:n('두께 mm',22),vents:n('통풍 구멍 수',16,0,48,1)},'steel',5),
 caliper:f('캘리퍼 몸체','Caliper body','caliper',{width:n('폭 mm',130),height:n('높이 mm',95),depth:n('깊이 mm',90),gap:n('디스크 통과 폭 mm',35),wall:n('벽 두께 mm',15)},'aluminum',2),
 brake_piston:f('캘리퍼 피스톤','Caliper piston','piston',{diameter:n('지름 mm',42),height:n('높이 mm',35),wall:n('벽 두께 mm',4),crown:n('바닥 두께 mm',5),grooves:n('홈 개수',1,0,5,1)},'steel',.2),
 pad:f('브레이크 패드','Brake pad','plate',{width:n('폭 mm',105),height:n('높이 mm',55),depth:n('두께 mm',12),friction:n('패드 마찰계수',.4,.1,1,.01)},'carbon',.25),
 damper_case:f('댐퍼 실린더','Damper cylinder','tube',{outerD:n('외경 mm',45),innerD:n('내경 mm',36),length:n('길이 mm',300)},'steel',1.4),
 damper_rod:f('댐퍼 로드','Damper rod','shaft',{length:n('길이 mm',250),diameter:n('로드 지름 mm',20),journalD:n('끝단 지름 mm',16),journalLength:n('끝단 길이 mm',25)},'steel',.7),
 arm:f('컨트롤 암','Control arm','arm',{length:n('길이 mm',350),width:n('폭 mm',260),depth:n('두께 mm',20),hole:n('부싱 구멍 mm',28)},'steel',2),
 rack:f('랙 기어','Steering rack','rack',{length:n('길이 mm',1000),diameter:n('몸통 지름 mm',28),teeth:n('랙 잇수',35,8,80,1)},'steel',3),
 tie_rod:f('타이 로드','Tie rod','shaft',{length:n('길이 mm',330),diameter:n('몸통 지름 mm',14),journalD:n('조인트 지름 mm',22),journalLength:n('조인트 길이 mm',25)},'steel',.7),
 stator:f('모터 고정자','Motor stator','stator',{outerD:n('외경 mm',240),innerD:n('회전자 공간 mm',150),length:n('길이 mm',180),slots:n('슬롯 수',24,6,72,1)},'steel',12),
 rotor:f('모터 회전자','Motor rotor','rotor',{diameter:n('지름 mm',148),length:n('길이 mm',180),shaftD:n('축 지름 mm',35),magnets:n('자석 수',8,2,24,1)},'steel',8),
 winding:f('고정자 권선','Stator winding','winding',{diameter:n('배치 지름 mm',185),length:n('권선 길이 mm',190),slots:n('코일 수',24,3,72,1),wire:n('묶음 두께 mm',8)},'copper',4),
 cell:f('원통형 배터리 셀','Battery cell','cell',{diameter:n('지름 mm',21),length:n('길이 mm',70),voltage:n('정격 전압 V',3.2,.5,5,.1),capacity:n('용량 Ah',5,.1,100,.1)},'aluminum',.07),
 busbar:f('버스바','Busbar','plate',{width:n('길이 mm',100),height:n('폭 mm',15),depth:n('두께 mm',2)},'copper',.08),
 pipe:f('직선 파이프','Pipe','tube',{outerD:n('외경 mm',45),innerD:n('내경 mm',40),length:n('길이 mm',400)},'steel',1),
 bend_pipe:f('곡선 파이프','Bent pipe','bend_pipe',{diameter:n('외경 mm',45),wall:n('벽 두께 mm',2),radius:n('굽힘 반경 mm',120),angle:n('굽힘 각도 °',90,10,180,1)},'steel',.7),
 radiator_core:f('라디에이터 코어','Radiator core','radiator',{width:n('폭 mm',600),height:n('높이 mm',400),depth:n('두께 mm',30),fins:n('핀 개수',28,6,80,1)},'aluminum',4),
 impeller:f('펌프 임펠러','Pump impeller','impeller',{diameter:n('외경 mm',90),width:n('폭 mm',20),blades:n('블레이드 수',8,3,24,1),bore:n('축 구멍 mm',15)},'aluminum',.4),
 panel:f('판재','Sheet panel','plate',{width:n('폭 mm',500),height:n('높이 mm',300),depth:n('두께 mm',2)},'steel',2),
 beam:f('구조 빔','Structural beam','beam',{length:n('길이 mm',1000),width:n('단면 폭 mm',60),height:n('단면 높이 mm',40),wall:n('벽 두께 mm',3)},'steel',4),
 tank_shell:f('탱크 반쪽 셸','Tank half shell','housing',{width:n('폭 mm',650),height:n('높이 mm',140),depth:n('깊이 mm',450),wall:n('벽 두께 mm',3)},'plastic',4)
};
const req=(feature,count=1)=>({feature,count});
const kit=(name,en,role,requirements,params={})=>({name,en,role,requirements:requirements.map(x=>Array.isArray(x)?req(...x):req(x)),params});
export const KITS={
 custom:kit('자유 설계 부품','Custom fabricated part','custom',[]),
 engine:kit('엔진','Engine','engine',['block',['liner',4],['piston',4],['conrod',4],'crank','head','cam',['valve',8]],{cylinders:n('목표 실린더 수',4,1,12,1),bmep:n('가정 평균유효압력 bar',10,1,35,.1),rpm:n('설계 회전수 rpm',5000,500,18000,100)}),
 wheel:kit('타이어·휠','Wheel assembly','wheel',['rim','tyre','hub']),
 transmission:kit('변속기','Gearbox','transmission',['housing',['shaft',2],['gear',2],['bearing',2]],{finalDrive:n('종감속비',3.9,.2,15,.01),efficiency:n('전달 효율',.92,.1,1,.01)}),
 differential:kit('차동장치','Differential','differential',['housing',['bevel',4],['shaft',2],['bearing',2]],{finalDrive:n('종감속비',3.9,.2,15,.01)}),
 brake:kit('브레이크','Brake assembly','brake',['disc','caliper',['brake_piston',2],['pad',2]],{clamp:n('양쪽 패드 합산 압착력 N',14000,100,100000,100)}),
 suspension:kit('현가장치','Suspension','suspension',['spring','damper_case','damper_rod','arm'],{travel:n('설계 작동거리 mm',160,10,600,5)}),
 steering:kit('조향장치','Steering assembly','steering',['rack','gear',['tie_rod',2]],{angle:n('최대 조향각 °',32,5,65,1)}),
 motor:kit('전기모터','Electric motor','motor',['stator','rotor','winding',['bearing',2]],{voltage:n('공급 전압 V',400,12,1500,1),current:n('가정 전류 A',400,1,2000,1),efficiency:n('가정 효율',.92,.1,1,.01),rpm:n('설계 회전수 rpm',6000,500,20000,100)}),
 battery:kit('배터리 팩','Battery pack','battery',['housing',['cell',4],['busbar',2]],{series:n('직렬 셀 수',4,1,200,1),parallel:n('병렬 셀 수',1,1,100,1),maxPower:n('설계 공급 한도 kW',40,1,1000,1)}),
 radiator:kit('라디에이터','Radiator','radiator',['radiator_core',['pipe',2]],{cooling:n('설계 열 제거량 kW',80,1,500,1)}),
 pump:kit('냉각 펌프','Coolant pump','pump',['housing','impeller','shaft','bearing'],{flow:n('설계 유량 L/min',45,1,500,1)}),
 exhaust:kit('흡배기 배관','Intake / exhaust','exhaust',['pipe','bend_pipe']),
 turbo:kit('터보차저','Turbocharger','turbo',['housing',['impeller',2],'shaft',['bearing',2]],{boost:n('목표 과급압 bar',1.2,0,5,.1)}),
 fuel:kit('연료 탱크·공급','Fuel system','fuel',[['tank_shell',2],'pipe'],{litres:n('설계 연료량 L',45,1,200,1)}),
 shaft:kit('구동축','Driveshaft','shaft',['shaft',['bearing',2]]),
 frame:kit('프레임','Frame','frame',[['beam',6]]),
 shell:kit('차체 구조','Body structure','shell',[['panel',4],['beam',6]]),
 steeringwheel:kit('스티어링 휠','Steering wheel','steeringwheel',['rim','hub'])
};
export const DIRECT_FEATURE={custom:'profile',panel:'panel',floor:'panel',door:'panel',glass:'panel',wing:'profile',beam:'beam',tube:'pipe',controlarm:'arm',hub:'hub'};
export function defaultFabrication(type='profile'){
 const f=FEATURES[type];if(!f)throw Error('지원하지 않는 소요소입니다.');
 return {version:1,type,params:Object.fromEntries(Object.entries(f.params).map(([k,p])=>[k,p.value])),operation:'extrude',profile:[[-60,-40],[60,-40],[60,40],[-60,40]],holes:[]};
}
export function defaultKitParams(kind){return Object.fromEntries(Object.entries(KITS[kind]?.params||{}).map(([k,v])=>[k,v.value]));}
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
export function pointInPolygon(p,poly){let yes=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if(((a[1]>p[1])!==(b[1]>p[1]))&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
export function validateFabrication(raw){
 if(!raw||raw.version!==1||!FEATURES[raw.type])throw Error('가공 형식이 올바르지 않습니다.');
 const f=JSON.parse(JSON.stringify(raw)),schema=FEATURES[f.type].params;
 for(const [key,s]of Object.entries(schema)){const v=f.params?.[key];if(!Number.isFinite(v)||v<s.min||v>s.max||(s.step===1&&!Number.isInteger(v)))throw Error(s.label+' 값을 확인하세요.');}
 const p=f.params;if(p.wall!==undefined&&p.diameter!==undefined&&p.wall*2>=p.diameter)throw Error('벽 두께가 지름보다 큽니다.');if(p.crown!==undefined&&p.crown>=p.height)throw Error('크라운 두께를 높이보다 작게 지정하세요.');if(['housing','tank_shell','beam'].includes(f.type)&&p.wall*2>=Math.min(p.width,p.height,p.depth||Infinity))throw Error('벽 두께를 외형 치수보다 작게 지정하세요.');if(f.type==='bend_pipe'&&p.wall*2>=p.diameter)throw Error('파이프 벽 두께를 확인하세요.');if(p.innerD!==undefined&&p.outerD!==undefined&&p.innerD>=p.outerD)throw Error('내경은 외경보다 작아야 합니다.');
 if(f.type==='block'&&p.pitch<p.bore+2)throw Error('실린더 간격을 보어보다 크게 지정하세요.');
 if(f.type==='gear'&&p.bore>=(p.teeth-2.5)*p.module)throw Error('축 구멍이 기어의 뿌리 지름보다 큽니다.');
 if(f.type==='profile'){
  if(!['extrude','revolve'].includes(f.operation)||!Array.isArray(f.profile)||f.profile.length<3||f.profile.length>128||f.profile.some(p=>!Array.isArray(p)||p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>10000)))throw Error('단면에 유효한 점 3~128개가 필요합니다.');
  let area=0;for(let i=0;i<f.profile.length;i++){const a=f.profile[i],b=f.profile[(i+1)%f.profile.length];area+=a[0]*b[1]-b[0]*a[1];}if(Math.abs(area)<.01)throw Error('단면의 면적이 너무 작습니다.');
  for(let i=0;i<f.profile.length;i++)for(let j=i+2;j<f.profile.length;j++){if(i===0&&j===f.profile.length-1)continue;const a=f.profile[i],b=f.profile[(i+1)%f.profile.length],c=f.profile[j],d=f.profile[(j+1)%f.profile.length];if(cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)throw Error('단면 선이 서로 교차합니다.');}
  if(f.operation==='revolve'&&f.profile.some(p=>p[0]<0))throw Error('회전 단면의 X는 반지름입니다. 0 이상으로 지정하세요.');
  if(!Array.isArray(f.holes)||f.holes.length>24)throw Error('구멍은 24개까지 지정하세요.');
  if(f.operation==='revolve'&&f.holes.length)throw Error('회전체의 빈 내부는 회전 단면에 내측 경로로 그리세요.');
  for(const h of f.holes){if(!['circle','rect'].includes(h.kind)||![h.x,h.y,h.size,h.height??h.size].every(Number.isFinite)||h.size<=0||h.size>5000||(h.height??h.size)<=0)throw Error('구멍 치수를 확인하세요.');const points=h.kind==='circle'?Array.from({length:32},(_,i)=>[h.x+Math.cos(i*Math.PI/16)*h.size/2,h.y+Math.sin(i*Math.PI/16)*h.size/2]):[[-1,-1],[-1,1],[1,1],[1,-1]].map(([x,y])=>[h.x+x*h.size/2,h.y+y*(h.height??h.size)/2]);if(points.some(p=>!pointInPolygon(p,f.profile)))throw Error('구멍이 단면 바깥으로 나갑니다.');}
 }
 return {version:1,type:f.type,params:Object.fromEntries(Object.keys(schema).map(k=>[k,f.params[k]])),operation:f.operation||'extrude',profile:Array.isArray(f.profile)?f.profile:[],holes:Array.isArray(f.holes)?f.holes:[]};
}
export function requirements(kind,params={}){const rows=(KITS[kind]?.requirements||[]).map(r=>({...r}));if(kind==='engine'){const n=params.cylinders||4;for(const r of rows)if(['liner','piston','conrod'].includes(r.feature))r.count=n;else if(r.feature==='valve')r.count=n*2;}if(kind==='battery')rows.find(r=>r.feature==='cell').count=(params.series||4)*(params.parallel||1);return rows;}
export function inspectAssembly(kind,parts,params={}){
 const counts={};for(const p of parts){const key=p.mechanicalRole||p.fabrication?.type;if(key)counts[key]=(counts[key]||0)+1;}
 const checks=requirements(kind,params).map(r=>({...r,actual:counts[r.feature]||0,ok:(counts[r.feature]||0)>=r.count}));
 const perf={},notes=[],feature=t=>parts.filter(p=>(p.mechanicalRole||p.fabrication?.type)===t),P=t=>{const a=feature(t)[0];return a?.roleParameters||a?.fabrication?.params;};
 if(kind==='engine'){
  const bore=P('liner')?.innerD||0,stroke=P('crank')?.stroke||0,cylinders=counts.piston||0,litres=Math.PI*bore*bore/4*stroke*cylinders/1e6;
  Object.assign(perf,{cylinders,displacement:litres,torque:(params.bmep||10)*1e5*litres/1000/(4*Math.PI),peakRpm:params.rpm||5000,redline:(params.rpm||5000)*1.3,idle:850,efficiency:.3});
  if(P('block')&&P('block').cylinders!==(params.cylinders||4))notes.push('블록의 실린더 수와 목표 개수가 다릅니다.');
  if(P('piston')&&bore&&P('piston').diameter>=bore)notes.push('피스톤 지름이 실린더 보어보다 작아야 합니다.');
  if(P('block')&&P('liner')&&P('liner').outerD>=P('block').bore)notes.push('라이너 외경과 블록 자리의 조립 여유를 확인하세요.');
 }else if(kind==='wheel'){
  Object.assign(perf,{grip:P('tyre')?.grip||1,rolling:P('tyre')?.rolling||.013});if(P('rim')&&P('tyre')&&Math.abs(P('rim').diameter-P('tyre').innerD)>5)notes.push('타이어 비드와 림 지름이 맞지 않습니다.');
 }else if(kind==='transmission'){
  const stages=new Map();for(const p of feature('gear')){const v=p.roleParameters||p.fabrication.params,g=stages.get(v.stage)||{};g[v.driven?'driven':'driver']=v.teeth;stages.set(v.stage,g);}const ratios=[...stages.entries()].sort((a,b)=>a[0]-b[0]).filter(([,v])=>v.driver&&v.driven).map(([,v])=>v.driven/v.driver);
  Object.assign(perf,{ratios:ratios.length?ratios:[1],finalDrive:params.finalDrive||3.9,efficiency:params.efficiency||.92});if(!ratios.length)notes.push('동일한 단 번호에 구동·종동 기어를 한 쌍 이상 지정하세요.');
 }else if(kind==='brake'){const mu=P('pad')?.friction||.4,r=(P('disc')?.outerD||0)/2000*.75;perf.brakeTorque=mu*(params.clamp||14000)*r;}
 else if(kind==='suspension'){const v=P('spring');perf.springRate=v?v.shear*v.wire**4/(8*v.diameter**3*v.coils):0;perf.travel=(params.travel||160)/1000;}
 else if(kind==='motor'){const rpm=params.rpm||6000,power=(params.voltage||400)*(params.current||400)*(params.efficiency||.92)/1000;Object.assign(perf,{power,torque:power*30000/(Math.PI*rpm),peakRpm:rpm,redline:rpm*2,efficiency:params.efficiency||.92});}
 else if(kind==='battery'){const v=P('cell');Object.assign(perf,{capacity:(params.series||4)*(params.parallel||1)*(v?.voltage||3.2)*(v?.capacity||5)/1000,voltage:(params.series||4)*(v?.voltage||3.2),maxPower:params.maxPower||40});}
 else if(kind==='steering')perf.steerAngle=params.angle||32;
 else if(kind==='differential')perf.finalDrive=params.finalDrive||3.9;
 else if(kind==='radiator')perf.cooling=params.cooling||80;
 else if(kind==='pump')perf.flow=params.flow||45;
 else if(kind==='turbo')perf.boost=params.boost||1.2;
 else if(kind==='fuel')perf.litres=params.litres||45;
 return {counts,checks,notes,perf,ready:parts.length>0&&checks.every(c=>c.ok)&&!notes.length,mass:parts.reduce((sum,p)=>sum+p.mass,0)};
}
export function validateManufacturedPart(p,depth=0,budget={count:0}){
 if(depth>4||++budget.count>MAX_PARTS*10)throw Error('중첩 조립품의 단계 또는 개수가 너무 많습니다.');
 if(p.fabrication)p.fabrication=validateFabrication(p.fabrication);if(p.mechanicalRole&&!FEATURES[p.mechanicalRole])throw Error('소요소 역할이 올바르지 않습니다.');if(p.roleParameters){if(!FEATURES[p.mechanicalRole])throw Error('기능 역할을 먼저 지정하세요.');for(const [k,v]of Object.entries(FEATURES[p.mechanicalRole].params)){const n=p.roleParameters[k];if(!Number.isFinite(n)||n<v.min||n>v.max||(v.step===1&&!Number.isInteger(n)))throw Error('기능 설계값이 올바르지 않습니다.');}}
 if(p.subassembly){const c=p.subassembly;if(c.version!==1||!KITS[c.kind]||!Array.isArray(c.parts)||!c.parts.length||c.parts.length>MAX_PARTS)throw Error('소부품 조립 데이터가 올바르지 않습니다.');for(const a of c.parts){if(!a||!Array.isArray(a.size)||a.size.length!==3||a.size.some(v=>!Number.isFinite(v)||v<=0||v>100)||!Array.isArray(a.position)||a.position.length!==3||a.position.some(v=>!Number.isFinite(v)||Math.abs(v)>10000)||!Array.isArray(a.rotation)||a.rotation.length!==3||a.rotation.some(v=>!Number.isFinite(v))||!a.material||!/^#[0-9a-f]{6}$/i.test(a.material.color))throw Error('조립 소요소의 형상 수치가 올바르지 않습니다.');validateManufacturedPart(a,depth+1,budget);}}
}
export function validateWorkshops(root,validateProject){
 const budget={count:0};root.parts.forEach(p=>validateManufacturedPart(p,0,budget));const verifyNested=p=>{if(p.subassembly){const c=p.subassembly;validateProject({format:'AUTOVERSE_WORKSHOP',version:2,parts:c.parts,fitAllowances:c.fitAllowances||{},rootId:c.rootId||c.parts[0]?.id,nextId:1,aero:{cd:.32,area:2.1}});for(const a of c.parts)verifyNested(a);for(const [k,v]of Object.entries(KITS[c.kind].params)){const n=c.params?.[k];if(!Number.isFinite(n)||n<v.min||n>v.max)throw Error('조립품 설계값이 올바르지 않습니다.');}}};root.parts.forEach(verifyNested);const w=root.workshops;if(!w)return root;
 if(w.version!==1||!Array.isArray(w.labs)||w.labs.length>32||!Array.isArray(w.library)||w.library.length>100)throw Error('작업실 저장 형식이 올바르지 않습니다.');
 const ids=new Set();for(const l of w.labs){if(typeof l.id!=='string'||!/^lab-[0-9]+$/.test(l.id)||ids.has(l.id)||!KITS[l.kind]||l.project?.workshops)throw Error('소부품 작업실 참조가 올바르지 않습니다.');ids.add(l.id);l.project=validateProject(l.project);l.project.parts.forEach(p=>validateManufacturedPart(p,0,budget));l.project.parts.forEach(verifyNested);for(const [k,v]of Object.entries(KITS[l.kind].params)){const n=l.params?.[k];if(!Number.isFinite(n)||n<v.min||n>v.max)throw Error('작업실 설계값이 올바르지 않습니다.');}}
 for(const l of w.labs){if(l.targetWorkspace&&l.targetWorkspace!=='main'&&(!ids.has(l.targetWorkspace)||l.targetWorkspace===l.id))throw Error('원본 작업실 연결이 올바르지 않습니다.');if(l.targetPartId!==undefined&&l.targetPartId!==null&&(typeof l.targetPartId!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(l.targetPartId)))throw Error('원본 부품 참조가 올바르지 않습니다.');if(l.originRole&&!Object.hasOwn(DIRECT_FEATURE,l.originRole))throw Error('부품 역할이 올바르지 않습니다.');}
 for(const item of w.library){if(!item||typeof item.id!=='string'||!KITS[item.kind]||!item.part)throw Error('제작품 목록이 올바르지 않습니다.');validateProject({format:'AUTOVERSE_WORKSHOP',version:2,parts:[{...item.part,parentId:null}],rootId:item.part.id,nextId:1,aero:{cd:.32,area:2.1}});validateManufacturedPart(item.part,0,budget);verifyNested(item.part);}
 if(w.drafts!==undefined){if(!w.drafts||typeof w.drafts!=='object'||Array.isArray(w.drafts)||Object.keys(w.drafts).length>2000)throw Error('단면 초안 저장 형식이 올바르지 않습니다.');const clean={};for(const [key,d]of Object.entries(w.drafts)){if(!/^(main|lab-[0-9]+):(new|part-[0-9]+)$/.test(key)||!d||d.version!==1||!FEATURES[d.type]||!['extrude','revolve'].includes(d.operation)||!Array.isArray(d.profile)||d.profile.length>128||d.profile.some(p=>!Array.isArray(p)||p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>10000))||!Array.isArray(d.holes)||d.holes.length>24)throw Error('단면 초안 데이터가 올바르지 않습니다.');const numeric=(values,schema)=>{const out={};for(const k of Object.keys(schema)){const v=values?.[k];if(!Number.isFinite(v)||Math.abs(v)>1e8)throw Error('단면 초안의 수치가 올바르지 않습니다.');out[k]=v;}return out;};const holes=d.holes.map(h=>{if(!h||!['circle','rect'].includes(h.kind)||![h.x,h.y,h.size,h.height??h.size].every(v=>Number.isFinite(v)&&Math.abs(v)<=10000))throw Error('단면 초안의 구멍 데이터가 올바르지 않습니다.');return {kind:h.kind,x:h.x,y:h.y,size:h.size,...(h.kind==='rect'?{height:h.height??h.size}:{})};});const role=d.assignedRole||d.type;if(!FEATURES[role])throw Error('단면 초안의 역할이 올바르지 않습니다.');clean[key]={version:1,type:d.type,operation:d.operation,profile:d.profile,holes,params:numeric(d.params,FEATURES[d.type].params),assignedRole:role,...(d.functionValues?{functionValues:numeric(d.functionValues,FEATURES[role].params)}:{})};}w.drafts=clean;}
 w.nextLab=Math.max(Number.isInteger(w.nextLab)?w.nextLab:1,...w.labs.map(l=>Number(l.id.split('-')[1])+1));return root;
}
