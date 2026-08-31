(() => {
  'use strict';

  const SAVE_KEY = 'janus.genesis.world_shell_r0.save.v1';
  const WORLD_SEED = 'genesis-one-world-r0';
  const layer = document.createElement('canvas');
  layer.id = 'genesis-material-layer';
  layer.setAttribute('aria-hidden', 'true');
  Object.assign(layer.style, {
    position: 'fixed', inset: '0', zIndex: '2', pointerEvents: 'none', width: '100vw', height: '100vh'
  });
  const worldCanvas = document.getElementById('genesis-world');
  worldCanvas?.insertAdjacentElement('afterend', layer);
  const ctx = layer.getContext('2d');
  const cache = new Map();
  let viewport = {w: innerWidth, h: innerHeight, dpr: 1};

  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function hashString(value){let h=0x811c9dc5;for(const ch of String(value)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193);}return h>>>0;}
  function mix32(v){let x=v>>>0;x^=x>>>16;x=Math.imul(x,0x7feb352d);x^=x>>>15;x=Math.imul(x,0x846ca68b);x^=x>>>16;return x>>>0;}
  const SEED=hashString(WORLD_SEED);
  function unitHash(x,y,s=0){return mix32(SEED^Math.imul(x|0,0x1f123bb5)^Math.imul(y|0,0x5f356495)^(s>>>0))/0xffffffff;}
  function smooth(t){return t*t*(3-2*t);}
  function lerp(a,b,t){return a+(b-a)*t;}
  function valueNoise(x,y,scale,salt){const gx=x/scale,gy=y/scale,x0=Math.floor(gx),y0=Math.floor(gy),tx=smooth(gx-x0),ty=smooth(gy-y0);const a=lerp(unitHash(x0,y0,salt),unitHash(x0+1,y0,salt),tx),b=lerp(unitHash(x0,y0+1,salt),unitHash(x0+1,y0+1,salt),tx);return lerp(a,b,ty);}
  function fbm(x,y,s){return valueNoise(x,y,34,s)*.46+valueNoise(x,y,17,s+101)*.27+valueNoise(x,y,8.5,s+211)*.17+valueNoise(x,y,4.25,s+307)*.10;}
  function terrainZ(x,y){const e=clamp(.12+fbm(x,y,0x1201)*.72+Math.max(0,1-Math.hypot(x,y)/24)*.18,0,1);return(e-.28)*5.5;}

  function resize(){const dpr=Math.min(2,devicePixelRatio||1),w=innerWidth,h=innerHeight;viewport={w,h,dpr};const bw=Math.floor(w*dpr),bh=Math.floor(h*dpr);if(layer.width!==bw||layer.height!==bh){layer.width=bw;layer.height=bh;layer.style.width=`${w}px`;layer.style.height=`${h}px`;ctx.setTransform(dpr,0,0,dpr,0,0);}}

  function loadSave(){try{return JSON.parse(localStorage.getItem(SAVE_KEY)||'null');}catch{return null;}}
  function camera(state,presentation){const p=state.player_position||{x:.5,y:.5};const ground=terrainZ(p.x,p.y)+1.75,yaw=Number(presentation.camera_heading)||0,pitch=Number(presentation.camera_pitch)||-.62,roll=Number(presentation.camera_roll)||0,d=Number(presentation.camera_distance)||12; if(presentation.camera_mode==='FIRST_PERSON')return{x:p.x,y:p.y,z:ground,yaw,pitch,roll,fov:1.05};if(presentation.camera_mode==='THIRD_PERSON'){const cp=Math.cos(pitch);return{x:p.x-Math.cos(yaw)*d*cp,y:p.y-Math.sin(yaw)*d*cp,z:ground-Math.sin(pitch)*d*.8+2,yaw,pitch,roll,fov:1};}return{x:p.x-Math.cos(yaw)*(d+8),y:p.y-Math.sin(yaw)*(d+8),z:ground+15,yaw,pitch:-.68,roll:0,fov:.82};}
  function project(wx,wy,wz,cam){let x=wx-cam.x,y=wy-cam.y,z=wz-cam.z;const cy=Math.cos(-cam.yaw),sy=Math.sin(-cam.yaw);let x1=x*cy-y*sy,y1=x*sy+y*cy,z1=z;const cp=Math.cos(-cam.pitch),sp=Math.sin(-cam.pitch);let y2=y1*cp-z1*sp,z2=y1*sp+z1*cp,x2=x1;const cr=Math.cos(-cam.roll),sr=Math.sin(-cam.roll);let x3=x2*cr-z2*sr,z3=x2*sr+z2*cr;if(y2<=.15)return null;const focal=(viewport.h*.5)/Math.tan(cam.fov*.5);return{x:viewport.w*.5+x3*focal/y2,y:viewport.h*.52-z3*focal/y2,d:y2,f:focal};}

  function imageFor(ref){const url=String(ref?.download_pointer||'');if(!/^https:\/\//i.test(url))return null;let item=cache.get(url);if(item)return item;const img=new Image();item={status:'loading',img,url};cache.set(url,item);img.crossOrigin='anonymous';img.referrerPolicy='no-referrer';img.decoding='async';img.onload=()=>{item.status='ready';};img.onerror=()=>{item.status='failed';};img.src=url;return item;}
  function dna(ref){const id=`${ref?.provider_id||''}:${ref?.asset_id||''}:${ref?.download_pointer||''}`;const h=hashString(id);return{hash:h.toString(16).padStart(8,'0'),roughness:.22+((h>>>8)&255)/255*.63,scale:.5+((h>>>16)&255)/255*1.8};}

  function drawMaterialPlate(m,cam){const ref=(m.asset_refs||[]).find(r=>r?.rights==='CC0'&&/^https:\/\//i.test(String(r.download_pointer||'')));if(!ref)return;const p=project(m.x,m.y,terrainZ(m.x,m.y)+1.5,cam);if(!p||p.x<-150||p.x>viewport.w+150||p.y<-150||p.y>viewport.h+150)return;const item=imageFor(ref),mat=dna(ref);const size=clamp(p.f/p.d*.55,18,120)*mat.scale*.65;ctx.save();ctx.globalAlpha=.72;ctx.translate(p.x,p.y);ctx.rotate((mat.roughness-.5)*.12);ctx.beginPath();ctx.roundRect(-size*.5,-size*.5,size,size,Math.min(10,size*.12));ctx.clip();if(item?.status==='ready'){ctx.drawImage(item.img,-size*.5,-size*.5,size,size);}else{const hue=parseInt(mat.hash.slice(0,4),16)%360;ctx.fillStyle=`hsl(${hue} 38% 42%)`;ctx.fillRect(-size*.5,-size*.5,size,size);}ctx.globalCompositeOperation='screen';ctx.fillStyle='rgba(115,236,255,.10)';ctx.fillRect(-size*.5,-size*.5,size,size);ctx.restore();ctx.save();ctx.strokeStyle='rgba(142,247,184,.45)';ctx.lineWidth=1;ctx.strokeRect(p.x-size*.5,p.y-size*.5,size,size);ctx.font='600 8px ui-monospace,monospace';ctx.fillStyle='rgba(210,240,230,.75)';ctx.fillText(`KRR ${mat.hash}`,p.x-size*.5,p.y+size*.5+11);ctx.restore();}

  function frame(){resize();ctx.clearRect(0,0,viewport.w,viewport.h);const rt=globalThis.GENESIS_WORLD_RUNTIME_V3;if(rt){const state=rt.getCanonicalState(),presentation=rt.getPresentationState(),cam=camera(state,presentation);for(const m of state.explicit_world_mutations||[])if(m.type==='GENERATED_STRUCTURE'&&Array.isArray(m.asset_refs)&&m.asset_refs.length)drawMaterialPlate(m,cam);}requestAnimationFrame(frame);}
  requestAnimationFrame(frame);

  globalThis.GENESIS_ASSET_MATERIALIZER=Object.freeze({version:'1.0.0',materialDNA:dna,get cacheSize(){return cache.size;}});
})();
