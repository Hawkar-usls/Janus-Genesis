(() => {
  'use strict';
  const base=globalThis.GENESIS_SCENE_GRAPH_EXECUTOR_R0_5;if(!base)return;
  async function executeGraph(graph,options={}){
    const receipt=await base.executeGraph(graph,options);
    const player=globalThis.GENESIS_AUDIO_ASSET_RUNTIME_R0_5_1;
    if(player&&globalThis.GENESIS_AUDIO_RUNTIME?.enabled){
      for(const row of receipt.node_receipts||[]){
        if(row.family!=='SOUND'||row.status!=='APPLIED')continue;
        const ref=(row.asset_refs||[]).find(r=>r?.type==='audio');
        if(ref){const playback=await player.playRef(ref,{volume:.13,max_seconds:10});row.external_audio_playback=playback;break;}
      }
    }
    return receipt;
  }
  const api=Object.freeze({version:'0.5.1',limits:base.limits,validateGraph:base.validateGraph,verifyTransport:base.verifyTransport,executeGraph,structuralEqual:base.structuralEqual,canonicalHash:base.canonicalHash});
  globalThis.GENESIS_SCENE_GRAPH_EXECUTOR_R0_5_1=api;globalThis.GENESIS_SCENE_GRAPH_EXECUTOR_R0_5=api;globalThis.GENESIS_SCENE_GRAPH_EXECUTOR_R0_4=api;
})();