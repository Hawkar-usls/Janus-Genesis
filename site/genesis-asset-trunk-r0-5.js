(() => {
  'use strict';

  const KINDS=Object.freeze(['material','mesh','audio','mechanic']);
  const SAFE_RIGHTS=new Set(['CC0','PUBLIC_DOMAIN','CC-BY','CC-BY-SA']);
  const bridge=()=>globalThis.GENESIS_COMMAND_BRIDGE_V3;
  function endpoint(){return String(bridge()?.endpoint||'').replace(/\/+$/,'');}
  function isSafeRef(ref){return ref&&typeof ref==='object'&&typeof ref.provider_id==='string'&&typeof ref.asset_id==='string'&&typeof ref.source_url==='string'&&SAFE_RIGHTS.has(String(ref.rights||'').toUpperCase())&&ref.binary_transport!=='SLIME';}
  async function search(kind,query,{limit=6}={}){
    const k=String(kind||'').toLowerCase();if(!KINDS.includes(k))throw new Error('ASSET_TRUNK_KIND_INVALID');
    const q=String(query||'').trim().slice(0,240);if(!q)return{ok:false,reason:'ASSET_QUERY_REQUIRED',refs:[]};
    const ep=endpoint();if(!bridge()?.online||!ep)return{ok:true,mode:'PROCEDURAL_OR_LOCAL_RECIPE_FALLBACK',refs:[],providers:[]};
    try{
      const url=ep+`/v1/genesis/assets/federated/search?kind=${encodeURIComponent(k)}&q=${encodeURIComponent(q)}&limit=${Math.max(1,Math.min(12,Number(limit)||6))}`;
      const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(9000)});if(!r.ok)throw new Error(`ASSET_FEDERATION_HTTP_${r.status}`);
      const data=await r.json();if(data?.schema!=='janus.genesis.asset_federation.search.v1')throw new Error('ASSET_FEDERATION_SCHEMA_INVALID');
      const refs=(Array.isArray(data.results)?data.results:[]).filter(isSafeRef).slice(0,12);
      return{ok:true,mode:refs.length?'FEDERATED_RIGHTS_GATED_REFERENCE':'PROCEDURAL_OR_LOCAL_RECIPE_FALLBACK',refs,providers:Array.isArray(data.providers)?data.providers:[]};
    }catch(e){return{ok:true,mode:`FEDERATION_DEGRADED:${e.message}`,refs:[],providers:[]};}
  }
  const resolveMaterial=(query,opts)=>search('material',query,opts);
  const resolveMesh=(query,opts)=>search('mesh',query,opts);
  const resolveAudio=(query,opts)=>search('audio',query,opts);
  const resolveMechanic=(query,opts)=>search('mechanic',query,opts);
  globalThis.GENESIS_ASSET_TRUNK_R0_5=Object.freeze({version:'0.5.0',kinds:KINDS,search,resolveMaterial,resolveMesh,resolveAudio,resolveMechanic,binary_bytes_through_slime:false,foreign_code_execution:false});
})();