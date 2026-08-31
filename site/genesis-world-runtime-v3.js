(() => {
  'use strict';

  const CONFIG = Object.freeze({
    schema: 'janus.genesis.world_shell_save.v1',
    generator_version: 'GENESIS_WORLD_SHELL_R0.2.0',
    world_id: 'GENESIS_ONE_WORLD_R0',
    world_seed: 'genesis-one-world-r0',
    save_key: 'janus.genesis.world_shell_r0.save.v1',
    chunk_size: 10,
    visible_radius: 2,
    prewarm_radius: 4,
    render_radius: 14,
    max_mutations: 512,
    max_chronicle_events: 2048,
  });

  const MIRRORS = Object.freeze({
    ORIGIN: {sky:'#07131b', horizon:'#1c3436', water:'#163849', shore:'#777057', meadow:'#3d704f', forest:'#244c3a', steppe:'#6c6847', highland:'#626967', void:'#171f27', accent:'#73ecff', glow:'#8ef7b8'},
    NOCTURNE: {sky:'#030611', horizon:'#11192d', water:'#0c1834', shore:'#49475b', meadow:'#263b50', forest:'#172b3d', steppe:'#4e4a5c', highland:'#4e5568', void:'#101421', accent:'#9bc4ff', glow:'#d7e8ff'},
    AETHER: {sky:'#080616', horizon:'#16283b', water:'#173454', shore:'#6a5876', meadow:'#315b69', forest:'#244653', steppe:'#67526f', highland:'#556579', void:'#15152a', accent:'#7af8ff', glow:'#d18cff'},
    EMBER: {sky:'#150907', horizon:'#3a241d', water:'#25394a', shore:'#80634a', meadow:'#6a5e3f', forest:'#403f31', steppe:'#806445', highland:'#6d5b52', void:'#211712', accent:'#ffc27a', glow:'#ff826b'}
  });

  const CAMERAS = Object.freeze(['FIRST_PERSON', 'THIRD_PERSON', 'ISOMETRIC']);
  const $ = id => document.getElementById(id);
  const canvas = $('genesis-world');
  const ctx = canvas.getContext('2d', {alpha:false});
  const minimap = $('minimap');
  const mapCtx = minimap?.getContext('2d');
  const keys = new Set();
  let entered = false;
  let lastFrame = performance.now();
  let lastChunk = '';
  let pointer = {active:false,id:null,x:0,y:0,mode:'look'};
  let viewport = {w:innerWidth,h:innerHeight,dpr:1};
  let textureResolver = null;

  function clamp(v,a,b){ return Math.max(a,Math.min(b,v)); }
  function hashString(value){ let h=0x811c9dc5; for(const ch of String(value)){ h^=ch.charCodeAt(0); h=Math.imul(h,0x01000193); } return h>>>0; }
  function mix32(v){ let x=v>>>0; x^=x>>>16; x=Math.imul(x,0x7feb352d); x^=x>>>15; x=Math.imul(x,0x846ca68b); x^=x>>>16; return x>>>0; }
  const WORLD_SEED_U32 = hashString(CONFIG.world_seed);
  function unitHash(x,y,s=0){ return mix32(WORLD_SEED_U32 ^ Math.imul(x|0,0x1f123bb5) ^ Math.imul(y|0,0x5f356495) ^ (s>>>0))/0xffffffff; }
  function smooth(t){ return t*t*(3-2*t); }
  function lerp(a,b,t){ return a+(b-a)*t; }
  function valueNoise(x,y,scale,salt){ const gx=x/scale, gy=y/scale, x0=Math.floor(gx), y0=Math.floor(gy), tx=smooth(gx-x0), ty=smooth(gy-y0); const a=lerp(unitHash(x0,y0,salt),unitHash(x0+1,y0,salt),tx); const b=lerp(unitHash(x0,y0+1,salt),unitHash(x0+1,y0+1,salt),tx); return lerp(a,b,ty); }
  function fbm(x,y,s){ return valueNoise(x,y,34,s)*.46+valueNoise(x,y,17,s+101)*.27+valueNoise(x,y,8.5,s+211)*.17+valueNoise(x,y,4.25,s+307)*.10; }

  function tileAt(x,y){
    const e=clamp(.12+fbm(x,y,0x1201)*.72+Math.max(0,1-Math.hypot(x,y)/24)*.18,0,1);
    const m=fbm(x+311,y-173,0x2402), w=fbm(x-97,y+251,0x3603);
    let biome='meadow';
    if(e<.285) biome='water'; else if(e<.345) biome='shore'; else if(e>.79) biome='highland'; else if(w>.84&&e>.52) biome='void'; else if(m>.63) biome='forest'; else if(m<.29) biome='steppe';
    return {x,y,height:e,moisture:m,weirdness:w,biome,z:(e-.28)*5.5};
  }

  function defaultSave(){ return {
    schema:CONFIG.schema, generator_version:CONFIG.generator_version, world_id:CONFIG.world_id, world_seed:CONFIG.world_seed,
    player_position:{x:.5,y:.5}, mirror_profile:'ORIGIN', camera_mode:'ISOMETRIC', camera_heading:-Math.PI/4,
    camera_pitch:-.62, camera_roll:0, camera_distance:12, discovered_chunk_coordinates:[], explicit_world_mutations:[], chronicle_hash_chain:[]
  }; }

  function loadSave(){
    const fallback=defaultSave();
    try{
      const p=JSON.parse(localStorage.getItem(CONFIG.save_key)||'null');
      if(!p||p.world_id!==CONFIG.world_id||p.world_seed!==CONFIG.world_seed) return fallback;
      return {
        ...fallback,
        player_position:{x:Number(p.player_position?.x)||.5,y:Number(p.player_position?.y)||.5},
        mirror_profile:MIRRORS[p.mirror_profile]?p.mirror_profile:'ORIGIN',
        camera_mode:CAMERAS.includes(p.camera_mode)?p.camera_mode:'ISOMETRIC',
        camera_heading:Number.isFinite(+p.camera_heading)?+p.camera_heading:fallback.camera_heading,
        camera_pitch:Number.isFinite(+p.camera_pitch)?clamp(+p.camera_pitch,-1.45,1.2):fallback.camera_pitch,
        camera_roll:Number.isFinite(+p.camera_roll)?clamp(+p.camera_roll,-Math.PI,Math.PI):0,
        camera_distance:Number.isFinite(+p.camera_distance)?clamp(+p.camera_distance,3,32):12,
        discovered_chunk_coordinates:Array.isArray(p.discovered_chunk_coordinates)?p.discovered_chunk_coordinates.slice(-8192):[],
        explicit_world_mutations:Array.isArray(p.explicit_world_mutations)?p.explicit_world_mutations.slice(-CONFIG.max_mutations):[],
        chronicle_hash_chain:Array.isArray(p.chronicle_hash_chain)?p.chronicle_hash_chain.slice(-CONFIG.max_chronicle_events):[]
      };
    }catch{return fallback;}
  }
  let save=loadSave();
  function persist(){ localStorage.setItem(CONFIG.save_key,JSON.stringify(save)); }

  async function sha256(text){ if(crypto?.subtle){ const d=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)); return [...new Uint8Array(d)].map(v=>v.toString(16).padStart(2,'0')).join(''); } return hashString(text).toString(16).padStart(8,'0'); }
  async function chronicle(type,data={}){ const prev=save.chronicle_hash_chain.at(-1)?.event_hash||'GENESIS'; const core={sequence:save.chronicle_hash_chain.length+1,type,data,prev}; const event_hash=await sha256(JSON.stringify(core)); save.chronicle_hash_chain.push({...core,event_hash}); save.chronicle_hash_chain=save.chronicle_hash_chain.slice(-CONFIG.max_chronicle_events); persist(); renderChronicle(); }

  function chunkOf(pos=save.player_position){ return {cx:Math.floor(pos.x/CONFIG.chunk_size),cy:Math.floor(pos.y/CONFIG.chunk_size)}; }
  function discover(){ const {cx,cy}=chunkOf(); const key=`${cx},${cy}`; if(key===lastChunk) return; lastChunk=key; if(!save.discovered_chunk_coordinates.some(([x,y])=>x===cx&&y===cy)){ save.discovered_chunk_coordinates.push([cx,cy]); persist(); chronicle('CHUNK_DISCOVERED',{chunk:[cx,cy]}); } }

  function cameraState(){
    const p=save.player_position, ground=tileAt(p.x,p.y).z+1.75;
    if(save.camera_mode==='FIRST_PERSON') return {x:p.x,y:p.y,z:ground,yaw:save.camera_heading,pitch:save.camera_pitch,roll:save.camera_roll,fov:1.05};
    if(save.camera_mode==='THIRD_PERSON'){
      const d=save.camera_distance, cp=Math.cos(save.camera_pitch);
      return {x:p.x-Math.cos(save.camera_heading)*d*cp,y:p.y-Math.sin(save.camera_heading)*d*cp,z:ground-Math.sin(save.camera_pitch)*d*.8+2,yaw:save.camera_heading,pitch:save.camera_pitch,roll:save.camera_roll,fov:1.00};
    }
    const d=save.camera_distance+8, yaw=save.camera_heading, pitch=-.68;
    return {x:p.x-Math.cos(yaw)*d,y:p.y-Math.sin(yaw)*d,z:ground+15,yaw,pitch,roll:0,fov:.82};
  }

  function project(wx,wy,wz,cam){
    let x=wx-cam.x,y=wy-cam.y,z=wz-cam.z;
    const cy=Math.cos(-cam.yaw), sy=Math.sin(-cam.yaw); let x1=x*cy-y*sy, y1=x*sy+y*cy, z1=z;
    const cp=Math.cos(-cam.pitch), sp=Math.sin(-cam.pitch); let y2=y1*cp-z1*sp, z2=y1*sp+z1*cp, x2=x1;
    const cr=Math.cos(-cam.roll), sr=Math.sin(-cam.roll); let x3=x2*cr-z2*sr, z3=x2*sr+z2*cr;
    const depth=y2;
    if(depth<=.15) return null;
    const focal=(viewport.h*.5)/Math.tan(cam.fov*.5);
    return {x:viewport.w*.5+x3*focal/depth,y:viewport.h*.52-z3*focal/depth,d:depth};
  }

  function polygon(points,fill,stroke=null,alpha=1){ if(points.some(p=>!p)) return; ctx.globalAlpha=alpha; ctx.beginPath(); ctx.moveTo(points[0].x,points[0].y); for(let i=1;i<points.length;i++)ctx.lineTo(points[i].x,points[i].y); ctx.closePath(); ctx.fillStyle=fill; ctx.fill(); if(stroke){ctx.strokeStyle=stroke;ctx.stroke();} ctx.globalAlpha=1; }

  function biomeColor(tile){ const m=MIRRORS[save.mirror_profile]; return m[tile.biome]||m.meadow; }
  function terrainCells(cam){
    const p=save.player_position, r=CONFIG.render_radius, cells=[];
    const sx=Math.floor(p.x-r), ex=Math.ceil(p.x+r), sy=Math.floor(p.y-r), ey=Math.ceil(p.y+r);
    for(let y=sy;y<ey;y++)for(let x=sx;x<ex;x++){
      const a=tileAt(x,y), b=tileAt(x+1,y), c=tileAt(x+1,y+1), d=tileAt(x,y+1);
      const pts=[project(x,y,a.z,cam),project(x+1,y,b.z,cam),project(x+1,y+1,c.z,cam),project(x,y+1,d.z,cam)];
      const valid=pts.filter(Boolean); if(valid.length!==4) continue;
      const depth=valid.reduce((s,q)=>s+q.d,0)/4;
      cells.push({depth,pts,tile:a});
    }
    cells.sort((a,b)=>b.depth-a.depth);
    for(const cell of cells){ polygon(cell.pts,biomeColor(cell.tile),'rgba(255,255,255,.035)',1); }
  }

  function primitiveBox(x,y,z,w,d,h,cam,color,glow=false){
    const v=[[-w,-d,0],[w,-d,0],[w,d,0],[-w,d,0],[-w,-d,h],[w,-d,h],[w,d,h],[-w,d,h]].map(([dx,dy,dz])=>project(x+dx,y+dy,z+dz,cam));
    const faces=[[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]];
    for(const f of faces){ polygon(f.map(i=>v[i]),color,glow?MIRRORS[save.mirror_profile].glow:'rgba(0,0,0,.3)',.95); }
  }

  function drawObject(obj,cam){
    const t=tileAt(obj.x,obj.y), z=t.z, m=MIRRORS[save.mirror_profile];
    if(obj.type==='TREE'){ primitiveBox(obj.x,obj.y,z,.08,.08,.9,cam,'#49351f'); primitiveBox(obj.x,obj.y,z+.75,.35,.35,.8,cam,m.forest); return; }
    if(obj.type==='ROCK'){ primitiveBox(obj.x,obj.y,z,.24,.2,.28,cam,m.highland); return; }
    if(obj.type==='CRYSTAL'){ primitiveBox(obj.x,obj.y,z,.12,.12,.9,cam,m.glow,true); return; }
    if(obj.type==='RUIN'||obj.type==='OBELISK'){ primitiveBox(obj.x,obj.y,z,.32,.32,1.7,cam,m.shore,true); return; }
    if(obj.type==='FIRST_FIRE'){ primitiveBox(obj.x,obj.y,z,.25,.25,.25,cam,'#5d3a25'); primitiveBox(obj.x,obj.y,z+.15,.12,.12,.8,cam,m.glow,true); }
  }

  function proceduralObjects(){
    const p=save.player_position,r=CONFIG.render_radius, out=[];
    for(let cy=Math.floor((p.y-r)/10);cy<=Math.floor((p.y+r)/10);cy++)for(let cx=Math.floor((p.x-r)/10);cx<=Math.floor((p.x+r)/10);cx++){
      if(cx===0&&cy===0) out.push({id:'first-fire',type:'FIRST_FIRE',x:.5,y:.5});
      for(let i=0;i<12;i++){
        const x=cx*10+.2+unitHash(cx,cy,0x5100+i)*9.6, y=cy*10+.2+unitHash(cx,cy,0x6200+i)*9.6, t=tileAt(x,y);
        if(t.biome==='water'||unitHash(cx,cy,0x7300+i)>.45) continue;
        const roll=unitHash(cx,cy,0x8400+i); const type=roll>.94?'RUIN':t.weirdness>.86?'CRYSTAL':t.biome==='forest'?'TREE':'ROCK';
        out.push({id:`${cx},${cy}:${i}`,type,x,y});
      }
    }
    return out;
  }

  function structureRecipe(mutation){
    const seed=parseInt(String(mutation.seed||mutation.action_seed||hashString(mutation.concept)).slice(0,8),16)||1;
    const kind=mutation.structure_kind||'generic_structure';
    const scale=.75+(seed%100)/160;
    return {kind,scale,levels:2+(seed%5),twist:((seed>>>8)%100)/100};
  }

  function drawStructure(m,cam){
    const recipe=structureRecipe(m), base=tileAt(m.x,m.y).z, c=MIRRORS[save.mirror_profile].accent;
    const x=m.x,y=m.y,s=recipe.scale;
    if(recipe.kind==='bridge'){ for(let i=-3;i<=3;i++) primitiveBox(x+i*.55,y,base+.2,.28,.75,.18,cam,c); return; }
    if(recipe.kind==='wall'){ for(let i=-3;i<=3;i++) primitiveBox(x+i*.45,y,base,.22,.18,1.6*s,cam,c); return; }
    if(recipe.kind==='house'){ primitiveBox(x,y,base,.9*s,.8*s,1.4*s,cam,c); primitiveBox(x,y,base+1.35*s,.75*s,.65*s,.5*s,cam,MIRRORS[save.mirror_profile].glow,true); return; }
    if(recipe.kind==='portal'){ primitiveBox(x-.65*s,y,base,.16,.16,2.4*s,cam,c,true); primitiveBox(x+.65*s,y,base,.16,.16,2.4*s,cam,c,true); primitiveBox(x,y,base+2.2*s,.82*s,.16,.16,cam,c,true); return; }
    if(recipe.kind==='tree'){ drawObject({type:'TREE',x,y},cam); return; }
    const levels=recipe.kind==='lighthouse'?6:recipe.kind==='tower'?5:recipe.levels;
    for(let i=0;i<levels;i++) primitiveBox(x,y,base+i*.52*s,(.5-i*.035)*s,(.5-i*.035)*s,.55*s,cam,i===levels-1?MIRRORS[save.mirror_profile].glow:c,i===levels-1);
    if(recipe.kind==='lighthouse') primitiveBox(x,y,base+levels*.52*s,.18,.18,.5,cam,'#fff7c2',true);
  }

  function renderWorld(){
    resize(); const m=MIRRORS[save.mirror_profile]; const grad=ctx.createLinearGradient(0,0,0,viewport.h); grad.addColorStop(0,m.sky);grad.addColorStop(.7,m.horizon);grad.addColorStop(1,'#020508');ctx.fillStyle=grad;ctx.fillRect(0,0,viewport.w,viewport.h);
    const cam=cameraState(); terrainCells(cam);
    const objects=proceduralObjects(); objects.sort((a,b)=>Math.hypot(b.x-cam.x,b.y-cam.y)-Math.hypot(a.x-cam.x,a.y-cam.y)); for(const o of objects) drawObject(o,cam);
    for(const mutation of save.explicit_world_mutations){ if(mutation.type==='GENERATED_STRUCTURE') drawStructure(mutation,cam); else if(mutation.type==='PLAYER_MARK') drawObject({type:'CRYSTAL',x:mutation.x,y:mutation.y},cam); }
    if(save.camera_mode==='THIRD_PERSON') primitiveBox(save.player_position.x,save.player_position.y,tileAt(save.player_position.x,save.player_position.y).z,.18,.18,1.65,cam,m.glow,true);
    if(save.camera_mode==='FIRST_PERSON'){ctx.strokeStyle=m.accent;ctx.globalAlpha=.6;ctx.beginPath();ctx.moveTo(viewport.w/2-8,viewport.h/2);ctx.lineTo(viewport.w/2+8,viewport.h/2);ctx.moveTo(viewport.w/2,viewport.h/2-8);ctx.lineTo(viewport.w/2,viewport.h/2+8);ctx.stroke();ctx.globalAlpha=1;}
    renderMinimap(); renderHud();
  }

  function resize(){ const dpr=Math.min(2,devicePixelRatio||1), w=Math.max(1,innerWidth),h=Math.max(1,innerHeight); viewport={w,h,dpr}; const bw=Math.floor(w*dpr),bh=Math.floor(h*dpr); if(canvas.width!==bw||canvas.height!==bh){canvas.width=bw;canvas.height=bh;canvas.style.width=`${w}px`;canvas.style.height=`${h}px`;ctx.setTransform(dpr,0,0,dpr,0,0);} }

  function renderMinimap(){ if(!mapCtx||!minimap)return; mapCtx.clearRect(0,0,minimap.width,minimap.height);mapCtx.fillStyle='#061016';mapCtx.fillRect(0,0,minimap.width,minimap.height);const c=chunkOf(),size=15,mid=90;for(const [cx,cy] of save.discovered_chunk_coordinates){mapCtx.fillStyle='#244b52';mapCtx.fillRect(mid+(cx-c.cx)*size,mid+(cy-c.cy)*size,size-1,size-1);}mapCtx.fillStyle=MIRRORS[save.mirror_profile].accent;mapCtx.fillRect(mid-3,mid-3,6,6); }
  function renderChronicle(){ const list=$('chronicle-list'); if(!list)return; list.innerHTML=''; for(const e of save.chronicle_hash_chain.slice(-20).reverse()){ const li=document.createElement('li');li.innerHTML=`<span class="seq">#${e.sequence}</span><span><b class="event">${escapeHtml(e.type)}</b><small class="meta">${escapeHtml(JSON.stringify(e.data||{}).slice(0,160))}</small></span><code class="hash">${String(e.event_hash).slice(0,8)}</code>`;list.append(li);} }
  function escapeHtml(v){return String(v).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}

  function factHash(){ const c=chunkOf(); return hashString(JSON.stringify({world:CONFIG.world_seed,gen:CONFIG.generator_version,chunk:[c.cx,c.cy]})).toString(16).padStart(8,'0'); }
  function renderHud(){ const c=chunkOf(); if($('chunk-coords'))$('chunk-coords').textContent=`${c.cx},${c.cy}`; if($('fact-hash'))$('fact-hash').textContent=factHash(); if($('mirror-fact-hash'))$('mirror-fact-hash').textContent=factHash(); if($('discovered-count'))$('discovered-count').textContent=save.discovered_chunk_coordinates.length; if($('mirror-name'))$('mirror-name').textContent=save.mirror_profile; if($('camera-name'))$('camera-name').textContent=save.camera_mode.replace('_',' '); if($('dimension-name'))$('dimension-name').textContent='3D'; if($('view-combination'))$('view-combination').textContent=`3D / ${save.camera_mode.replace('_',' ')}`; if($('view-toggle'))$('view-toggle').textContent=`VIEW: ${save.camera_mode.replace('_',' ')}`; if($('generator-state'))$('generator-state').textContent='GENESIS WORLD RUNTIME V3 / 3D CAUSE RENDER'; }

  function movementVector(){ let f=0,s=0; if(keys.has('KeyW')||keys.has('ArrowUp'))f+=1;if(keys.has('KeyS')||keys.has('ArrowDown'))f-=1;if(keys.has('KeyA')||keys.has('ArrowLeft'))s-=1;if(keys.has('KeyD')||keys.has('ArrowRight'))s+=1; if(!f&&!s)return null; const len=Math.hypot(f,s)||1; f/=len;s/=len; const yaw=save.camera_heading; return {x:Math.cos(yaw)*f+Math.cos(yaw+Math.PI/2)*s,y:Math.sin(yaw)*f+Math.sin(yaw+Math.PI/2)*s}; }
  function move(dx,dy,dt=1){ const speed=(keys.has('ShiftLeft')||keys.has('ShiftRight'))?7:3.2; save.player_position.x+=dx*speed*dt;save.player_position.y+=dy*speed*dt;discover();persist(); }

  function setCamera(mode){ if(!CAMERAS.includes(mode))return false; save.camera_mode=mode; if(mode==='ISOMETRIC'){save.camera_pitch=-.68;save.camera_roll=0;save.camera_distance=12;} persist(); renderHud(); return true; }
  function setMirror(name){ if(!MIRRORS[name])return false; save.mirror_profile=name;persist();return true; }
  function leaveMark(label='PLAYER MARK'){ const p=save.player_position; save.explicit_world_mutations.push({type:'PLAYER_MARK',x:p.x,y:p.y,label:String(label).slice(0,64),created_at:Date.now()});save.explicit_world_mutations=save.explicit_world_mutations.slice(-CONFIG.max_mutations);persist();chronicle('PLAYER_MARK',{x:+p.x.toFixed(2),y:+p.y.toFixed(2),label:String(label).slice(0,64)}); }
  function returnToHearth(){save.player_position={x:.5,y:.5};discover();persist();chronicle('RETURN_TO_HEARTH',{});}
  function materializeStructure(plan,provenance={}){ const p=save.player_position, yaw=save.camera_heading, dist=3.2; const x=p.x+Math.cos(yaw)*dist,y=p.y+Math.sin(yaw)*dist; const mutation={type:'GENERATED_STRUCTURE',concept:String(plan.concept||'generated structure').slice(0,96),structure_kind:String(plan.structure_kind||'generic_structure'),seed:String(plan.action_seed||plan.seed||hashString(plan.concept||'')),x,y,created_at:Date.now(),recipe:`KRR_GENERATIVE_${String(plan.structure_kind||'generic').toUpperCase()}_R1`,asset_refs:Array.isArray(provenance.asset_refs)?provenance.asset_refs.slice(0,8):[],janus_receipt_hash:provenance.receipt_hash||null};save.explicit_world_mutations.push(mutation);save.explicit_world_mutations=save.explicit_world_mutations.slice(-CONFIG.max_mutations);persist();chronicle('STRUCTURE_MATERIALIZED',{concept:mutation.concept,kind:mutation.structure_kind,x:+x.toFixed(2),y:+y.toFixed(2),recipe:mutation.recipe,asset_refs:mutation.asset_refs});return mutation; }

  function executeIntent(intent,provenance={}){
    if(!intent||typeof intent!=='object')return {ok:false,reason:'INTENT_INVALID'};
    if(intent.kind==='MOVE'){ const dir=intent.direction||'FORWARD',steps=clamp(Number(intent.steps)||1,1,64); const dirs={N:[0,-1],NE:[1,-1],E:[1,0],SE:[1,1],S:[0,1],SW:[-1,1],W:[-1,0],NW:[-1,-1]}; let v=dirs[dir]; if(dir==='FORWARD')v=[Math.cos(save.camera_heading),Math.sin(save.camera_heading)]; if(!v)return {ok:false,reason:'DIRECTION_INVALID'}; const l=Math.hypot(v[0],v[1])||1;save.player_position.x+=v[0]/l*steps;save.player_position.y+=v[1]/l*steps;discover();persist();chronicle('TEXT_MOVE',{direction:dir,steps});return {ok:true}; }
    if(intent.kind==='RETURN_TO_HEARTH'){returnToHearth();return {ok:true};}
    if(intent.kind==='PLACE_MARK'){leaveMark(intent.label||'PLAYER MARK');return {ok:true};}
    if(intent.kind==='GENERATE_STRUCTURE'){return {ok:true,mutation:materializeStructure(intent,provenance)};}
    if(intent.kind==='SET_CAMERA')return {ok:setCamera(intent.camera)};
    if(intent.kind==='SET_MIRROR')return {ok:setMirror(intent.mirror)};
    return {ok:false,reason:'INTENT_NOT_ALLOWLISTED'};
  }

  function cameraDrag(dx,dy,mode){ if(save.camera_mode==='ISOMETRIC'){save.camera_heading+=dx*.006; save.camera_pitch=clamp(save.camera_pitch+dy*.004,-1.25,-.28);} else if(mode==='roll'){save.camera_roll=clamp(save.camera_roll+dx*.006,-Math.PI,Math.PI);} else {save.camera_heading+=dx*.005;save.camera_pitch=clamp(save.camera_pitch+dy*.004,-1.35,1.1);} persist(); }

  function setupUI(){
    $('enter-world')?.addEventListener('click',()=>{entered=true;$('welcome').hidden=true;canvas.focus?.();});
    $('leave-mark')?.addEventListener('click',()=>leaveMark()); $('reset-view')?.addEventListener('click',returnToHearth);
    $('mirror-toggle')?.addEventListener('click',()=>{$('mirror-panel').hidden=!$('mirror-panel').hidden;}); $('view-toggle')?.addEventListener('click',()=>{$('mirror-panel').hidden=false;}); $('chronicle-toggle')?.addEventListener('click',()=>{$('chronicle-panel').hidden=!$('chronicle-panel').hidden;renderChronicle();});
    document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>{$(b.dataset.close).hidden=true;}));
    const mo=$('mirror-options'); if(mo){mo.innerHTML='';for(const name of Object.keys(MIRRORS)){const b=document.createElement('button');b.type='button';b.textContent=name;b.addEventListener('click',()=>setMirror(name));mo.append(b);}}
    const co=$('camera-options'); if(co){co.innerHTML='';for(const name of CAMERAS){const b=document.createElement('button');b.type='button';b.textContent=name.replace('_',' ');b.addEventListener('click',()=>setCamera(name));co.append(b);}}
    const dim=$('dimension-options'); if(dim){dim.innerHTML='<button type="button" class="selected" disabled>3D ONLY</button>';}
    canvas.tabIndex=0;
  }

  function setupInput(){
    addEventListener('keydown',e=>{ if(e.target instanceof HTMLInputElement||e.target instanceof HTMLTextAreaElement||e.target?.isContentEditable)return; const codes=['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','ShiftLeft','ShiftRight']; if(codes.includes(e.code)){keys.add(e.code);e.preventDefault();} if(e.code==='KeyC'){save.camera_roll=0;persist();} });
    addEventListener('keyup',e=>keys.delete(e.code));
    canvas.addEventListener('pointerdown',e=>{pointer={active:true,id:e.pointerId,x:e.clientX,y:e.clientY,mode:(e.button===1||e.altKey)?'roll':'look'};canvas.setPointerCapture?.(e.pointerId);});
    canvas.addEventListener('pointermove',e=>{if(!pointer.active||pointer.id!==e.pointerId)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;pointer.x=e.clientX;pointer.y=e.clientY;cameraDrag(dx,dy,pointer.mode);});
    const end=e=>{if(pointer.id===e.pointerId)pointer.active=false;};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
    canvas.addEventListener('wheel',e=>{ if(save.camera_mode==='THIRD_PERSON'||save.camera_mode==='ISOMETRIC'){save.camera_distance=clamp(save.camera_distance+e.deltaY*.012,3,32);persist();e.preventDefault();} },{passive:false});
    document.querySelectorAll('.mobile-pad [data-move]').forEach(btn=>{const map={up:'KeyW',down:'KeyS',left:'KeyA',right:'KeyD'},code=map[btn.dataset.move]; const on=e=>{e.preventDefault();keys.add(code);},off=e=>{e.preventDefault();keys.delete(code);};btn.addEventListener('pointerdown',on);btn.addEventListener('pointerup',off);btn.addEventListener('pointercancel',off);});
  }

  function frame(now){ const dt=Math.min(.05,(now-lastFrame)/1000);lastFrame=now;if(entered){const v=movementVector();if(v)move(v.x,v.y,dt);}renderWorld();requestAnimationFrame(frame); }

  setupUI();setupInput();discover();renderChronicle();requestAnimationFrame(frame);

  globalThis.GENESIS_WORLD_RUNTIME_V3=Object.freeze({
    version:'0.2.0',
    getCanonicalState(){const c=save.chronicle_hash_chain.at(-1);return {world_id:save.world_id,world_seed:save.world_seed,generator_version:save.generator_version,player_position:{...save.player_position},discovered_chunk_coordinates:save.discovered_chunk_coordinates.map(v=>[...v]),explicit_world_mutations:save.explicit_world_mutations.map(v=>({...v})),chronicle_tip_hash:c?.event_hash||'GENESIS'};},
    getPresentationState(){return {mirror_profile:save.mirror_profile,camera_mode:save.camera_mode,camera_heading:save.camera_heading,camera_pitch:save.camera_pitch,camera_roll:save.camera_roll,camera_distance:save.camera_distance};},
    executeIntent,
    setCamera,
    setMirror,
    leaveMark,
    returnToHearth,
    setTextureResolver(fn){textureResolver=typeof fn==='function'?fn:null;return !!textureResolver;},
    getFactHash:factHash
  });
})();
