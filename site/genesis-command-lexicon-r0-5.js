(() => {
  'use strict';
  const base=globalThis.GENESIS_COMMAND_BRIDGE_V3;if(!base)return;
  const JUMP=['jump','leap','прыгни','прыгай','прыжок','стрибни','стрибай','стрибок','skocz','skok','spring','springe','sprung','salta','salto','saute','saut'];
  const norm=v=>String(v||'').normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();
  const escRx=v=>String(v).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const has=(text,token)=>new RegExp(`(^|[^\\p{L}\\p{N}_])${escRx(token)}(?=$|[^\\p{L}\\p{N}_])`,'iu').test(text);
  const hashText=text=>{let h=0x811c9dc5;for(const ch of String(text)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193);}return(h>>>0).toString(16).padStart(8,'0');};
  const localCompile=raw=>{const text=norm(raw);if(JUMP.some(t=>has(text,t))){const rt=globalThis.GENESIS_WORLD_RUNTIME_V5||globalThis.GENESIS_WORLD_RUNTIME_V4;return{kind:'JUMP',action_seed:hashText(JSON.stringify(rt?.getCanonicalState?.()||{})+'|'+text),canonical_world_mutation:false};}return base.localCompile(raw);};
  globalThis.GENESIS_COMMAND_BRIDGE_V3=Object.freeze({version:'3.0.1+r0.5',healthCheck:base.healthCheck,executeText:base.executeText,configureEndpoint:base.configureEndpoint,localCompile,focusConsole:base.focusConsole,get online(){return base.online;},get endpoint(){return base.endpoint;},get health(){return base.health;}});
  globalThis.GENESIS_COMMAND_BRIDGE_V2=globalThis.GENESIS_COMMAND_BRIDGE_V3;
})();