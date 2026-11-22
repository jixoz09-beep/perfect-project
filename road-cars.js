/* Independently constructed reference models. Dimensions and styling references
 * are recorded in each entry; these are not OEM CAD or photogrammetry assets. */
import * as T from 'three';
import {vehicleProxy,batchVehicleGroup} from 'vehicle-lod';
import {PHOTO_PROFILES,buildPhotoBody} from 'photo-body';
import {buildActyonReference} from 'actyon-reference';
import {REFERENCE_SPECS} from 'reference-specs';
import {emptyProject,newPart} from 'core';
export const CAR_SPECS=[
 {id:'avante-2026',name:'아반떼',year:2026,generation:'제공 사진 기준 아반떼',L:4.710,W:1.825,H:1.420,WB:2.720,r:.318,seats:5,power:91,mass:1270,color:'#a2aeba',type:'sedan',dash:'avante',cab:[-.39,-.21,.16,.29],source:'https://www.hyundai.com/contents/repn-car/catalog/avante-hybrid-2026-price.pdf'},
 {id:'grandeur-2026',name:'그랜저',year:2026,generation:'지엔7',L:5.035,W:1.880,H:1.460,WB:2.895,r:.350,seats:5,power:146,mass:1620,color:'#171d23',type:'sedan',dash:'grandeur',cab:[-.36,-.23,.15,.28],source:'https://ownersmanual.hyundai.com/full_webhelp/GN7/2026/ko_KR/id6db2d9a179c.html'},
 {id:'wrangler-2024',name:'지프 랭글러',year:2024,generation:'제이엘 · 4도어 하드톱',L:4.885,W:1.895,H:1.840,WB:3.008,r:.410,seats:5,power:200,mass:2040,color:'#75816b',type:'jeep',dash:'wrangler',cab:[-.39,-.36,.15,.19],source:'https://www.jeep.co.kr/jeep_life/news_media1/posts/post_240103.html'},
 {id:'carnival-yp',name:'카니발',year:null,generation:'와이피 · 제공 사진 기준 7인승',L:5.155,W:1.995,H:1.775,WB:3.090,r:.365,seats:7,power:216,mass:2100,color:'#d2d3cc',type:'van',dash:'carnival',cab:[-.43,-.38,.18,.32],source:'https://www.kia.com/kr/vehicles/carnival/specification'},
 {id:'equus-2015',name:'에쿠스',year:2015,generation:'브이아이 · 후기형',L:5.160,W:1.900,H:1.495,WB:3.045,r:.360,seats:5,power:246,mass:1925,color:'#20202a',type:'sedan',dash:'equus',cab:[-.35,-.22,.14,.29],source:'https://www.hyundai.com/kr/ko/brand/brandstory/model/equus-history/2009-equus-vi'},
 {id:'actyon-2009',name:'액티언',year:2009,generation:'쌍용 · 1세대 에스유브이',L:4.455,W:1.880,H:1.740,WB:2.740,r:.365,seats:5,power:104,mass:1780,color:'#496571',type:'actyon',dash:'actyon',cab:[-.42,-.21,.12,.30],source:'https://3sun.tistory.com/868'},
 {id:'sorento-2025',name:'쏘렌토',year:2025,generation:'엠큐4 · 부분변경',L:4.815,W:1.900,H:1.695,WB:2.815,r:.365,seats:7,power:148,mass:1785,color:'#687b70',type:'suv',dash:'sorento',cab:[-.43,-.35,.13,.30],source:'https://www.kia.com/kr/vehicles/sorento/specification'},
 {id:'spark-2015',name:'스파크',year:2015,generation:'쉐보레 스파크 · 엠300',L:3.595,W:1.595,H:1.520,WB:2.375,r:.2895,seats:5,power:55,mass:910,color:'#a9d0e3',type:'hatch',dash:'spark',cab:[-.44,-.33,.12,.30],source:'사용자 제공 2015 쉐보레 스파크 사진·제원'},
 {id:'damas-2019',name:'다마스',year:2019,generation:'뉴 다마스 · 5인승',L:3.485,W:1.400,H:1.920,WB:1.840,r:.280,seats:5,power:30,mass:930,color:'#c4d6dc',type:'microvan',dash:'damas',cab:[-.46,-.43,.34,.46],source:'https://www.gm-korea.co.kr/'},
 {id:'camaro-2021',name:'카마로',year:2021,generation:'6세대 부분변경 · 에스에스 쿠페',L:4.784,W:1.897,H:1.348,WB:2.812,r:.355,seats:4,power:339,mass:1715,color:'#e3bb33',type:'coupe',dash:'camaro',cab:[-.32,-.18,.10,.23],source:'https://media.chevrolet.com/content/dam/Media/documents/INTL/chevrolet/2019/vehicles/camaro/Product-Information-Chevrolet-Camaro.pdf'}
];
function tire(s){const m=s.match(/(\d+)\/(\d+)\s*R(\d+)/);return{width:+m[1]/1000,radius:+m[3]*.0254/2+(+m[1])*(+m[2])/100000,rimRadius:+m[3]*.0254/2};}
for(const s of CAR_SPECS){const ref=REFERENCE_SPECS[s.id];if(!ref)continue;const f=tire(ref.selectedTireFront),b=tire(ref.selectedTireRear);Object.assign(s,{referenceSpecifications:ref,source:ref.source,L:ref.lengthMM/1000,W:ref.widthMM/1000,H:ref.heightMM/1000,WB:ref.wheelbaseMM/1000,mass:ref.massKG??ref.simulationMassKG,trackFront:ref.trackFrontMM/1000,trackRear:ref.trackRearMM/1000,tireWidthFront:f.width,tireWidthRear:b.width,rimRadiusFront:f.rimRadius,rimRadiusRear:b.rimRadius,r:f.radius,rRear:b.radius});if(['avante','grandeur','carnival','sorento','camaro','wrangler'].includes(s.dash))s.power=Math.round(parseFloat(ref.powerOriginal)*.7355);}
const specMap=new Map(CAR_SPECS.map(s=>[s.id,s]));
export function getCarSpec(id){return specMap.get(({'spark-2018':'spark-2015','carnival-2025':'carnival-yp','camaro-2018':'camaro-2021'})[id]||id);}
function trainingProject(s){const p=emptyProject();p.name=s.name+' · '+(s.year?s.year+'년형':'제공 사진 기준');p.driveModel=s.id;p.referenceModel=true;p.parts=[];const add=(role,position,size,mass)=>{const a=newPart(role,p);a.position=position;a.size=size;a.mass=mass;p.parts.push(a);if(!p.rootId)p.rootId=a.id;return a;};add('shell',[0,.55,0],[s.L,.6,s.W],s.mass-220);const engine=add('engine',[s.WB*.4,.65,0],[.5,.45,.55],140);engine.perf={...engine.perf,power:s.power};for(const x of [-s.WB/2,s.WB/2])for(const sign of [-1,1])add('wheel',[x,s.r,sign*((x>0?s.trackFront:s.trackRear)??s.W*.88)/2],[s.r*2,s.r*2,.22],15);add('seat',[0,.6,-s.W*.23],[.5,.7,.5],20);return p;}
export const ROAD_FLEET=CAR_SPECS.map(s=>({id:s.id,name:s.name+' · '+(s.year||'제공 사진 기준'),description:s.generation,source:'외관·운전석 재현 모델',spec:s,project:trainingProject(s)}));

