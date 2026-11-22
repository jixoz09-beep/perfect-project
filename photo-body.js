/* Separate photo-reference profiles. Hand-built surfaces; not scan/CAD data. */
import * as T from 'three';
import {buildPhotoSignature} from 'photo-signatures';
export const PHOTO_PROFILES={
 equus:{belt:.94,frontBase:1.31,frontRoof:.43,rearRoof:-1.11,rearBase:-1.98,roofWidth:.715,roof:1.47,frontHeight:.98,rearHeight:.95,color:'#14151a',grille:'vertical'},
 actyon:{belt:1.08,frontBase:1.17,frontRoof:.43,rearRoof:-.91,rearBase:-2.04,roofWidth:.715,roof:1.72,frontHeight:1.03,rearHeight:1.10,color:'#ac1726',grille:'horizontal'},
 avante:{belt:.94,frontBase:1.29,frontRoof:.34,rearRoof:-1.12,rearBase:-1.95,roofWidth:.69,roof:1.405,frontHeight:.94,rearHeight:.99,color:'#a0a5aa',grille:'provided-photo'},
 grandeur:{belt:.96,frontBase:1.37,frontRoof:.55,rearRoof:-1.30,rearBase:-2.03,roofWidth:.715,roof:1.44,frontHeight:.96,rearHeight:.95,color:'#613b47',grille:'wide-mesh'},
 wrangler:{belt:1.03,frontBase:1.19,frontRoof:.98,rearRoof:-1.67,rearBase:-1.83,roofWidth:.77,roof:1.80,frontHeight:1.06,rearHeight:1.04,color:'#616d48',grille:'seven-slot'},
 carnival:{belt:1.055,frontBase:1.40,frontRoof:.65,rearRoof:-1.98,rearBase:-2.30,roofWidth:.79,roof:1.70,frontHeight:1.025,rearHeight:1.08,color:'#b3b5b2',grille:'yp'},
 sorento:{belt:1.07,frontBase:1.23,frontRoof:.51,rearRoof:-1.47,rearBase:-2.06,roofWidth:.755,roof:1.655,frontHeight:1.06,rearHeight:1.11,color:'#8a8d83',grille:'mq4-fl'},
 spark:{belt:.98,frontBase:1.02,frontRoof:.37,rearRoof:-1.11,rearBase:-1.57,roofWidth:.61,roof:1.49,frontHeight:.89,rearHeight:1.01,color:'#a9d0e3',grille:'m300'},
 camaro:{belt:.83,frontBase:.86,frontRoof:.04,rearRoof:-1.15,rearBase:-1.82,roofWidth:.69,roof:1.31,frontHeight:.84,rearHeight:.90,color:'#1769a3',grille:'ss-2021'},
 damas:{belt:1.10,frontBase:1.56,frontRoof:1.06,rearRoof:-1.48,rearBase:-1.64,roofWidth:.613,roof:1.88,frontHeight:1.25,rearHeight:1.13,color:'#2864a0',grille:'cabover'}
};
export function buildPhotoBody({s,mats,exterior,interior,mesh,rounded,pipe,cylinder,quad,glass}){
 const c=PHOTO_PROFILES[s.dash],{W,r,WB}=s,isJeep=s.dash==='wrangler',L=s.L-(isJeep?.32:0),half=L/2,isVan=s.dash==='damas',isSUV=s.dash==='actyon';
 mats.paint.color.set(c.color);mats.paint.roughness=.23;mats.glass.opacity=.38;mats.glass.color.set('#243339');
 function surface(fn,nu,nv,material,name,parent=exterior){const a=[],ix=[];for(let i=0;i<=nu;i++)for(let j=0;j<=nv;j++)a.push(...fn(i/nu,j/nv));for(let i=0;i<nu;i++)for(let j=0;j<nv;j++){const n=i*(nv+1)+j;ix.push(n,n+nv+1,n+1,n+1,n+nv+1,n+nv+2);}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(a,3));g.setIndex(ix);g.computeVertexNormals();const nu2=Math.max(3,Math.ceil(nu/4)),nv2=Math.max(2,Math.ceil(nv/3)),lp=[],li=[];for(let i=0;i<=nu2;i++)for(let j=0;j<=nv2;j++)lp.push(...fn(i/nu2,j/nv2));for(let i=0;i<nu2;i++)for(let j=0;j<nv2;j++){const a=i*(nv2+1)+j;li.push(a,a+nv2+1,a+1,a+1,a+nv2+1,a+nv2+2);}g.userData.driveCanvasProxy={position:new T.Float32BufferAttribute(lp,3),index:li};const m=mesh(g,material,parent,name);m.userData.photoSurface=name;return m;}
 const width=x=>W*.5*(1-(isVan?.015:.055)*Math.abs(x/half)**5),belt=x=>c.belt-(c.belt-c.frontHeight)*Math.max(0,x/half)**4-(c.belt-c.rearHeight)*Math.max(0,-x/half)**4;
 const corner=isVan?.08:isJeep?.07:isSUV?.24:.20;
 const endX=(end,z,v=1)=>end*(half-.025-corner*Math.abs(z/width(end*half))**3);
 const warp=(x,z)=>x-Math.sign(x)*(.025+corner*Math.abs(z/width(x))**3)*Math.abs(x/half)**16;
 const vanTrim=new T.MeshStandardMaterial({color:'#8c969b',roughness:.60,metalness:.14,side:T.DoubleSide});
 const wheelX=[-WB/2+(isVan?.12:0),WB/2+(isVan?.12:0)];
 const bottom=x=>Math.max(isVan?.34:.27,...wheelX.map(axle=>{const q=(x-axle)/(r*1.12);return Math.abs(q)<1?r+r*1.12*Math.sqrt(1-q*q):0;}));
 for(const sign of [-1,1]){
  surface((u,v)=>{const x=-half+u*L,y=bottom(x)+(belt(x)-bottom(x))*v,w=width(x)-.045*(1-v)**3-.025*v**8+.025*Math.sin(v*Math.PI);return[warp(x,sign*width(x)),y,sign*w];},100,10,mats.paint,'차종 전용 측면 곡면');
  if(isVan)surface((u,v)=>{const x=-half+u*L,y=bottom(x)+(.82-bottom(x))*v;return[warp(x,sign*width(x)),y,sign*(width(x)-.045*(1-y/belt(x))**3+.004)];},100,8,vanTrim,'다마스 하단 투톤 패널');
  for(const axle of wheelX){const pts=[];for(let i=0;i<=32;i++){const a=i/32*Math.PI;pts.push([axle+Math.cos(a)*r*1.12,r+Math.sin(a)*r*1.12,sign*(width(axle)+.005)]);}pipe(pts,isSUV?.027:.012,mats.black);}
  const sz=sign*W*.47,rz=sign*c.roofWidth;
  surface((u,v)=>{const x=c.frontBase+(c.rearBase-c.frontBase)*u,z=sign*((width(x)-.025)*(1-v)+W*.47*v);return[warp(x,z),belt(x)+.008*Math.sin(v*Math.PI),z];},44,6,mats.paint,'도어 상단 어깨 곡면');
  function cabin(u,v,offset=0){const baseX=c.frontBase+(c.rearBase-c.frontBase)*u,topX=c.frontRoof+(c.rearRoof-c.frontRoof)*u,x=baseX+(topX-baseX)*v,y=belt(baseX)+(c.roof-.05-.035*Math.abs(2*u-1)**4-belt(baseX))*v,z=sz+(rz-sz)*v+sign*(.022*Math.sin(v*Math.PI)+offset);return[x,y,z];}
  // The metal A/C pillars surround the smaller glass aperture.
  const lo=isVan?.055:.06,hi=isVan?.95:.91,vl=.065,vh=.91;
  for(const [a,b,ya,yb]of[[0,lo,0,1],[hi,1,0,1],[lo,hi,0,vl],[lo,hi,vh,1]])surface((u,v)=>cabin(a+(b-a)*u,ya+(yb-ya)*v),20,8,mats.paint,'유리 주변 차체 기둥');
  glass.push(surface((u,v)=>cabin(lo+(hi-lo)*u,vl+(vh-vl)*v,.004),32,12,mats.glass,'차종 전용 옆유리'));
  const trim=s.dash==='equus'?mats.chrome:mats.black;
  for(const v of [vl,vh]){const points=[];for(let j=0;j<=20;j++)points.push(cabin(lo+(hi-lo)*j/20,v,.008));pipe(points,.006,trim);}
  for(const u of [lo,hi]){const points=[];for(let j=0;j<=12;j++)points.push(cabin(u,vl+(vh-vl)*j/12,.008));pipe(points,.006,trim);}
  const bx=isVan?.28:-.18;
  const bu=(c.frontBase-bx)/(c.frontBase-c.rearBase);
  surface((u,v)=>cabin(bu+(u-.5)*.027,vl+(vh-vl)*v,.011),2,12,mats.black,'B필러');
  if(isVan)surface((u,v)=>cabin(.67+(u-.5)*.022,vl+(vh-vl)*v,.011),2,12,mats.paint,'다마스 뒷유리 기둥');
  if(isSUV)surface((u,v)=>cabin(.76+(u-.5)*.018,vl+(vh-vl)*v,.011),2,12,mats.black,'액티언 쿼터유리 기둥');
  for(const x of (isVan?[.35,-.72]:[.02,-1.12])){
   pipe([[x,c.belt-.015,sign*(width(x)+.003)],[x-.04,.42,sign*(width(x)-.01)]],.005,mats.black);
   rounded(isVan?.04:.17,isVan?.15:.032,.024,x-.13,c.belt-.10,sign*(width(x)+.018),s.dash==='equus'?mats.chrome:mats.black);
  }
  rounded(isVan?.14:.24,isVan?.23:.145,.16,c.frontBase-.12,c.belt+.14,sign*(W*.52),mats.paint);
  rounded(.014,.10,.12,c.frontBase-.24,c.belt+.14,sign*(W*.52),mats.chrome);
  rounded((c.frontBase-c.rearBase)*.94,.28,.04,(c.frontBase+c.rearBase)/2,c.belt-.18,sign*W*.435,mats.dash,interior);
  if(isSUV)pipe([[c.rearRoof-.06,c.roof+.015,sign*.57],[c.frontRoof-.14,c.roof+.015,sign*.57]],.022,mats.chrome);
  if(s.dash==='equus')pipe([[-2,.41,sign*W*.485],[1.65,.41,sign*W*.485]],.015,mats.chrome);
  if(isVan){for(let j=0;j<3;j++)pipe([[-1.55,.48+j*.065,sign*W*.502],[1.25,.48+j*.065,sign*W*.502]],.009,mats.chrome);}
 }
 surface((u,v)=>{const x=c.rearRoof+(c.frontRoof-c.rearRoof)*u,z=(v*2-1)*c.roofWidth;return[x,c.roof-.05+.05*Math.sin(v*Math.PI)-.035*Math.abs(2*u-1)**4,z];},28,20,isJeep?mats.black:mats.paint,'차종 전용 지붕 곡면');
 function glazing(a,b,aw,bw,ay,by,name){glass.push(surface((u,v)=>{const x=a+(b-a)*u,z=(v*2-1)*(aw+(bw-aw)*u);return[x,ay+(by-ay)*u+(.05+.005*u)*Math.sin(v*Math.PI),z];},16,20,mats.glass,name));}
 glazing(c.frontRoof,c.frontBase,c.roofWidth,W*.455,c.roof-.085,belt(c.frontBase),'앞유리 곡면');
 glazing(c.rearRoof,c.rearBase,c.roofWidth,W*.455,c.roof-.085,belt(c.rearBase),'뒷유리 곡면');
 for(const [a,b]of [[c.frontBase,half],[c.rearBase,-half]])surface((u,v)=>{const x=a+(b-a)*u,z=(v*2-1)*width(x);return[warp(x,z),belt(x)+.055*(1-(v*2-1)**2)+.018*Math.sin(u*Math.PI),z];},26,24,mats.paint,'후드·트렁크 곡면');
 for(const end of [-1,1]){
  const height=end>0?c.frontHeight:c.rearHeight;
  surface((u,v)=>{const z=(u*2-1)*width(end*half),y=.30+v*(height+.055*(1-(u*2-1)**2)-.30);return[endX(end,z,v),y,z];},40,16,mats.paint,'차종 전용 곡면 범퍼');
  if(isSUV||isVan)surface((u,v)=>{const z=(u*2-1)*width(end*half),top=isVan?.83:.69,y=.30+v*(top-.30);return[endX(end,z,v)+end*.004,y,z];},40,12,mats.black,'하단 무광 범퍼');
 }
 rounded(L*.88,.09,W*.88,0,.30,0,mats.black,interior);
 const front=half-.008,rear=-half+.006;
 function face(points,x,mat,name){const shape=new T.Shape(points.map(p=>new T.Vector2(...p)));let g=new T.ShapeGeometry(shape),a=g.attributes.position,ix=g.index.array,tri=[];for(let i=0;i<ix.length;i+=3)tri.push([ix[i],ix[i+1],ix[i+2]].map(j=>[a.getX(j),a.getY(j)]));for(let k=0;k<2;k++){const out=[];for(const[a,b,c]of tri){const ab=[(a[0]+b[0])/2,(a[1]+b[1])/2],bc=[(b[0]+c[0])/2,(b[1]+c[1])/2],ca=[(c[0]+a[0])/2,(c[1]+a[1])/2];out.push([a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]);}tri=out;}const end=x>0?1:-1,pos=tri.flatMap(t=>t.flatMap(([z,y])=>[endX(end,z)+end*.012,y,z]));g.dispose();g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.computeVertexNormals();return mesh(g,mat,exterior,name);}
 function projector(z,y,r,mat=mats.headlight,end=1){return cylinder(r,.012,endX(end,z,(y-.30)/((end>0?c.frontHeight:c.rearHeight)-.30))+end*.018,y,z,mat,exterior,'x',32);}
 if(['equus','damas','actyon'].includes(s.dash)){
 if(isSUV){
  const grille=[[-.58,1.01],[.58,1.01],[.34,.81],[0,.74],[-.34,.81]];face(grille,front,mats.black,'액티언 역삼각 그릴');
  for(let j=0;j<5;j++){const y=.81+j*.039,w=.18+j*.075;pipe(Array.from({length:13},(_,i)=>{const z=-w+2*w*i/12;return[endX(1,z,(y-.3)/(c.frontHeight-.3))+.018,y,z];}),.007,mats.chrome);}
  for(const sign of [-1,1]){
   face([[sign*.84,1.04],[sign*.43,.84],[sign*.73,.82],[sign*.87,.95]],front-.015,mats.chrome,'액티언 삼각 헤드램프');
   projector(sign*.72,.91,.070);
   projector(sign*.81,.95,.033);
   projector(sign*.70,.58,.045);
   face([[sign*.77,1.13],[sign*.89,.97],[sign*.85,.70],[sign*.63,.70],[sign*.66,1.10]],rear,mats.red,'액티언 리어램프');
   projector(sign*.67,.47,.065,mats.red,-1);
  }
 }else if(isVan){
  for(const sign of [-1,1]){
   face([[sign*.33,1.13],[sign*.61,1.13],[sign*.61,.93],[sign*.33,.93]],front,mats.chrome,'다마스 사각 전조등');
   for(const z of [sign*.405,sign*.52])projector(z,1.03,.052);
   face([[sign*.35,.60],[sign*.58,.60],[sign*.58,.53],[sign*.35,.53]],front,mats.amber,'다마스 방향지시등');
   face([[sign*.58,1.17],[sign*.67,1.17],[sign*.67,.89],[sign*.58,.89]],rear,mats.red,'다마스 테일램프');
  }
  face([[-.38,.46],[.38,.46],[.35,.38],[-.35,.38]],front,mats.black,'다마스 전면 흡기구');
 }else{
  face([[-.49,.88],[.49,.88],[.42,.61],[-.42,.61]],front,mats.black,'에쿠스 그릴 개구');
  for(let i=-11;i<=11;i++){const z=i*.036;pipe([[endX(1,z*.9)+.018,.635,z*.9],[endX(1,z)+.018,.86,z]],.007,mats.chrome);}
  pipe([[-.49,.875],[0,.89],[.49,.875]].map(([z,y])=>[endX(1,z)+.018,y,z]),.013,mats.chrome);
  for(const sign of [-1,1]){face([[sign*.84,1.02],[sign*.48,.91],[sign*.48,.82],[sign*.86,.82]],front-.025,mats.chrome,'에쿠스 헤드램프');for(const z of [sign*.65,sign*.79])projector(z,.89,.052);face([[sign*.86,.95],[sign*.43,.88],[sign*.35,.74],[sign*.83,.75]],rear,mats.red,'에쿠스 리어램프');face([[sign*.44,.38],[sign*.70,.38],[sign*.70,.32],[sign*.44,.32]],rear,mats.chrome,'에쿠스 배기구');projector(sign*.68,.50,.042);}
 }
 }else buildPhotoSignature({s,c,L,W,half,front,rear,endX,face,projector,mats,exterior,rounded,pipe,cylinder,mesh});
 for(const end of [-1,1]){const x=endX(end,0)+end*.012;rounded(.016,.10,.39,x,isVan?.63:.45,0,mats.black);}
 if(!isVan&&['equus','actyon'].includes(s.dash)){face([[-.41,.56],[.41,.56],[.35,.40],[-.35,.40]],front,mats.black,'하단 중앙 흡기구');}
 cylinder(isVan?.018:.021,.025,endX(1,0)+.016,isSUV?1.018:isVan?.88:.93,0,mats.chrome,exterior,'x',20);
 for(const sign of [-1,1])pipe([[c.frontBase+.03,belt(c.frontBase)+.055,sign*.48],[c.frontBase-.10,belt(c.frontBase)+.062,sign*.18]],.008,mats.black);
 return c;
}
