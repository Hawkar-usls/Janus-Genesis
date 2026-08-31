(() => {
  'use strict';

  const button = document.getElementById('audio-toggle');
  let enabled = false;
  let lastMutationCount = -1;
  let lastChunkKey = '';

  function hash(value){let h=0x811c9dc5;for(const ch of String(value)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193);}return h>>>0;}
  function worldState(){
    const rt=globalThis.GENESIS_WORLD_RUNTIME_V3;
    if(!rt)return {entropy:.2,depth:.1,portal_energy:.1,danger:.05,weather_intensity:.2};
    const s=rt.getCanonicalState(),p=s.player_position||{x:0,y:0},h=hash(`${Math.floor(p.x/10)},${Math.floor(p.y/10)}`);
    return {
      entropy: Math.min(1,.16+(s.explicit_world_mutations?.length||0)*.025),
      depth: Math.min(1,Math.hypot(p.x,p.y)/180),
      portal_energy: ((h>>>8)&255)/255*.55,
      danger: ((h>>>16)&255)/255*.32,
      weather_intensity: (h&255)/255*.58
    };
  }
  function forge(){return globalThis.GENESIS_AUDIO_FORGE||null;}
  function updateLabel(){if(button)button.textContent=`AUDIO: ${enabled?'ON':'OFF'}`;}

  async function toggle(){
    const f=forge();
    if(!f){button.textContent='AUDIO: UNAVAILABLE';return;}
    if(enabled){f.disable?.();enabled=false;updateLabel();return;}
    try{
      await f.enable?.({seed:'genesis-world-runtime-v3',world_state:worldState()});
      enabled=true;updateLabel();f.cue?.('discovery');
    }catch{enabled=false;button.textContent='AUDIO: BLOCKED';}
  }

  function tick(){
    if(!enabled)return;
    const f=forge(),rt=globalThis.GENESIS_WORLD_RUNTIME_V3;if(!f||!rt)return;
    const state=rt.getCanonicalState(),p=state.player_position||{x:0,y:0};
    f.setWorldState?.(worldState());
    const chunk=`${Math.floor(p.x/10)},${Math.floor(p.y/10)}`;
    if(lastChunkKey&&chunk!==lastChunkKey)f.cue?.('discovery');
    lastChunkKey=chunk;
    const count=state.explicit_world_mutations?.length||0;
    if(lastMutationCount>=0&&count>lastMutationCount)f.cue?.('portal_open');
    lastMutationCount=count;
  }

  button?.addEventListener('click',toggle);
  updateLabel();
  setInterval(tick,900);
  globalThis.GENESIS_AUDIO_RUNTIME=Object.freeze({toggle,get enabled(){return enabled;},worldState});
})();
