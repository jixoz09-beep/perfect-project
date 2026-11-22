/* Individual front/rear components for the seven newly supplied photo sets. */
import * as T from 'three';
export function buildPhotoSignature({s,c,L,W,half,front,rear,endX,face,projector,mats:m,exterior,rounded:box,pipe,cylinder:cyl,mesh}){
 const frontLine=(points,mat,r=.009,end=1)=>pipe(points.map(([z,y])=>[endX(end,z)+end*.023,y,z]),r,mat);
 const polygon=(pts,mat,end=1,name='')=>face(pts,end>0?front:rear,mat,name);
 function bowtie(y){polygon([[-.095,y+.018],[-.035,y+.018],[-.027,y+.04],[.035,y+.04],[.043,y+.018],[.095,y+.018],[.095,y-.018],[.035,y-.018],[.027,y-.04],[-.035,y-.04],[-.043,y-.018],[-.095,y-.018]],m.chrome,1,'Bowtie emblem');}
 function grille(w,y,h){polygon([[-w,y+h/2],[w,y+h/2],[w*.93,y-h/2],[-w*.93,y-h/2]],m.black);for(let row=0;row<4;row++)for(let col=-6;col<=6;col++){const z=col*w/7,yy=y-h*.34+row*h*.22;frontLine([[z-.028,yy],[z,yy+.013],[z+.028,yy]],m.chrome,.0035);}}
 const lamps=(inner,outer,y,h)=>{for(const sign of[-1,1])polygon([[sign*inner,y],[sign*outer,y+.035],[sign*outer,y-h],[sign*(inner+.035),y-h*.62]],m.headlight);};
 if(s.dash==='spark'){
  polygon([[-.37,.84],[.37,.84],[.36,.78],[-.36,.78]],m.black);polygon([[-.38,.72],[.38,.72],[.29,.48],[-.29,.48]],m.black);bowtie(.75);
  for(let i=0;i<4;i++)frontLine([[-.31,.51+i*.045],[.31,.51+i*.045]],m.black,.008);
  for(const sign of[-1,1]){polygon([[sign*.36,.89],[sign*.65,1.11],[sign*.71,.77],[sign*.44,.78]],m.chrome,1,'M300 tall headlamp');projector(sign*.59,.87,.060);projector(sign*.57,.997,.033,m.amber);polygon([[sign*.43,.60],[sign*.66,.62],[sign*.63,.45],[sign*.43,.47]],m.black);projector(sign*.54,.51,.035);polygon([[sign*.54,1.12],[sign*.70,1.22],[sign*.68,.78],[sign*.56,.76]],m.red,-1,'M300 rear lamp');projector(sign*.61,1.04,.057,m.red,-1);projector(sign*.61,.89,.048,m.headlight,-1);box(.024,.16,.024,-1.20,1.20,sign*.716,m.black);pipe([[-1.10,1.51,sign*.49],[.25,1.51,sign*.49]],.013,m.chrome);}
 }else if(s.dash==='avante'){
  polygon([[-.72,.83],[.72,.83],[.58,.38],[-.58,.38]],m.black);frontLine([[-.86,.96],[-.67,.94],[0,.944],[.67,.94],[.86,.96]],m.headlight,.009);
  for(const sign of[-1,1]){frontLine([[sign*.86,.96],[sign*.81,.87]],m.headlight,.011);polygon([[sign*.53,.81],[sign*.85,.85],[sign*.83,.60],[sign*.63,.51]],m.black);for(let i=0;i<3;i++)frontLine([[sign*.62,.60+i*.065],[sign*.82,.61+i*.065]],m.black,.014);polygon([[sign*.82,.50],[sign*.90,.42],[sign*.72,.37],[sign*.65,.45]],m.chrome);frontLine([[sign*.86,1.00],[sign*.87,.69]],m.red,.013,-1);box(.035,.14,.10,rear-.04,.37,sign*.60,m.black);}
  frontLine([[-.83,.94],[.83,.94]],m.red,.009,-1);
 }else if(s.dash==='grandeur'){
  grille(.79,.67,.36);frontLine([[-.90,.96],[.90,.96]],m.headlight,.009);
  for(const sign of[-1,1])for(let j=0;j<5;j++)box(.022,.025,.033,endX(1,sign*(.64+j*.043))+.024,.825,sign*(.64+j*.043),m.headlight);
  frontLine([[-.86,.965],[.86,.965]],m.red,.011,-1);frontLine([[-.76,.42],[0,.39],[.76,.42]],m.chrome,.016,-1);
 }else if(s.dash==='wrangler'){
  polygon([[-.69,1.12],[.69,1.12],[.69,.76],[-.69,.76]],m.paint);
  for(let j=-3;j<=3;j++)box(.026,.285,.058,front+.02,.93,j*.138,m.black,exterior,.025);
  for(const sign of[-1,1]){projector(sign*.64,1.00,.114,m.chrome);projector(sign*.64,1.00,.095);projector(sign*.61,.54,.053);box(.33,.11,.42,half-.24,.81,sign*.77,m.black);box(.24,.045,.26,half-.16,.87,sign*.77,m.headlight);box(.18,.095,.30,rear+.21,.88,sign*.81,m.black);box(.12,.34,.10,rear-.015,.96,sign*.73,m.red);for(const x of[.76,-.28])for(const y of[.55,.94])box(.065,.05,.024,x,y,sign*W*.5,m.paint);}
  box(.18,.16,W*1.04,front-.06,.53,0,m.black);cyl(s.r,.24,rear-.13,1.04,0,m.rubber,exterior,'x',36);cyl(s.r*.65,.25,rear-.14,1.04,0,m.rim,exterior,'x',24);for(let j=0;j<5;j++){const a=j/5*Math.PI*2,o=box(.021,s.r*1.14,.032,rear-.28,1.04,0,m.chrome);o.rotation.x=a;}
  for(const axle of[-s.WB/2,s.WB/2])for(const sign of[-1,1]){const pts=[];for(let j=0;j<=20;j++){const a=j/20*Math.PI;pts.push([axle+Math.cos(a)*s.r*1.18,s.r+Math.sin(a)*s.r*1.15,sign*(W/2+.025)]);}pipe(pts,.045,m.black);}
 }else if(s.dash==='carnival'){
  grille(.53,.86,.27);for(const y of[.75,.82,.89,.96])frontLine([[-.49,y],[.49,y]],m.chrome,.006);
  lamps(.54,.91,1.025,.16);
  for(const sign of[-1,1]){projector(sign*.70,.97,.050);polygon([[sign*.61,.65],[sign*.88,.70],[sign*.84,.43],[sign*.66,.43]],m.black);for(let j=0;j<3;j++)box(.023,.026,.073,endX(1,sign*.75)+.024,.49+j*.048,sign*.75,m.headlight);polygon([[sign*.50,1.09],[sign*.89,1.11],[sign*.85,.96],[sign*.49,.96]],m.red,-1);pipe([[-1.95,1.02,sign*(W/2+.004)],[-.12,1.02,sign*(W/2+.004)]],.009,m.black);}
 }else if(s.dash==='sorento'){
  grille(.61,.91,.25);for(const sign of[-1,1]){frontLine([[sign*.61,1.06],[sign*.87,1.08],[sign*.85,.79]],m.headlight,.009);polygon([[sign*.69,1.04],[sign*.84,1.05],[sign*.83,.79],[sign*.70,.79]],m.black);for(let j=0;j<3;j++)box(.023,.042,.065,endX(1,sign*.77)+.022,.84+j*.067,sign*.77,m.headlight);polygon([[sign*.63,1.17],[sign*.86,1.16],[sign*.86,.90],[sign*.65,.90]],m.red,-1);frontLine([[sign*.68,1.14],[sign*.68,.93]],m.black,.012,-1);frontLine([[sign*.80,1.14],[sign*.80,.93]],m.black,.012,-1);}
  polygon([[-.71,.68],[.71,.68],[.66,.42],[-.66,.42]],m.black);frontLine([[-.70,.41],[.70,.41]],m.chrome,.025);
 }else if(s.dash==='camaro'){
  polygon([[-.79,.82],[.79,.82],[.70,.73],[-.70,.73]],m.black);lamps(.45,.87,.85,.050);bowtie(.782);polygon([[-.62,.67],[.62,.67],[.46,.38],[-.46,.38]],m.black);
  for(const sign of[-1,1]){polygon([[sign*.63,.68],[sign*.87,.73],[sign*.84,.45],[sign*.66,.43]],m.black);frontLine([[sign*.78,.65],[sign*.76,.48]],m.headlight,.007);for(const z of[sign*.54,sign*.73]){projector(z,.91,.057,m.red,-1);box(.025,.075,.13,endX(-1,z)-.018,.91,z,m.red);}for(const z of[sign*.63,sign*.75])cyl(.044,.10,rear-.02,.33,z,m.chrome,exterior,'x');}
  box(.37,.025,.33,1.27,.910,0,m.black);for(let j=0;j<4;j++)box(.012,.013,.25,1.14+j*.085,.926,0,m.black);
 }
}
