(() => {
  'use strict';

  const REQUEST_SCHEMA='janus.genesis.api.request.v1';
  const ENDPOINT_KEY='janus.genesis.api.endpoint.v1';
  const MAX_TEXT=2000;
  const $=id=>document.getElementById(id);
  const runtime=()=>globalThis.GENESIS_WORLD_RUNTIME_V3;
  let endpoint='';
  let online=false;
  let lastHealth=null;
  let requestCounter=0;

  const LEX={
    create:['build','create','make','construct','place','построй','построить','создай','создать','сделай','поставь','размести','побудуй','створи','зроби','розмісти','zbuduj','stworz','postaw','baue','bauen','erschaffe','construye','crear','crea','construis','cree','creer'],
    move:['go','walk','move','travel','explore','wander','иди','идти','двигай','пройди','беги','исследуй','броди','йди','рухайся','біжи','досліджуй','мандруй','idz','rusz','biegnij','eksploruj','geh','gehe','lauf','erkunde','camina','muevete','explora','marche','deplace'],
    back:['return','home','hearth','вернись','домой','к огню','к костру','повернись','додому','до вогню','wroc','domu','ognia','zuruck','heim','regresa','casa','retourne','maison'],
    mark:['mark','sign','метка','метку','знак','мітка','познач','znak','markierung','zeichen','marca','senal','marque','signe']
  };
  const DIR={N:['north','север','північ','polnoc','norden','norte','nord'],NE:['northeast','north east','северо-вост','північний схід','nordost','noreste','nord-est'],E:['east','восток','схід','wschod','osten','este','est'],SE:['southeast','south east','юго-вост','південний схід','sudost','sureste','sud-est'],S:['south','юг','південь','poludnie','suden','sur','sud'],SW:['southwest','south west','юго-зап','південний захід','sudwest','suroeste','sud-ouest'],W:['west','запад','захід','zachod','westen','oeste','ouest'],NW:['northwest','north west','северо-зап','північний захід','nordwest','noroeste','nord-ouest']};
  const CAM={FIRST_PERSON:['first person','1st person','первое лицо','від першої особи','pierwsza osoba','ego perspektive','primera persona','premiere personne'],THIRD_PERSON:['third person','3rd person','третье лицо','від третьої особи','trzecia osoba','dritte person','tercera persona','troisieme personne'],ISOMETRIC:['isometric','isometry','изометр','ізометр','izometr','isometrisch','isometrica','isometrique']};
  const MIR={ORIGIN:['origin','исток','початок'],NOCTURNE:['nocturne','ноктюрн'],AETHER:['aether','ether','эфир','ефір','аэтер'],EMBER:['ember','угли','пепел','жар','попіл']};
  const KIND={lighthouse:['lighthouse','маяк','latarnia','leuchtturm','faro','phare'],bridge:['bridge','мост','міст','most','brucke','puente','pont'],tower:['tower','башн','веж','wieza','turm','torre','tour'],house:['house','home','дом','будинок','haus','casa','maison'],wall:['wall','стен','стіна','sciana','mauer','muro','mur'],portal:['portal','портал'],tree:['tree','дерев','drzew','baum','arbol','arbre'],statue:['statue','стату','памятник','пам\'ятник','pomnik']};

  function norm(v){return String(v||'').normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();}
  function has(text,list){return list.some(v=>text.includes(v));}
  function matchMap(text,map){for(const [key,list] of Object.entries(map))if(has(text,list))return key;return null;}
  function concept(text){let s=norm(text);for(const list of Object.values(LEX))for(const t of list)s=s.replaceAll(t,' ');for(const list of Object.values(DIR))for(const t of list)s=s.replaceAll(t,' ');s=s.replace(/\b\d+\b/g,' ').replace(/[^\p{L}\p{N}_\- ']+/gu,' ').replace(/\s+/g,' ').trim();return s.slice(0,96)||'generated structure';}
  function kindFor(c){for(const [k,list] of Object.entries(KIND))if(has(c,list))return k;return'generic_structure';}
  function localCompile(raw){const text=norm(raw),camera=matchMap(text,CAM),mirror=matchMap(text,MIR),direction=matchMap(text,DIR);if(camera)return{kind:'SET_CAMERA',camera};if(mirror)return{kind:'SET_MIRROR',mirror};if(has(text,LEX.back))return{kind:'RETURN_TO_HEARTH'};if(has(text,LEX.mark)&&!has(text,LEX.create))return{kind:'PLACE_MARK',label:raw.slice(0,64)};if(has(text,LEX.create)){const c=concept(text);return{kind:'GENERATE_STRUCTURE',concept:c,structure_kind:kindFor(c),action_seed:hashText(JSON.stringify(runtime()?.getCanonicalState()||{})+'|'+text),placement:'IN_FRONT_OF_PLAYER'};}if(has(text,LEX.move)||direction){const m=text.match(/\b(\d{1,3})\b/);return{kind:'MOVE',direction:direction||'FORWARD',steps:Math.max(1,Math.min(64,m?+m[1]:1))};}return{kind:'UNRESOLVED',reason:'LOCAL_FALLBACK_NO_MATCH'};}
  function hashText(text){let h=0x811c9dc5;for(const ch of String(text)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193);}return(h>>>0).toString(16).padStart(8,'0');}

  function apiBase(){return endpoint.replace(/\/+$/,'');}
  async function healthCheck(){
    if(!endpoint){setStatus(false,'NO ENDPOINT');return false;}
    try{const r=await fetch(apiBase()+'/v1/health',{cache:'no-store',signal:AbortSignal.timeout(2500)});if(!r.ok)throw new Error(`HTTP ${r.status}`);const data=await r.json();online=data?.janus_api_available===true&&data?.genesis_intent_available===true;lastHealth=data;setStatus(online,online?'JANUS HOME ONLINE':'JANUS HEALTH REJECT');return online;}catch(e){online=false;lastHealth=null;setStatus(false,`OFFLINE ${e.name==='TimeoutError'?'TIMEOUT':'NO ROUTE'}`);return false;}
  }
  function setStatus(ok,text){const s=$('janus-api-status');if(s){s.textContent=text;s.classList.toggle('safe',ok);s.classList.toggle('warn',!ok);}const m=$('world-mode');if(m)m.textContent=ok?'JANUS-ROUTED':'LOCAL DEGRADED';}

  function payloadFor(text){return{schema:REQUEST_SCHEMA,request_id:`genesis-${Date.now()}-${++requestCounter}`,player_text:text,language_hint:navigator.language||null,canonical_world_state:runtime().getCanonicalState(),presentation:runtime().getPresentationState(),capabilities:{runtime:'GENESIS_WORLD_RUNTIME_V3',asset_trunk:true,cameras:['FIRST_PERSON','THIRD_PERSON','ISOMETRIC']}};}
  async function janusCompile(text){const r=await fetch(apiBase()+'/v1/genesis/intent',{method:'POST',headers:{'Content-Type':'application/json','X-Janus-Request-Id':`g-${Date.now()}`},body:JSON.stringify(payloadFor(text)),signal:AbortSignal.timeout(7000)});if(!r.ok)throw new Error(`JANUS_API_HTTP_${r.status}`);const data=await r.json();if(data?.schema!=='janus.genesis.api.response.v1'||!data.intent_plan)throw new Error('JANUS_RESPONSE_SCHEMA_INVALID');if(data.authority?.janus_api_is_world_authority!==false||data.authority?.genesis_validator_required!==true)throw new Error('JANUS_AUTHORITY_BOUNDARY_INVALID');return data;}

  async function assetSearch(query,type){if(!online)return[];try{const url=apiBase()+`/v1/genesis/assets/search?q=${encodeURIComponent(query)}&type=${encodeURIComponent(type)}&limit=4`;const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)return[];const d=await r.json();if(d.provider_id!=='poly_haven'||d.rights_gate!=='PROVIDER_WIDE_CC0_ASSETS')return[];return Array.isArray(d.results)?d.results:[];}catch{return[];}}
  async function assetFiles(assetId){if(!online)return[];try{const r=await fetch(apiBase()+`/v1/genesis/assets/files/${encodeURIComponent(assetId)}`,{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)return[];const d=await r.json();if(d.provider_id!=='poly_haven'||d.rights!=='CC0')return[];return Array.isArray(d.files)?d.files:[];}catch{return[];}}
  function preferredFile(files){const images=files.filter(f=>/\.(?:jpg|jpeg|png|webp)$/i.test(String(f.url||'')));const light=images.filter(f=>(Number(f.size)||1e18)<8_000_000);return(light[0]||images[0]||files[0]||null);}
  async function resolveAssets(intent){
    if(intent.kind!=='GENERATE_STRUCTURE')return[];
    const q=intent.concept||intent.structure_kind||'stone';
    const [textures,models]=await Promise.all([assetSearch(q,'textures'),assetSearch(q,'models')]);
    const refs=[];
    for(const row of [textures[0],models[0]].filter(Boolean)){
      const files=await assetFiles(row.asset_id),file=preferredFile(files);
      refs.push({provider_id:'poly_haven',asset_id:row.asset_id,name:row.name,type:row.type,rights:'CC0',source_url:row.source_url,download_pointer:file?.url||null,size:file?.size||null});
    }
    renderAssets(refs);
    return refs;
  }
  function renderAssets(refs){const box=$('asset-trunk-results');if(!box)return;box.innerHTML='';if(!refs.length){box.textContent=online?'NO MATCH / PROCEDURAL FALLBACK':'JANUS OFFLINE / PROCEDURAL FALLBACK';return;}for(const a of refs){const item=document.createElement('div');item.className='asset-hit';item.innerHTML=`<strong>${escapeHtml(a.name||a.asset_id)}</strong><span>${escapeHtml(a.type||'asset')} · CC0 · Poly Haven</span><code>${escapeHtml(a.asset_id)}</code>`;box.append(item);}const count=$('asset-count');if(count)count.textContent=String(refs.length);}
  function escapeHtml(v){return String(v).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}

  async function executeText(text){
    const raw=String(text||'').trim();if(!raw||raw.length>MAX_TEXT)return;
    const result=$('action-result'),planEl=$('action-plan'),button=$('action-submit');button.disabled=true;result.textContent='JANUS ROUTING…';
    let response=null,intent=null,mode='LOCAL DEGRADED';
    try{
      if(online){response=await janusCompile(raw);intent=response.intent_plan;mode='JANUS HOME';}
      else intent=localCompile(raw);
      if(intent.kind==='UNRESOLVED'){planEl.textContent=`UNRESOLVED · ${intent.reason||'NO MECHANIC'}`;result.textContent='Команда не материализована: JANUS не выдал bounded mechanic.';return;}
      planEl.textContent=`${mode} → ${intent.kind}${intent.structure_kind?' / '+intent.structure_kind:''}`;
      const asset_refs=await resolveAssets(intent);
      const exec=runtime().executeIntent(intent,{receipt_hash:response?.receipt_hash||null,asset_refs});
      if(!exec?.ok)throw new Error(exec?.reason||'GENESIS_VALIDATOR_REJECT');
      result.textContent=intent.kind==='GENERATE_STRUCTURE'?`MATERIALIZED: ${intent.concept} · KRR recipe · assets ${asset_refs.length}`:`EXECUTED: ${intent.kind}`;
    }catch(e){result.textContent=`REJECTED / DEGRADED: ${e.message}`;if(online){online=false;setStatus(false,'JANUS ROUTE LOST');}}
    finally{button.disabled=false;updateStateHash();}
  }

  function updateStateHash(){const e=$('action-state-hash');if(e)e.textContent=hashText(JSON.stringify(runtime()?.getCanonicalState()||{}));}
  function configureEndpoint(value){endpoint=String(value||'').trim().replace(/\/+$/,'');if(endpoint)localStorage.setItem(ENDPOINT_KEY,endpoint);else localStorage.removeItem(ENDPOINT_KEY);const input=$('janus-api-endpoint');if(input)input.value=endpoint;healthCheck();}

  function setup(){
    const qs=new URLSearchParams(location.search);endpoint=qs.get('janus_api')||localStorage.getItem(ENDPOINT_KEY)||'';
    const form=$('action-form'),input=$('action-input');form?.addEventListener('submit',e=>{e.preventDefault();executeText(input.value);input.select();});
    const ep=$('janus-api-endpoint');if(ep){ep.value=endpoint;ep.addEventListener('change',()=>configureEndpoint(ep.value));}
    $('janus-api-connect')?.addEventListener('click',()=>configureEndpoint(ep?.value||endpoint));
    input?.addEventListener('keydown',e=>e.stopPropagation());input?.addEventListener('keyup',e=>e.stopPropagation());
    updateStateHash();healthCheck();setInterval(healthCheck,15000);setInterval(updateStateHash,1200);
  }

  setup();
  globalThis.GENESIS_JANUS_BRIDGE=Object.freeze({healthCheck,executeText,configureEndpoint,get online(){return online;},get endpoint(){return endpoint;},get health(){return lastHealth;}});
})();
