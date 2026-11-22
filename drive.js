import {createDrivingClassroom} from 'driving';import {FLEET} from 'driving-fleet';
const launch=document.getElementById('launch');let instance=null;function start(){launch.hidden=true;instance=createDrivingClassroom({fleet:FLEET,onExit:()=>{instance=null;launch.hidden=false;}});window.autoverseDriving=instance;}
launch.onclick=start;start();
