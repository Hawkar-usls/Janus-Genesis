(() => {
  'use strict';
  const SAFE_RIGHTS=new Set(['CC0','PUBLIC_DOMAIN','CC-BY','CC-BY-SA']);
  let activeAudio=null;
  let stopTimer=null;

  function safeRef(ref){
    return !!ref && ref.type==='audio' && SAFE_RIGHTS.has(String(ref.rights||'').toUpperCase()) && /^https:\/\//.test(String(ref.download_pointer||'')) && ref.binary_transport!=='SLIME';
  }
  function stop(){
    if(stopTimer!==null){clearTimeout(stopTimer);stopTimer=null;}
    if(activeAudio!==null){
      try{activeAudio.pause();activeAudio.src='';if(typeof activeAudio.load==='function')activeAudio.load();}catch(_err){}
      activeAudio=null;
    }
  }
  async function playRef(ref,options){
    const opts=options||{};
    const volume=Number.isFinite(Number(opts.volume))?Number(opts.volume):0.16;
    const maxSeconds=Number.isFinite(Number(opts.max_seconds))?Number(opts.max_seconds):12;
    if(!safeRef(ref))return {ok:false,reason:'AUDIO_REF_RIGHTS_OR_POINTER_REJECT'};
    if(!globalThis.GENESIS_AUDIO_RUNTIME || globalThis.GENESIS_AUDIO_RUNTIME.enabled!==true)return {ok:false,reason:'AUDIO_DISABLED'};
    stop();
    try{
      const audio=new Audio();
      audio.crossOrigin='anonymous';audio.preload='metadata';audio.volume=Math.max(0,Math.min(0.35,volume));audio.src=ref.download_pointer;
      activeAudio=audio;
      const materializer=globalThis.GENESIS_ASSET_MATERIALIZER_V3;
      if(materializer && typeof materializer.recordAttribution==='function')materializer.recordAttribution(ref);
      await audio.play();
      const bounded=Math.max(2,Math.min(20,maxSeconds));
      stopTimer=setTimeout(stop,bounded*1000);
      return {ok:true,provider_id:ref.provider_id,asset_id:ref.asset_id,rights:ref.rights,bounded_seconds:bounded};
    }catch(err){
      stop();
      return {ok:false,reason:'AUDIO_PROVIDER_PLAYBACK_FAILED:'+(err&&err.name?err.name:'Error')};
    }
  }
  function isActive(){return activeAudio!==null;}
  globalThis.GENESIS_AUDIO_ASSET_RUNTIME_R0_5_1=Object.freeze({version:'0.5.1',safe_rights:Object.freeze(Array.from(SAFE_RIGHTS)),playRef,stop,isActive,binary_bytes_through_slime:false,autoplay_without_user_audio_enable:false});
})();