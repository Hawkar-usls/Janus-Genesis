(() => {
  'use strict';
  const nativeRAF=globalThis.requestAnimationFrame.bind(globalThis);
  const nativeCancel=globalThis.cancelAnimationFrame?globalThis.cancelAnimationFrame.bind(globalThis):null;
  const state={tier:'FULL_60',target_fps:60,min_interval_ms:1000/60,ema_cost_ms:0,last_present_ms:0,frames:0,hidden:false};
  const handles=new Map();let nextHandle=1;
  function chooseTier(){
    if(state.hidden){state.tier='HIDDEN_4';state.target_fps=4;state.min_interval_ms=250;return;}
    const c=state.ema_cost_ms;
    if(c>24){state.tier='SAFE_30';state.target_fps=30;state.min_interval_ms=1000/30;return;}
    if(c>15){state.tier='BALANCED_45';state.target_fps=45;state.min_interval_ms=1000/45;return;}
    state.tier='FULL_60';state.target_fps=60;state.min_interval_ms=1000/60;
  }
  function governedRAF(callback){
    const id=nextHandle++;
    const loop=now=>{
      if(!handles.has(id))return;
      const elapsed=now-state.last_present_ms;
      if(elapsed+0.2<state.min_interval_ms){handles.set(id,nativeRAF(loop));return;}
      state.last_present_ms=now;
      const start=performance.now();
      try{callback(now);}finally{
        const cost=Math.max(0,performance.now()-start);
        state.ema_cost_ms=state.frames?state.ema_cost_ms*0.9+cost*0.1:cost;
        state.frames++;
        chooseTier();
        handles.delete(id);
      }
    };
    handles.set(id,nativeRAF(loop));
    return id;
  }
  function governedCancel(id){const native=handles.get(id);handles.delete(id);if(nativeCancel&&native!==undefined)nativeCancel(native);}
  if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{state.hidden=!!document.hidden;chooseTier();});
  globalThis.requestAnimationFrame=governedRAF;
  if(nativeCancel)globalThis.cancelAnimationFrame=governedCancel;
  globalThis.GENESIS_FRAME_GOVERNOR_R0_5_2=Object.freeze({version:'0.5.2',getState:()=>({...state}),canonical_world_mutation:false,changes_generator_version:false});
})();