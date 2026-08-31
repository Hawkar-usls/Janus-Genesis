(() => {
  'use strict';
  const SAFE_RIGHTS=new Set(['CC0','PUBLIC_DOMAIN','CC-BY','CC-BY-SA']);
  let active=null,stopTimer=null;
  function safe(ref){return ref&&ref.type==='audio'&&SAFE_RIGHTS.has(String(ref.rights||'').toUpperCase())&&/^https:\/\//.test(String(ref.download_pointer||''))&&ref.binary_transport!=='SLIME';}
  function stop(){if(stopTimer){clearTimeout(stopTimer);stopTimer=null;}if(active){try{active.pause();active.src='';active.load?.();}catch{}active=null;}}
  async function playRef(ref,{volume=.16,max_seconds=12}={}){if(!safe(ref))return{ok:false,reason:'AUDIO_REF_RIGHTS_OR_POINTER_REJECT'};if(!globalThis.GENESIS_AUDIO_RUNTIME?.enabled)return{ok:false,reason:'AUDIO_DISABLED'};stop();try{const audio=new Audio();audio.crossOrigin='anonymous';audio.preload='metadata';audio.volume=Math.max(0,Math.min(.35,Number(volume)||.16));audio.src=ref.download_pointer;active=audio;globalThis.GENESIS_ASSET_MATERIALIZER_V3?.recordAttribution?.(ref);await audio.play();stopTimer=setTimeout(stop,Math.max(2,Math.min(20,Number(max_seconds)||12))*1000);return{ok:true,provider_id:ref.provider_id,asset_id:ref.asset_id,rights:ref.rights,bounded_seconds:Math.max(2,Math.min(20,Number(max_seconds)||12)};}catch(e){stop();return{ok:false,reason:`AUDIO_PROVIDER_PLAYBACK_FAILED:${e?.name||'Error'}`};}}
  globalThis.GENESIS_AUDIO_ASSET_RUNTIME_R0_5_1=Object.freeze({version:'0.5.1',safe_rights:Object.freeze([...SAFE_RIGHTS]),playRef,stop,get active(){return!!active;},binary_bytes_through_slime:false,autoplay_without_user_audio_enable:false});
})();