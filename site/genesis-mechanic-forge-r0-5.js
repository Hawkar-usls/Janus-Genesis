(() => {
  'use strict';

  const ALLOWED=new Set(['HINGE','DOOR','ELEVATOR','ROTATOR','OSCILLATOR','PARTICLE_EMITTER','BREAKABLE','BUOYANT','VEHICLE_WHEEL','NPC_PATH','TRIGGER_ZONE','ANIMATION_CLIP','COLLIDER_PROFILE']);
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  function recipe(kind,params={},source='GENESIS_LOCAL_RECIPE'){
    const k=String(kind||'').toUpperCase();
    if(!ALLOWED.has(k))throw new Error('MECHANIC_KIND_NOT_ALLOWLISTED');
    const clean={};
    for(const [key,value] of Object.entries(params||{})){
      if(!/^[a-zA-Z][a-zA-Z0-9_]{0,47}$/.test(key))throw new Error('MECHANIC_PARAM_KEY_INVALID');
      if(typeof value==='number'){if(!Number.isFinite(value))throw new Error('MECHANIC_PARAM_NUMBER_INVALID');clean[key]=value;continue;}
      if(typeof value==='boolean'||value===null){clean[key]=value;continue;}
      if(typeof value==='string'){clean[key]=value.slice(0,160);continue;}
      throw new Error('MECHANIC_PARAM_TYPE_FORBIDDEN');
    }
    return Object.freeze({schema:'janus.genesis.mechanic_recipe.v1',kind:k,params:Object.freeze(clean),source:String(source).slice(0,120),remote_code_executed:false});
  }
  function forStructure(kind,seed='0'){
    const k=String(kind||'generic_structure').toLowerCase(),s=parseInt(String(seed).slice(0,8),16)||1;
    if(k==='lighthouse')return[recipe('ROTATOR',{axis:'Z',rpm:clamp(4+(s%8),4,12),target:'BEACON_LIGHT'}),recipe('COLLIDER_PROFILE',{shape:'TAPERED_TOWER'})];
    if(k==='portal')return[recipe('OSCILLATOR',{frequency_hz:.35+(s%30)/100,amplitude:.22,target:'EMISSIVE'}),recipe('TRIGGER_ZONE',{radius:1.15,event:'PORTAL_ENTER'})];
    if(k==='house'||k==='castle')return[recipe('HINGE',{axis:'Z',degrees:92,target:'PRIMARY_DOOR'}),recipe('COLLIDER_PROFILE',{shape:'ARCHITECTURE_STATIC'})];
    if(k==='bridge'||k==='wall'||k==='tower'||k==='statue')return[recipe('COLLIDER_PROFILE',{shape:'ARCHITECTURE_STATIC'})];
    if(k==='tree')return[recipe('COLLIDER_PROFILE',{shape:'VEGETATION_TRUNK'})];
    return[recipe('COLLIDER_PROFILE',{shape:'GENERIC_STATIC'})];
  }
  function phase(mechanic,seconds){
    if(!mechanic||!ALLOWED.has(mechanic.kind))return 0;
    if(mechanic.kind==='ROTATOR')return seconds*(Number(mechanic.params.rpm)||6)*Math.PI*2/60;
    if(mechanic.kind==='OSCILLATOR')return Math.sin(seconds*(Number(mechanic.params.frequency_hz)||.5)*Math.PI*2)*(Number(mechanic.params.amplitude)||.2);
    return 0;
  }
  globalThis.GENESIS_MECHANIC_FORGE_R0_5=Object.freeze({version:'0.5.0',allowed:Object.freeze([...ALLOWED]),recipe,forStructure,phase,foreign_code_execution:false});
})();