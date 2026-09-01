(() => {
  'use strict';

  const VERSION='0.7.0';
  const CONTRACT_PATH='contracts/GENESIS_PLAYER_MIRROR_R0_7.json';
  const STORAGE_KEY='janus.genesis.player_mirror_r0_7.v1';
  const PROFILE_ORDER=Object.freeze(['ORIGIN','JANUS_16','NOCTURNE','AETHER','EMBER']);
  const PROFILES=Object.freeze({
    ORIGIN:Object.freeze({runtime_mirror:'ORIGIN',postprocess:'NONE',logical_pixel_css:1,frame_cap:0}),
    JANUS_16:Object.freeze({runtime_mirror:'ORIGIN',postprocess:'JANUS_16',logical_pixel_css:4,frame_cap:20}),
    NOCTURNE:Object.freeze({runtime_mirror:'NOCTURNE',postprocess:'NONE',logical_pixel_css:1,frame_cap:0}),
    AETHER:Object.freeze({runtime_mirror:'AETHER',postprocess:'NONE',logical_pixel_css:1,frame_cap:0}),
    EMBER:Object.freeze({runtime_mirror:'EMBER',postprocess:'NONE',logical_pixel_css:1,frame_cap:0})
  });

  // Independent Genesis palette: mechanism inspired by constrained-palette
  // rendering research, not copied from Bad Pixels, C64 ROMs, or any game asset.
  const JANUS_16_HEX=Object.freeze([
    '#020406','#07131b','#153b4c','#1f4a34',
    '#346b48','#616765','#756b50','#69623e',
    '#8b3f35','#b56a3b','#d5a95f','#d6d9c5',
    '#73ecff','#8ef7b8','#9b6cff','#f2f6ff'
  ]);

  const parseHex=hex=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)];
  const JANUS_16=Object.freeze(JANUS_16_HEX.map(parseHex));
  const LUT=new Uint8Array(32768);
  for(let r=0;r<32;r++)for(let g=0;g<32;g++)for(let b=0;b<32;b++){
    const rr=r*8+4,gg=g*8+4,bb=b*8+4;
    let best=0,bestDistance=Infinity;
    for(let i=0;i<JANUS_16.length;i++){
      const p=JANUS_16[i],dr=rr-p[0],dg=gg-p[1],db=bb-p[2],distance=dr*dr+dg*dg+db*db;
      if(distance<bestDistance){bestDistance=distance;best=i;}
    }
    LUT[(r<<10)|(g<<5)|b]=best;
  }

  const source=document.getElementById('genesis-world');
  const runtime=globalThis.GENESIS_WORLD_RUNTIME_V5;
  if(!source||!runtime){
    console.error('[GENESIS MIRROR R0.7] WORLD_RUNTIME_UNAVAILABLE');
    return;
  }

  let current='ORIGIN';
  let output=null;
  let outputCtx=null;
  let lastFrameAt=0;
  let lastProof=null;
  let control=null;

  function readSelection(){
    try{
      const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');
      const profile=String(parsed?.profile||'ORIGIN').toUpperCase();
      return PROFILES[profile]?profile:'ORIGIN';
    }catch{return'ORIGIN';}
  }

  function persistSelection(profile){
    localStorage.setItem(STORAGE_KEY,JSON.stringify({
      schema:'janus.genesis.player_mirror_state.v1',
      version:VERSION,
      scope:'PLAYER_LOCAL_PRESENTATION',
      profile
    }));
  }

  function canonicalSnapshot(){
    return {
      fact_hash:String(runtime.getFactHash()),
      canonical_state:runtime.getCanonicalState()
    };
  }

  function canonicalEqual(a,b){
    return a.fact_hash===b.fact_hash&&JSON.stringify(a.canonical_state)===JSON.stringify(b.canonical_state);
  }

  function ensureOutput(){
    if(output)return output;
    output=document.createElement('canvas');
    output.id='genesis-player-mirror-output-r0-7';
    output.setAttribute('aria-hidden','true');
    output.style.position='fixed';
    output.style.inset='0';
    output.style.width='100vw';
    output.style.height='100vh';
    output.style.pointerEvents='none';
    output.style.imageRendering='pixelated';
    output.style.zIndex='0';
    output.hidden=true;
    source.insertAdjacentElement('afterend',output);
    outputCtx=output.getContext('2d',{alpha:false,willReadFrequently:true});
    if(!outputCtx)throw new Error('MIRROR_2D_CONTEXT_UNAVAILABLE');
    return output;
  }

  function setPresentationSurface(profile){
    const spec=PROFILES[profile];
    if(spec.postprocess==='JANUS_16'){
      ensureOutput().hidden=false;
      source.style.visibility='hidden';
    }else{
      source.style.visibility='';
      if(output)output.hidden=true;
    }
    document.documentElement.dataset.genesisMirrorHardware=profile.toLowerCase();
  }

  function updateControl(){
    if(!control)return;
    control.textContent=`MIRROR ${current.replace('_',' ')}`;
    control.dataset.profile=current;
    control.title=current==='JANUS_16'
      ?'JANUS_16: Player-local low-resolution 16-color perceptual hardware'
      :'Player-local presentation profile; canonical world remains unchanged';
  }

  function installControl(){
    if(document.getElementById('mirror-hardware-toggle')){
      control=document.getElementById('mirror-hardware-toggle');
      updateControl();
      return;
    }
    const anchor=document.getElementById('mirror-chip');
    control=document.createElement('button');
    control.type='button';
    control.id='mirror-hardware-toggle';
    control.className='status-chip';
    control.style.cursor='pointer';
    control.addEventListener('click',()=>cycle());
    if(anchor)anchor.insertAdjacentElement('afterend',control);
    else document.body.appendChild(control);
    updateControl();
  }

  function applyProfile(requested,{persist=true}={}){
    const profile=String(requested||'').toUpperCase();
    const spec=PROFILES[profile];
    if(!spec)return{ok:false,reason:'MIRROR_PROFILE_NOT_ALLOWLISTED',profile};

    const before=canonicalSnapshot();
    const previousPresentation=runtime.getPresentationState().mirror_profile;
    const previousProfile=current;
    const changed=previousPresentation!==spec.runtime_mirror;
    if(changed&&!runtime.setMirror(spec.runtime_mirror))return{ok:false,reason:'RUNTIME_MIRROR_REJECTED',profile};
    const after=canonicalSnapshot();

    if(!canonicalEqual(before,after)){
      if(changed)runtime.setMirror(previousPresentation);
      current=previousProfile;
      setPresentationSurface(previousProfile);
      updateControl();
      console.error('[GENESIS MIRROR R0.7] CANONICAL_INVARIANCE_BREACH',{before,after,requested:profile});
      return{ok:false,reason:'CANONICAL_INVARIANCE_BREACH',profile,before,after};
    }

    current=profile;
    setPresentationSurface(profile);
    if(persist)persistSelection(profile);
    updateControl();
    lastProof=Object.freeze({
      profile,
      fact_hash_before:before.fact_hash,
      fact_hash_after:after.fact_hash,
      chronicle_tip_before:before.canonical_state?.chronicle_tip_hash||'GENESIS',
      chronicle_tip_after:after.canonical_state?.chronicle_tip_hash||'GENESIS',
      canonical_equal:true
    });
    globalThis.dispatchEvent(new CustomEvent('genesis:mirror-changed',{detail:{profile,proof:lastProof}}));
    return{ok:true,profile,proof:lastProof};
  }

  function cycle(){
    const index=PROFILE_ORDER.indexOf(current);
    return applyProfile(PROFILE_ORDER[(index+1)%PROFILE_ORDER.length]);
  }

  function renderJanus16(now){
    if(current!=='JANUS_16'||!output||output.hidden)return;
    if(globalThis.GENESIS_BIRTH_R0_6?.isUnborn?.())return;
    const spec=PROFILES.JANUS_16;
    const interval=1000/spec.frame_cap;
    if(now-lastFrameAt<interval)return;
    lastFrameAt=now;

    const rect=source.getBoundingClientRect();
    const width=Math.max(1,Math.ceil(rect.width/spec.logical_pixel_css));
    const height=Math.max(1,Math.ceil(rect.height/spec.logical_pixel_css));
    if(output.width!==width||output.height!==height){output.width=width;output.height=height;outputCtx.imageSmoothingEnabled=false;}
    outputCtx.imageSmoothingEnabled=false;
    outputCtx.drawImage(source,0,0,width,height);
    const image=outputCtx.getImageData(0,0,width,height),data=image.data;
    for(let i=0;i<data.length;i+=4){
      const paletteIndex=LUT[((data[i]>>3)<<10)|((data[i+1]>>3)<<5)|(data[i+2]>>3)];
      const color=JANUS_16[paletteIndex];
      data[i]=color[0];data[i+1]=color[1];data[i+2]=color[2];
    }
    outputCtx.putImageData(image,0,0);
  }

  function frame(now){
    renderJanus16(now);
    requestAnimationFrame(frame);
  }

  installControl();
  applyProfile(readSelection(),{persist:false});
  requestAnimationFrame(frame);

  globalThis.GENESIS_PLAYER_MIRROR_R0_7=Object.freeze({
    version:VERSION,
    contract:CONTRACT_PATH,
    profiles:PROFILE_ORDER,
    palette:Object.freeze([...JANUS_16_HEX]),
    getProfile:()=>current,
    getProof:()=>lastProof,
    setProfile:profile=>applyProfile(profile),
    cycle
  });
})();