export function buildRoadCar(id){
 const s=getCarSpec(id);if(!s)throw new Error('차량 형식이 없습니다.');
 if(s.dash==='actyon')return buildActyonReference(s);
 const root=new T.Group(),exterior=new T.Group(),interior=new T.Group();root.add(exterior,interior);
 const {L,W,H,r,WB}=s;const boxy=['jeep','microvan','van','suv'].includes(s.type);const waist=s.type==='microvan'?.96:H*(boxy?.56:.59),floor=s.type==='microvan'?.46:.29;
 const mats={paint:new T.MeshPhysicalMaterial({color:s.color,metalness:.62,roughness:.27,clearcoat:.85,clearcoatRoughness:.2,side:T.DoubleSide}),glass:new T.MeshPhysicalMaterial({color:'#b8d4df',metalness:.03,roughness:.10,transparent:true,opacity:.30,depthWrite:false,side:T.DoubleSide}),black:new T.MeshStandardMaterial({color:'#151b20',roughness:.65,side:T.DoubleSide}),rubber:new T.MeshStandardMaterial({color:'#202528',roughness:.94}),chrome:new T.MeshStandardMaterial({color:'#bac3c9',metalness:.95,roughness:.24}),rim:new T.MeshStandardMaterial({color:'#969fa7',metalness:.88,roughness:.25}),leather:new T.MeshStandardMaterial({color:['equus','grandeur','carnival'].includes(s.dash)?'#b8ac95':'#343a3e',roughness:.83,side:T.DoubleSide}),dash:new T.MeshStandardMaterial({color:'#272c31',roughness:.8,side:T.DoubleSide}),wood:new T.MeshStandardMaterial({color:'#67432b',roughness:.37}),headlight:new T.MeshStandardMaterial({color:'#eff8ff',emissive:'#c9e7fa',emissiveIntensity:.7}),red:new T.MeshStandardMaterial({color:'#ac1624',emissive:'#b51422',emissiveIntensity:.45}),amber:new T.MeshStandardMaterial({color:'#dfac3a',emissive:'#c68e12',emissiveIntensity:.3})};
 if(s.dash==='equus')mats.leather.color.set('#76665b');if(s.dash==='grandeur'){mats.leather.color.set('#7d4b43');mats.dash.color.set('#5c3833');}if(s.dash==='avante')mats.leather.color.set('#292a2c');if(s.dash==='damas')mats.leather.color.set('#365676');
 const glass=[];let meshes=0;
 function mesh(g,m,parent=exterior,name=''){const o=new T.Mesh(g,m);o.name=name;o.castShadow=true;o.receiveShadow=true;o.geometry.userData.driveKeepDetail=true;vehicleProxy(o.geometry);parent.add(o);meshes++;return o;}
 function rounded(w,h,d,x,y,z,m,parent=exterior,radius=.035){const g=new T.BoxGeometry(w,h,d,2,2,2),a=g.attributes.position,R=Math.min(radius,w/2,h/2,d/2);for(let i=0;i<a.count;i++){const v=new T.Vector3().fromBufferAttribute(a,i),q=new T.Vector3(T.MathUtils.clamp(v.x,-w/2+R,w/2-R),T.MathUtils.clamp(v.y,-h/2+R,h/2-R),T.MathUtils.clamp(v.z,-d/2+R,d/2-R));v.sub(q).normalize().multiplyScalar(R).add(q);a.setXYZ(i,...v.toArray());}g.computeVertexNormals();const o=mesh(g,m,parent);o.position.set(x,y,z);return o;}
 function quad(points,m,parent=exterior,name=''){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(points.flat(),3));g.setIndex([0,1,2,0,2,3]);g.computeVertexNormals();return mesh(g,m,parent,name);}
 function pipe(points,radius,m,parent=exterior,name=''){const curve=new T.CatmullRomCurve3(points.map(p=>new T.Vector3(...p)));return mesh(new T.TubeGeometry(curve,Math.min(48,Math.max(6,points.length*2)),radius,6,false),m,parent,name);}
 function cylinder(radius,length,x,y,z,m,parent=exterior,axis='z',segments=24){const o=mesh(new T.CylinderGeometry(radius,radius,length,segments),m,parent);if(axis==='z')o.rotation.x=Math.PI/2;if(axis==='x')o.rotation.z=Math.PI/2;o.position.set(x,y,z);return o;}
 function panelYZ(points,x,m,parent=exterior){const shape=new T.Shape();points.forEach(([y,z],i)=>i?shape.lineTo(z,y):shape.moveTo(z,y));shape.closePath();const o=mesh(new T.ShapeGeometry(shape),m,parent);o.rotation.y=Math.PI/2;o.position.x=x;return o;}
 const frontAxle=WB/2+(s.type==='microvan'?.12:0),rearAxle=-WB/2+(s.type==='microvan'?.12:0);
 const photoProfile=PHOTO_PROFILES[s.dash];
 const [rearBase,rearRoof,frontRoof,frontBase]=photoProfile?[photoProfile.rearBase,photoProfile.rearRoof,photoProfile.frontRoof,photoProfile.frontBase]:s.cab.map(x=>x*L),roofWidth=photoProfile?.roofWidth??W*(boxy?.43:.385),roofY=photoProfile?.roof??H-.055;
 if(photoProfile)buildPhotoBody({s,mats,exterior,interior,mesh,rounded,pipe,cylinder,quad,glass});
 const samples=112;
 function widthAt(x){const t=x/(L/2);return W/2*(1-(boxy?.035:.10)*Math.abs(t)**4-(s.type==='coupe'?.025:0)*Math.max(0,t));}
 function beltAt(x){const t=x/(L/2);return waist-(s.type==='actyon'?.12:s.type==='coupe'?.08:.035)*Math.max(0,t)**3;}
 function lowerAt(x){let y=floor;for(const axle of [frontAxle,rearAxle]){const q=(x-axle)/(r*1.10);if(Math.abs(q)<1)y=Math.max(y,r+Math.sqrt(1-q*q)*r*1.08);}return y;}
 if(!photoProfile){
 // Smooth side skins with actual wheel openings, rather than overlapping boxes.
 for(const sign of [-1,1]){
  const positions=[],indices=[];
  for(let i=0;i<=samples;i++){const x=-L/2+i/samples*L,w=widthAt(x),top=beltAt(x),bottom=Math.min(top-.04,lowerAt(x));for(let k=0;k<4;k++){const t=k/3,y=bottom+(top-bottom)*t,z=sign*(w-.035+Math.sin(t*Math.PI)*.035);positions.push(x,y,z);}}
  for(let i=0;i<samples;i++)for(let k=0;k<3;k++){const a=i*4+k;indices.push(a,a+4,a+1,a+1,a+4,a+5);}
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(positions,3));g.setIndex(indices);g.computeVertexNormals();mesh(g,mats.paint,exterior,'차체 곡면');
 }
 rounded(L*.93,.10,W*.88,0,floor+.025,0,mats.black,interior,.025);

 function deck(start,end){for(let i=0;i<20;i++){const a=start+(end-start)*i/20,b=start+(end-start)*(i+1)/20;for(const sign of [-1,1])quad([[a,beltAt(a),sign*widthAt(a)],[a,beltAt(a)+.07,0],[b,beltAt(b)+.07,0],[b,beltAt(b),sign*widthAt(b)]],mats.paint);}}
 deck(-L/2,rearBase);deck(frontBase,L/2);
 for(let i=0;i<22;i++){const a=rearRoof+(frontRoof-rearRoof)*i/22,b=rearRoof+(frontRoof-rearRoof)*(i+1)/22;for(let j=0;j<12;j++){const za=-roofWidth+j/12*roofWidth*2,zb=-roofWidth+(j+1)/12*roofWidth*2;const y=z=>roofY+.055*(1-(z/roofWidth)**2);quad([[a,y(za),za],[a,y(zb),zb],[b,y(zb),zb],[b,y(za),za]],s.type==='jeep'?mats.black:mats.paint);}}
 const baseFrontY=beltAt(frontBase)+.035,baseRearY=beltAt(rearBase)+.035;
 const wind=quad([[frontBase,baseFrontY,-W*.45],[frontBase,baseFrontY,W*.45],[frontRoof,roofY,roofWidth],[frontRoof,roofY,-roofWidth]],mats.glass,exterior,'앞유리');glass.push(wind);
 glass.push(quad([[rearBase,baseRearY,W*.45],[rearBase,baseRearY,-W*.45],[rearRoof,roofY,-roofWidth],[rearRoof,roofY,roofWidth]],mats.glass,exterior,'뒷유리'));
 const pillar=(points,rad=.028)=>pipe(points,rad,mats.black,exterior,'차체 기둥');
 for(const sign of [-1,1]){
  const baseZ=sign*W*.45,roofZ=sign*roofWidth,bx=s.type==='coupe'?-.35:-.18;
  const windows=[[[frontBase,baseFrontY,baseZ],[bx,waist+.02,baseZ],[bx,roofY,roofZ],[frontRoof,roofY,roofZ]],[[bx-.045,waist+.02,baseZ],[rearBase,baseRearY,baseZ],[rearRoof,roofY,roofZ],[bx-.045,roofY,roofZ]]];
  for(const points of windows)glass.push(quad(points,mats.glass,exterior,'옆유리'));
  pillar([[frontBase,baseFrontY,baseZ],[frontRoof,roofY,roofZ]],.035);pillar([[rearBase,baseRearY,baseZ],[rearRoof,roofY,roofZ]],.045);pillar([[bx,waist,baseZ],[bx,roofY,roofZ]],.035);
  pillar([[rearBase,waist,baseZ],[0,waist+.01,sign*widthAt(0)],[frontBase,baseFrontY,baseZ]],.012);
  for(const axle of [frontAxle,rearAxle]){const points=[];for(let i=0;i<=24;i++){const a=Math.PI*i/24;points.push([axle+Math.cos(a)*r*1.11,r+Math.sin(a)*r*1.09,sign*(widthAt(axle)+.012)]);}pipe(points,s.type==='jeep'?.06:.016,mats.black);}
  const doors=s.type==='coupe'?[[-.17,frontBase-.08]]:[[-.16,frontBase-.08],[rearBase+.10,-.24]];
  for(const [a,b] of doors){pipe([[a,waist-.04,sign*(widthAt(a)+.008)],[a,floor+.12,sign*(widthAt(a)+.01)],[b,floor+.10,sign*(widthAt(b)+.01)],[b,waist-.04,sign*(widthAt(b)+.008)]],.006,mats.black);rounded(.16,.025,.025,a+.12,waist-.08,sign*(widthAt(a)+.022),mats.chrome);}
  const mirror=rounded(.22,.12,.14,frontBase-.12,waist+.10,sign*(W*.52),mats.paint);rounded(.015,.08,.11,frontBase-.205,waist+.10,sign*(W*.52),mats.chrome);
  // Inner door panels and handles are retained in the driver's view.
  rounded((frontBase-rearBase)*.98,.23,.045,(frontBase+rearBase)/2,waist-.14,sign*W*.435,mats.leather,interior);rounded(.28,.035,.075,.05,waist-.12,sign*W*.41,mats.dash,interior);
  if(['suv','van','actyon'].includes(s.type))pipe([[rearRoof+.05,H+.025,sign*W*.36],[frontRoof-.10,H+.025,sign*W*.36]],.022,mats.chrome);
 }
 // Bumpers and model-specific front/rear signatures.
 for(const end of [-1,1])rounded(.12,waist-floor-.04,W*.94,end*(L/2-.065),(waist+floor)/2,0,mats.paint,exterior,.045);
 const front=L/2-.09,rear=-L/2+.055;
 panelYZ([[floor+.08,-W*.40],[floor+.08,W*.40],[waist-.12,W*.36],[waist-.12,-W*.36]],front,mats.black);
 function lamp(points,x=front,material=mats.headlight){return panelYZ(points,x,material);}
 if(s.type==='jeep'){
  rounded(.10,.37,W*.74,front-.03,waist-.06,0,mats.paint);
  for(let i=-3;i<=3;i++)rounded(.024,.27,.055,front+.035,waist-.05,i*W*.055,mats.black);
  for(const z of [-W*.35,W*.35]){cylinder(.112,.025,front+.06,waist+.01,z,mats.chrome,exterior,'x');cylinder(.090,.035,front+.078,waist+.01,z,mats.headlight,exterior,'x');rounded(.24,.10,.32,front-.15,waist-.25,z,mats.black);}
  rounded(.23,.13,W*1.02,front-.10,floor+.10,0,mats.black);
  // Rear-mounted spare wheel is a distinct fifth wheel, outside the cabin.
  const spare=new T.Group();spare.position.set(-L/2+.125,waist,0);spare.rotation.y=Math.PI/2;exterior.add(spare);cylinder(r,.22,0,0,0,mats.rubber,spare);cylinder(r*.62,.24,0,0,0,mats.rim,spare);
 }else if(s.type==='microvan'){
  for(const z of [-W*.32,W*.32])rounded(.025,.17,.30,front+.025,waist-.20,z,mats.headlight);for(let i=0;i<3;i++)rounded(.018,.016,W*.34,front+.04,waist-.13-i*.05,0,mats.black);rounded(.08,.14,W*.98,front-.02,floor+.08,0,mats.black);
 }else if(s.dash==='grandeur'){
  rounded(.023,.022,W*.94,front+.01,waist+.01,0,mats.headlight);
  for(const sign of [-1,1])rounded(.028,.18,.10,front+.03,waist-.21,sign*W*.37,mats.headlight);
  for(let i=-8;i<=8;i++)rounded(.018,.21,.012,front+.015,waist-.23,i*W*.041,mats.chrome);
 }else if(['carnival','sorento'].includes(s.dash)){
  for(const sign of [-1,1]){const z=sign*W*.39;rounded(.025,.28,.035,front+.04,waist-.04,z,mats.headlight);rounded(.025,.025,.23,front+.05,waist+.085,z-sign*.10,mats.headlight);for(let i=0;i<3;i++)rounded(.023,.047,.055,front+.055,waist+.04-i*.075,z-sign*.065,mats.headlight);}
  for(let j=-1;j<=1;j++)for(let i=-6;i<=6;i++)rounded(.018,.016,.055,front+.01,waist-.17+j*.07,i*W*.05,mats.chrome);
 }else if(s.dash==='equus'){
  for(let j=0;j<6;j++)rounded(.025,.018,W*.44,front+.045,waist-.23+j*.048,0,mats.chrome);
  for(const sign of [-1,1])lamp([[waist+.045,sign*W*.45],[waist+.035,sign*W*.25],[waist-.085,sign*W*.28],[waist-.10,sign*W*.45]]);
  cylinder(.022,.12,L*.42,waist+.16,0,mats.chrome,exterior,'y',10);
 }else if(s.dash==='actyon'){
  for(const sign of [-1,1])lamp([[waist+.02,sign*W*.46],[waist+.12,sign*W*.30],[waist-.11,sign*W*.25],[waist-.17,sign*W*.43]]);
  for(let j=0;j<4;j++)rounded(.025,.016,W*.27,front+.04,waist-.18+j*.045,0,mats.chrome);
 }else{
  for(const sign of [-1,1])lamp([[waist+.04,sign*W*.46],[waist+.045,sign*W*.22],[waist-.025,sign*W*.25],[waist-.10,sign*W*.45]]);
  for(let j=0;j<4;j++)rounded(.02,.009,W*.65,front+.02,waist-.17+j*.045,0,s.dash==='spark'?mats.chrome:mats.black);
  if(s.dash==='camaro'){rounded(.7,.01,.065,L*.29,waist+.08,-.11,mats.black);rounded(.7,.01,.065,L*.29,waist+.08,.11,mats.black);}
 }
 for(const sign of [-1,1]){
  if(['van','suv','microvan','jeep','actyon'].includes(s.type))rounded(.023,.24,.09,rear-.01,waist-.04,sign*W*.40,mats.red);
  else rounded(.023,.075,W*.24,rear-.01,waist-.02,sign*W*.32,mats.red);
 }
 if(['grandeur','avante'].includes(s.dash))rounded(.025,.018,W*.90,rear-.01,waist+.02,0,mats.red);
 for(const x of [front,rear]){rounded(.015,.095,.39,x+(x>0?.03:-.03),floor+.16,0,mats.chrome);}
 for(const z of [-W*.28,W*.28])pipe([[frontBase+.03,baseFrontY+.02,z],[frontBase-.08,baseFrontY+.025,z-.25]],.008,mats.black);

 }
 const wheels=[];
 for(const x of [rearAxle,frontAxle])for(const sign of [-1,1]){
  const wheelRadius=x===frontAxle?r:(s.rRear??r);const g=new T.Group();g.position.set(x,wheelRadius,sign*(photoProfile?((x===frontAxle?s.trackFront:s.trackRear)/2):(W/2-.075)));exterior.add(g);const thickness=photoProfile?(x===frontAxle?s.tireWidthFront:s.tireWidthRear):(s.type==='jeep'?.27:.205);
  if(photoProfile){
   const rimRadius=(x===frontAxle?s.rimRadiusFront:s.rimRadiusRear)||.1524,faceZ=sign*(thickness/2+.006);
   const tire=mesh(new T.TorusGeometry((wheelRadius+rimRadius)/2,(wheelRadius-rimRadius)/2,12,48),mats.rubber,g,'타이어 둥근 숄더');tire.scale.z=thickness/(wheelRadius-rimRadius);
   cylinder(rimRadius,thickness,0,0,0,mats.black,g);
   for(const side of [-1,1]){const lip=mesh(new T.TorusGeometry(rimRadius-.009,.012,8,48),mats.rim,g,'휠 림');lip.position.z=side*thickness/2;}
   cylinder(rimRadius*.68,.015,0,0,0,mats.chrome,g);cylinder(.041,thickness+.02,0,0,0,mats.rim,g);
   const count=['equus','grandeur'].includes(s.dash)?10:s.dash==='carnival'?9:s.dash==='spark'?7:5;for(let j=0;j<count;j++){const a=j/count*Math.PI*2;for(const shift of(s.dash==='equus'?[-.035,.035]:[0])){const spoke=rounded(s.dash==='damas'?.028:.015,rimRadius*.83,.025,Math.sin(a)*rimRadius*.52,Math.cos(a)*rimRadius*.52,faceZ,mats.rim,g,.006);spoke.rotation.z=-a+shift;}}
   for(let j=0;j<5;j++){const a=j/5*Math.PI*2;cylinder(.008,.018,Math.cos(a)*.038,Math.sin(a)*.038,faceZ,mats.chrome,g);}
  }else{
  cylinder(wheelRadius,thickness,0,0,0,mats.rubber,g);cylinder(wheelRadius*.72,thickness+.008,0,0,0,mats.black,g);
  cylinder(wheelRadius*.62,.012,0,0,sign*(thickness/2+.01),mats.chrome,g);
  const n=s.type==='jeep'?5:s.dash==='equus'?10:6;
  for(let j=0;j<n;j++){const angle=j/n*Math.PI*2,spoke=rounded(wheelRadius*.11,wheelRadius*1.28,.024,0,0,sign*(thickness/2+.026),mats.rim,g,.009);spoke.rotation.z=angle;}
  cylinder(.055,thickness+.065,0,0,0,mats.rim,g);}
  wheels.push({mesh:g,rotation:g.rotation.clone(),radius:wheelRadius,front:x===frontAxle});
 }
 // Per-model cockpit: dashboard, seats, steering, consoles, vents and mirrors.
 const eyeY=s.type==='microvan'?1.36:Math.max(1.02,H*.75),eyeX=Math.min(frontRoof-.36,frontBase-(photoProfile?(s.dash==='damas'?1.01:1.24):.99)),driverZ=-W*.235,dashX=Math.min(frontBase-(photoProfile?.26:.04),eyeX+.95),dashY=eyeY-.24;
 const darkDash=rounded(.42,.17,W*.85,dashX,dashY,0,mats.dash,interior,.06);
 rounded(.24,.22,.24,dashX-.14,dashY-.13,driverZ,mats.dash,interior);
 const instrument=new T.Group();instrument.position.set(dashX-.225,dashY+.01,driverZ);interior.add(instrument);
 const textures=[];
 function screen(width,height,x,y,z,kind='nav'){
  rounded(.035,height+.026,width+.026,x+.015,y,z,mats.black,interior,.012);
  const canvas=typeof document!=='undefined'?document.createElement('canvas'):null;
  if(!canvas)return null;canvas.width=kind==='cluster'?600:800;canvas.height=280;
  const context=canvas.getContext('2d'),texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
  const o=mesh(new T.PlaneGeometry(width,height),new T.MeshBasicMaterial({map:texture,side:T.DoubleSide}),interior,'실내 화면');o.rotation.y=-Math.PI/2;o.position.set(x-.008,y,z);textures.push({canvas,context,texture,kind});return o;
 }
 const modern=['avante','grandeur','sorento'].includes(s.dash);
 if(['avante','grandeur'].includes(s.dash)){screen(.26,.074,dashX-.23,dashY+.145,driverZ,'cluster');screen(.315,.31,dashX-.29,dashY+.010,.055);rounded(.20,.035,.37,dashX-.17,dashY-.20,.055,mats.black,interior,.01);for(const z of[-.11,.22])cylinder(.016,.018,dashX-.285,dashY-.185,z,mats.chrome,interior,'x',16);}
 else if(s.dash==='sorento'){screen(.35,.14,dashX-.23,dashY+.11,driverZ,'cluster');screen(.38,.14,dashX-.23,dashY+.11,.08);}

 else{
  rounded(.065,.19,.39,dashX-.19,dashY+.055,driverZ,mats.black,interior,.045);
  screen(.30,.13,dashX-.232,dashY+.065,driverZ,'cluster');
  if(s.dash!=='damas')screen(s.dash==='wrangler'?.48:s.dash==='equus'?.31:.24,s.dash==='equus'?.16:.14,dashX-.24,dashY+(s.dash==='equus'?.075:-.025),.06);
  else{rounded(.02,.055,.21,dashX-.235,dashY-.02,.06,mats.black,interior);for(const z of [-.02,.14])cylinder(.018,.025,dashX-.255,dashY-.02,z,mats.chrome,interior,'x',12);}
 }
 if(s.dash==='actyon'){rounded(.20,.48,.36,dashX-.12,dashY-.17,.03,mats.dash,interior,.035);for(let i=0;i<5;i++)cylinder(.018,.023,dashX-.235,dashY-.22-i*.063,-.155,mats.black,interior,'x',12);screen(.23,.065,dashX-.24,dashY-.21,.045,'radio');}
 if(s.dash==='damas'){for(const z of [-W*.34,-.13,.17,W*.34])rounded(.025,.105,.055,dashX-.25,dashY-.04,z,mats.black,interior,.005);rounded(.023,.07,.22,dashX-.25,dashY-.02,.02,mats.black,interior);}
 const roundVents=['wrangler','camaro','actyon'].includes(s.dash);
 for(const z of (s.dash==='damas'?[]:s.dash==='wrangler'?[-W*.34,W*.34]:s.dash==='actyon'?[-W*.34,-.07,.16,W*.34]:[-W*.34,-.16,.23,W*.34])){
  if(roundVents){cylinder(s.dash==='camaro'?(Math.abs(z)<.3?.069:.046):.040,.035,dashX-.24,dashY+(s.dash==='actyon'&&Math.abs(z)<.2?.13:-.11),z,mats.chrome,interior,'x',24);cylinder(s.dash==='camaro'?(Math.abs(z)<.3?.056:.038):.031,.039,dashX-.26,dashY+(s.dash==='actyon'&&Math.abs(z)<.2?.13:-.11),z,mats.black,interior,'x',24);}
  else{rounded(.025,.031,.13,dashX-.24,dashY-.095,z,mats.black,interior,.004);for(let j=-1;j<=1;j++)rounded(.026,.003,.12,dashX-.255,dashY-.095+j*.007,z,mats.chrome,interior,.001);}
 }
 if(s.dash==='equus'){rounded(.03,.052,W*.76,dashX-.21,dashY-.095,0,mats.wood,interior);cylinder(.028,.018,dashX-.25,dashY+.055,.06,mats.chrome,interior,'x',24);}
 if(s.dash==='wrangler'){rounded(.06,.14,W*.80,dashX-.20,dashY-.08,0,new T.MeshStandardMaterial({color:'#994e43',roughness:.7}),interior);pipe([[dashX-.27,dashY-.03,.28],[dashX-.30,dashY-.03,.56]],.022,mats.chrome,interior);}

 if(s.dash==='carnival'){rounded(.035,.045,W*.76,dashX-.20,dashY-.07,0,mats.wood,interior);for(const z of[-.16,.27])rounded(.025,.16,.055,dashX-.255,dashY+.045,z,mats.black,interior,.008);}
 if(['avante','grandeur'].includes(s.dash)){const ambient=new T.MeshBasicMaterial({color:s.dash==='avante'?'#9a2848':'#bd6b37'});rounded(.025,.008,W*.76,dashX-.245,dashY-.09,0,ambient,interior,.002);for(const sign of[-1,1])rounded(.70,.008,.015,eyeX-.02,waist-.12,sign*W*.425,ambient,interior,.002);}
 if(s.dash==='spark'){rounded(.065,.19,.29,dashX-.19,dashY+.075,driverZ,mats.black,interior,.045);for(const z of[-.14,.01,.17])cylinder(.022,.025,dashX-.25,dashY-.215,z,mats.chrome,interior,'x',16);rounded(.02,.07,.25,dashX-.25,dashY-.105,.05,mats.black,interior,.01);}
 const consoleX=eyeX-.04,consoleY=floor+.29;
 rounded(.85,.24,.22,consoleX,consoleY,0,mats.dash,interior,.045);
 if(['avante','grandeur'].includes(s.dash)){rounded(.045,.055,.13,dashX-.34,eyeY-.28,driverZ+.20,mats.black,interior,.018);}
 else if(s.dash==='sorento'){cylinder(.052,.035,consoleX+.15,consoleY+.14,0,mats.chrome,interior,'y',24);}
 else{pipe([[consoleX+.12,consoleY+.12,0],[consoleX+.17,consoleY+.29,0]],.018,mats.chrome,interior);rounded(.065,.05,.05,consoleX+.17,consoleY+.30,0,mats.black,interior);}
 if(s.dash==='wrangler'){pipe([[consoleX+.04,consoleY+.10,-.14],[consoleX+.09,consoleY+.25,-.14]],.014,mats.chrome,interior);cylinder(.026,.040,consoleX+.09,consoleY+.27,-.14,mats.black,interior,'y',20);}
 for(const z of [-.043,.043])cylinder(.027,.008,consoleX-.15,consoleY+.125,z,mats.black,interior,'y',20);
 if(s.type==='microvan')rounded(.68,.25,.38,eyeX-.15,.64,0,mats.dash,interior,.08);
 const steering=new T.Group();steering.position.set(dashX-.43,eyeY-.20,driverZ);steering.rotation.z=-.10;interior.add(steering);
 const ring=mesh(new T.TorusGeometry(.17,.017,10,40),mats.black,steering,'운전대');ring.rotation.y=Math.PI/2;
 rounded(.04,.09,.16,0,0,0,mats.leather,steering,.02);if(s.dash==='wrangler')cylinder(.065,.022,-.025,0,0,mats.black,steering,'x',24);if(s.dash==='grandeur')rounded(.045,.12,.20,-.01,0,0,mats.leather,steering,.025);
 for(const sign of [-1,1])pipe([[0,0,sign*.04],[0,sign*.015,sign*.15]],.015,mats.chrome,steering);
 if(s.dash!=='grandeur')pipe([[0,-.015,0],[0,-.15,0]],.016,mats.chrome,steering);
 pipe([[dashX-.42,eyeY-.20,driverZ],[dashX-.1,eyeY-.30,driverZ]],.028,mats.black,interior);
 if(s.dash==='equus'){for(const start of [.30,3.45]){const points=[];for(let i=0;i<16;i++){const a=start+i/15*.98;points.push([0,Math.sin(a)*.17,Math.cos(a)*.17]);}pipe(points,.019,mats.wood,steering);}}
 if(s.dash==='actyon'){rounded(.045,.14,.23,0,0,0,mats.dash,steering,.03);for(const sign of [-1,1])for(let i=0;i<4;i++)rounded(.014,.02,.025,-.031,.035-i*.026,sign*.105,mats.chrome,steering,.003);}
 const seats=[];
 function seat(x,z,driver=false){const g=new T.Group();interior.add(g);rounded(.48,.12,.44,x,floor+.30,z,mats.leather,g,.06);rounded(.13,.50,.45,x-.20,floor+.58,z,mats.leather,g,.055).rotation.z=-.12;rounded(.10,.17,.24,x-.23,floor+.94,z,mats.leather,g,.04);for(const side of [-1,1])pipe([[x-.08,floor+.37,z+side*.19],[x-.12,floor+.77,z+side*.19]],.018,mats.black,g);for(const sign of[-1,1]){rounded(.36,.06,.055,x,floor+.37,z+sign*.20,mats.leather,g,.022);rounded(.10,.39,.045,x-.15,floor+.61,z+sign*.20,mats.leather,g,.02).rotation.z=-.12;}seats.push({group:g,driver});}
 seat(eyeX-.02,driverZ,true);seat(eyeX-.02,-driverZ);
 const rows=s.seats>=7?3:2;
 for(let row=1;row<rows;row++){const x=eyeX-.74*row;for(const sign of [-1,1])seat(x,sign*W*.235);}
 if(s.seats===5)seat(eyeX-.74,0);
 if(s.seats===7)seat(eyeX-.74*(s.dash==='carnival'?2:1),0);
 const mirror=rounded(.035,.075,.23,frontRoof+.07,H-.19,0,mats.chrome,interior,.015);pipe([[frontRoof+.07,H-.14,0],[frontRoof+.07,H-.10,0]],.012,mats.black,interior);
 rounded(.21,.045,.30,frontRoof-.13,H-.08,driverZ,mats.leather,interior);
 function drawReferenceCluster(ctx,c,speed){
  const blue=s.dash==='equus',max=s.dash==='damas'?160:s.dash==='actyon'?220:260;ctx.fillStyle=blue?'#071025':'#101213';ctx.fillRect(0,0,c.width,c.height);ctx.textAlign='center';
  for(const [x,limit,rpm]of[[137,8,true],[450,max,false]]){const y=146,R=102;ctx.strokeStyle=blue?'#508cdb':'#a3a7a6';ctx.lineWidth=3;ctx.beginPath();ctx.arc(x,y,R,Math.PI*.75,Math.PI*2.25);ctx.stroke();
   for(let i=0;i<=40;i++){const a=Math.PI*.75+i/40*Math.PI*1.5;ctx.strokeStyle=i>34&&rpm?'#c44f4b':'#b9c4ca';ctx.lineWidth=i%5===0?3:1;ctx.beginPath();ctx.moveTo(x+Math.cos(a)*(R-4),y+Math.sin(a)*(R-4));ctx.lineTo(x+Math.cos(a)*(R-(i%5===0?18:10)),y+Math.sin(a)*(R-(i%5===0?18:10)));ctx.stroke();if(i%5===0){ctx.fillStyle='#dce4e6';ctx.font='15px sans-serif';ctx.fillText(String(Math.round(i/40*limit)),x+Math.cos(a)*(R-33),y+Math.sin(a)*(R-33)+5);}}
   const value=rpm?Math.min(5,.8+speed/35):speed,a=Math.PI*.75+value/limit*Math.PI*1.5;ctx.strokeStyle='#e25743';ctx.lineWidth=4;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+Math.cos(a)*78,y+Math.sin(a)*78);ctx.stroke();ctx.fillStyle='#b7c8c8';ctx.font='13px sans-serif';ctx.fillText(rpm?'x1000 rpm':'km/h',x,y+42);
  }
  ctx.fillStyle=blue?'#67a2d7':'#a5b9a0';ctx.fillRect(236,202,128,32);ctx.fillStyle='#142221';ctx.font='18px monospace';ctx.fillText('000000',300,225);
 }
 function drawSparkCluster(ctx,c,speed){ctx.fillStyle='#0b1014';ctx.fillRect(0,0,c.width,c.height);ctx.strokeStyle='#a7bdc0';ctx.lineWidth=8;ctx.beginPath();ctx.arc(176,142,105,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#d9e1dd';ctx.font='25px sans-serif';for(let i=0;i<=8;i++){const a=Math.PI*.75+i/8*Math.PI*1.5;ctx.fillText(String(i),176+Math.cos(a)*79,150+Math.sin(a)*79);}const a=Math.PI*.75+Math.min(6,1+speed/25)/8*Math.PI*1.5;ctx.strokeStyle='#df5142';ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(176,142);ctx.lineTo(176+Math.cos(a)*78,142+Math.sin(a)*78);ctx.stroke();ctx.fillStyle='#334c9b';ctx.fillRect(310,70,250,150);ctx.fillStyle='#d5e7ee';ctx.font='bold 66px sans-serif';ctx.fillText(String(Math.round(speed)),435,165);ctx.font='22px sans-serif';ctx.fillText('km/h',435,199);}
 function update(speed,steer,time=0){steering.rotation.x=-steer*1.7;for(const item of textures){const {context:ctx,canvas:c,kind}=item;if(!ctx)continue;ctx.fillStyle='#0c1520';ctx.fillRect(0,0,c.width,c.height);ctx.strokeStyle='#6f919e';ctx.lineWidth=4;ctx.fillStyle='#dcecf2';ctx.textAlign='center';if(kind==='radio'){ctx.fillStyle='#82c9ab';ctx.font='42px sans-serif';ctx.fillText('23.5   AUTO',c.width/2,170);}else if(kind==='cluster'&&s.dash==='spark'){drawSparkCluster(ctx,c,speed);}else if(kind==='cluster'&&photoProfile&&!modern){drawReferenceCluster(ctx,c,speed);}else if(kind==='cluster'){ctx.font='bold 96px sans-serif';ctx.fillText(String(Math.round(speed)),c.width/2,158);ctx.font='24px sans-serif';ctx.fillStyle='#99acb4';ctx.fillText('킬로미터/시',c.width/2,206);if(!modern){for(const x of [100,500]){ctx.beginPath();ctx.arc(x,145,80,Math.PI*.75,Math.PI*2.25);ctx.stroke();ctx.strokeStyle='#e1bd75';ctx.beginPath();ctx.moveTo(x,145);const a=Math.PI*.75+speed/160*Math.PI*1.5;ctx.lineTo(x+Math.cos(a)*64,145+Math.sin(a)*64);ctx.stroke();}}}else{ctx.fillStyle='#192b36';ctx.fillRect(10,10,c.width-20,c.height-20);ctx.strokeStyle='#506d7c';ctx.lineWidth=12;for(let i=0;i<4;i++){ctx.beginPath();ctx.moveTo(80+i*180,10);ctx.lineTo(140+i*160,c.height);ctx.stroke();}ctx.lineWidth=13;ctx.strokeStyle='#80d0c5';ctx.beginPath();ctx.moveTo(100,240);ctx.lineTo(360,150);ctx.lineTo(650,120);ctx.stroke();ctx.fillStyle='#e6c477';ctx.beginPath();ctx.arc(360,150,11,0,Math.PI*2);ctx.fill();ctx.fillStyle='#edf2ec';ctx.font='bold 33px sans-serif';ctx.fillText('종로 · 광화문',c.width/2,50);}item.texture.needsUpdate=true;}}
 update(0,0);
 batchVehicleGroup(exterior);batchVehicleGroup(interior);
 root.userData={size:new T.Vector3(L,H,W),wheels,spec:s,driverEye:new T.Vector3(eyeX,eyeY,driverZ),steering,interior,exterior,seats,glass,photoProfile:!!photoProfile,referenceFidelity:'사진 대조 진행 중 · 실차 정밀 복원 미완성',updateCockpit:update,meshCount:meshes};
 interior.traverse(o=>{if(o.isMesh)o.userData.driveInterior=false;});
 root.traverse(o=>{if(o.isMesh)o.userData.driveVehicle=true;});
 return root;
}
