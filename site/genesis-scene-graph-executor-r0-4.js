(() => {
  'use strict';

  const SCHEMA='janus.genesis.scene_graph.v1';
  const VERSION='0.4.0';
  const LIMITS=Object.freeze({max_nodes:32,max_edges:64,max_depth:8,max_resource_units:128,max_node_resource_units:16});
  const FAMILIES=new Set(['STRUCTURE','ENTITY','MATERIAL','ATMOSPHERE','TERRAIN','SOUND','EFFECT','PRESENTATION','RULE','INSPECTION','NAVIGATION']);
  const RECEIPT_KEY='janus.genesis.scene_graph_receipts_r0_4';

  function runtime(){return globalThis.GENESIS_WORLD_RUNTIME_V4;}
  function isObject(v){return v!==null&&typeof v==='object'&&!Array.isArray(v);}
  function hex64(v){return /^[0-9a-f]{64}$/i.test(String(v||''));}
  function exactLimits(v){return isObject(v)&&Object.entries(LIMITS).every(([k,n])=>v[k]===n)&&Object.keys(v).length===Object.keys(LIMITS).length;}
  async function sha256(text){const bytes=new TextEncoder().encode(String(text));if(globalThis.crypto?.subtle){const digest=await crypto.subtle.digest('SHA-256',bytes);return[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');}let h=0x811c9dc5;for(const b of bytes){h^=b;h=Math.imul(h,0x01000193);}return(h>>>0).toString(16).padStart(8,'0').repeat(8).slice(0,64);}
  function structuralEqual(a,b){if(a===b)return true;if(Array.isArray(a)&&Array.isArray(b))return a.length===b.length&&a.every((v,i)=>structuralEqual(v,b[i]));if(isObject(a)&&isObject(b)){const ak=Object.keys(a).sort(),bk=Object.keys(b).sort();return ak.length===bk.length&&ak.every((k,i)=>k===bk[i]&&structuralEqual(a[k],b[k]));}return false;}

  function validateGraph(graph){
    if(!isObject(graph)||graph.schema!==SCHEMA)throw new Error('SCENE_GRAPH_SCHEMA_INVALID');
    if(graph.version!==VERSION)throw new Error('SCENE_GRAPH_VERSION_INVALID');
    if(!exactLimits(graph.limits))throw new Error('SCENE_GRAPH_LIMITS_INVALID');
    if(!Array.isArray(graph.nodes)||graph.nodes.length<1)throw new Error('SCENE_GRAPH_NODES_REQUIRED');
    if(graph.nodes.length>LIMITS.max_nodes)throw new Error('SCENE_GRAPH_NODE_LIMIT');
    const byId=new Map(),indegree=new Map(),outgoing=new Map(),depth=new Map();let edges=0,resources=0;
    for(const node of graph.nodes){
      if(!isObject(node)||!/^n-[0-9a-f]{16}$/i.test(String(node.id||'')))throw new Error('SCENE_GRAPH_NODE_ID_INVALID');
      if(byId.has(node.id))throw new Error('SCENE_GRAPH_NODE_ID_DUPLICATE');
      if(!FAMILIES.has(String(node.family||'').toUpperCase()))throw new Error('SCENE_GRAPH_FAMILY_NOT_ALLOWLISTED');
      if(typeof node.operation!=='string'||!node.operation||node.operation.length>64)throw new Error('SCENE_GRAPH_OPERATION_INVALID');
      if(!isObject(node.params))throw new Error('SCENE_GRAPH_PARAMS_INVALID');
      if(!Array.isArray(node.depends_on)||node.depends_on.length>LIMITS.max_nodes)throw new Error('SCENE_GRAPH_DEPENDENCIES_INVALID');
      const units=Number(node.resource_units);if(!Number.isInteger(units)||units<0||units>LIMITS.max_node_resource_units)throw new Error('SCENE_GRAPH_NODE_RESOURCE_LIMIT');
      resources+=units;edges+=node.depends_on.length;byId.set(node.id,node);indegree.set(node.id,0);outgoing.set(node.id,[]);depth.set(node.id,1);
    }
    if(edges>LIMITS.max_edges)throw new Error('SCENE_GRAPH_EDGE_LIMIT');
    if(resources>LIMITS.max_resource_units)throw new Error('SCENE_GRAPH_RESOURCE_LIMIT');
    for(const node of graph.nodes){for(const dep of node.depends_on){if(dep===node.id)throw new Error('SCENE_GRAPH_SELF_CYCLE');if(!byId.has(dep))throw new Error('SCENE_GRAPH_DEPENDENCY_MISSING');outgoing.get(dep).push(node.id);indegree.set(node.id,indegree.get(node.id)+1);}}
    const ready=[...byId.keys()].filter(id=>indegree.get(id)===0).sort(),order=[];
    while(ready.length){const id=ready.shift();order.push(id);for(const child of outgoing.get(id).sort()){depth.set(child,Math.max(depth.get(child),depth.get(id)+1));if(depth.get(child)>LIMITS.max_depth)throw new Error('SCENE_GRAPH_DEPTH_LIMIT');indegree.set(child,indegree.get(child)-1);if(indegree.get(child)===0){ready.push(child);ready.sort();}}}
    if(order.length!==byId.size)throw new Error('SCENE_GRAPH_CYCLE');
    if(Array.isArray(graph.topological_order)&&!structuralEqual(graph.topological_order,order))throw new Error('SCENE_GRAPH_ORDER_MISMATCH');
    return{order,byId,edges,resources};
  }

  async function verifyTransport(response){
    if(!isObject(response)||response.schema!=='janus.genesis.scene_graph.response.v1')throw new Error('SCENE_GRAPH_RESPONSE_SCHEMA_INVALID');
    const authority=response.authority||{};
    if(authority.janus_graph_is_world_authority!==false||authority.model_output_is_command!==false||authority.genesis_validator_required!==true||authority.world_mutation_authorized_by_janus!==false||authority.external_effect_authorized!==false)throw new Error('SCENE_GRAPH_AUTHORITY_BOUNDARY_INVALID');
    const proof=response.transport_proof;
    if(proof){if(typeof proof.canonical_graph_json!=='string'||!hex64(proof.canonical_graph_utf8_sha256))throw new Error('SCENE_GRAPH_TRANSPORT_PROOF_INVALID');const digest=await sha256(proof.canonical_graph_json);if(digest.toLowerCase()!==String(proof.canonical_graph_utf8_sha256).toLowerCase())throw new Error('SCENE_GRAPH_TRANSPORT_HASH_MISMATCH');let parsed;try{parsed=JSON.parse(proof.canonical_graph_json);}catch{throw new Error('SCENE_GRAPH_TRANSPORT_JSON_INVALID');}if(!structuralEqual(parsed,response.scene_graph))throw new Error('SCENE_GRAPH_TRANSPORT_STRUCTURE_MISMATCH');}
    if(response.scene_graph?.graph_hash&&!hex64(response.scene_graph.graph_hash))throw new Error('SCENE_GRAPH_HASH_SHAPE_INVALID');
    if(response.receipt_hash&&!hex64(response.receipt_hash))throw new Error('SCENE_GRAPH_RECEIPT_HASH_SHAPE_INVALID');
    return validateGraph(response.scene_graph);
  }

  function collectAssetRefs(node,receipts,byId){const refs=[];for(const dep of node.depends_on||[]){const receipt=receipts.get(dep);if(Array.isArray(receipt?.asset_refs))refs.push(...receipt.asset_refs);}return refs.slice(0,8);}
  function persistGraphReceipt(receipt){try{const rows=JSON.parse(localStorage.getItem(RECEIPT_KEY)||'[]');rows.push(receipt);localStorage.setItem(RECEIPT_KEY,JSON.stringify(rows.slice(-512)));}catch{}}
  function intentFromNode(node){const op=String(node.operation||'').toUpperCase(),p=node.params||{},concept=node.concept||p.concept;
    if(node.family==='STRUCTURE'&&op==='GENERATE_STRUCTURE')return{kind:'GENERATE_STRUCTURE',concept,structure_kind:p.structure_kind||'generic_structure',placement:p.placement||'IN_FRONT_OF_PLAYER',distance:p.distance,action_seed:p.action_seed};
    if(node.family==='ENTITY'&&op==='SPAWN_ENTITY')return{kind:'SPAWN_ENTITY',concept,entity_kind:p.entity_kind||'generic_entity',placement:p.placement||'IN_FRONT_OF_PLAYER',action_seed:p.action_seed};
    if(node.family==='ATMOSPHERE')return{kind:'SET_ATMOSPHERE',time:p.time,fog:p.fog,weather:p.weather};
    if(node.family==='TERRAIN'&&op==='WORLD_TRANSFORM')return{kind:'WORLD_TRANSFORM',transform_kind:p.transform_kind,radius:p.radius,amount:p.amount,distance:p.distance,action_seed:p.action_seed};
    if(node.family==='PRESENTATION'&&['SET_CAMERA','SET_MIRROR','SET_CAMERA_DISTANCE'].includes(op))return{kind:op,...p};
    if(node.family==='INSPECTION'&&op==='INSPECT')return{kind:'INSPECT',query:p.query||concept};
    if(node.family==='NAVIGATION'&&['MOVE','RETURN_TO_HEARTH','PLACE_MARK'].includes(op))return{kind:op,...p};
    return null;
  }

  async function executeNode(node,context){
    const rt=runtime();if(!rt)throw new Error('GENESIS_RUNTIME_UNAVAILABLE');const p=node.params||{};
    if(node.family==='MATERIAL'&&node.operation==='RESOLVE_MATERIAL'){
      if(typeof context.resolveMaterial==='function'){const resolved=await context.resolveMaterial(p.query||node.concept,p);if(resolved?.ok)return{ok:true,asset_refs:resolved.asset_refs||[],result:{mode:resolved.mode||'RIGHTS_GATED_REFERENCE',fallback:p.fallback||null}};}
      return{ok:true,asset_refs:[],result:{mode:'PROCEDURAL_KRR_FALLBACK',fallback:p.fallback||'KRR_PROCEDURAL_MATERIAL_R0'}};
    }
    if(node.family==='SOUND'&&node.operation==='AUDIO_CUE'){
      const forge=globalThis.GENESIS_AUDIO_FORGE;if(!globalThis.GENESIS_AUDIO_RUNTIME?.enabled||!forge?.cue)return{ok:false,reason:'AUDIO_DISABLED'};forge.cue(String(p.cue||'discovery'));return{ok:true,result:{cue:p.cue||'discovery',profile:p.profile||null}};
    }
    if(node.family==='EFFECT'&&node.operation==='RUINED_TOWER'){
      const intent={kind:'GENERATE_STRUCTURE',concept:'ruined tower',structure_kind:'tower',placement:'IN_FRONT_OF_PLAYER',distance:6,action_seed:context.graph.action_seed};const out=rt.executeIntent(intent,{receipt_hash:context.janus_receipt_hash||null,asset_refs:collectAssetRefs(node,context.receipts,context.byId)});return out?.ok?{ok:true,result:{fallback:'GENERATE_RUINED_TOWER',mutation:out.mutation||null}}:{ok:false,reason:out?.reason||'EFFECT_REJECTED'};
    }
    if(node.family==='ENTITY'&&node.operation==='SPAWN_GROUP'){
      const count=Math.max(1,Math.min(8,Number(p.count)||3)),made=[];for(let i=0;i<count;i++){const out=rt.executeIntent({kind:'GENERATE_STRUCTURE',concept:`${node.concept} ${i+1}`,structure_kind:'tree',distance:3.2+i*.72,action_seed:`${context.graph.action_seed}:${i}`},{receipt_hash:context.janus_receipt_hash||null,asset_refs:collectAssetRefs(node,context.receipts,context.byId)});if(out?.ok)made.push(out.mutation||true);}return made.length?{ok:true,result:{count:made.length,appearance:p.appearance||null,placement:p.placement||null}}:{ok:false,reason:'GROUP_MATERIALIZATION_FAILED'};
    }
    if(node.family==='RULE'&&node.operation==='SPATIAL_RELATION'){
      if(p.target&&!context.byId.has(p.target))return{ok:false,reason:'RULE_TARGET_MISSING'};return{ok:true,result:{relation:p.relation||'RELATED',target:p.target||null,subject:p.subject||null,mode:'BOUNDED_SCENE_CONSTRAINT_RECEIPT'}};
    }
    if(node.family==='INSPECTION'&&node.operation==='VISIBLE_FAILURE')return{ok:false,reason:String(p.reason||'UNRESOLVED_SCENE_SEMANTICS')};
    const intent=intentFromNode(node);if(!intent)return{ok:false,reason:'NODE_OPERATION_NOT_MATERIALIZABLE'};
    const out=rt.executeIntent(intent,{receipt_hash:context.janus_receipt_hash||null,asset_refs:collectAssetRefs(node,context.receipts,context.byId)});return out?.ok?{ok:true,result:out}:{ok:false,reason:out?.reason||'GENESIS_VALIDATOR_REJECT'};
  }

  async function executeGraph(graph,{janus_receipt_hash=null,resolveMaterial=null,source='UNKNOWN'}={}){
    const validated=validateGraph(graph),receipts=new Map(),started_at=new Date().toISOString();
    const context={graph,byId:validated.byId,receipts,janus_receipt_hash,resolveMaterial};
    for(const id of validated.order){const node=validated.byId.get(id),blocking=(node.depends_on||[]).find(dep=>{const depNode=validated.byId.get(dep),r=receipts.get(dep);return depNode?.required!==false&&r&&r.status!=='APPLIED';});let status='FAILED',reason=null,result=null,asset_refs=[];
      if(blocking){status='SKIPPED_DEPENDENCY';reason=`FAILED_REQUIRED_ANCESTOR:${blocking}`;}else{try{const out=await executeNode(node,context);if(out?.ok){status='APPLIED';result=out.result??null;asset_refs=out.asset_refs||[];}else{status='FAILED';reason=out?.reason||'NODE_FAILED';}}catch(e){status='FAILED';reason=e?.message||String(e);}}
      const core={graph_id:graph.graph_id,node_id:id,family:node.family,operation:node.operation,status,reason,result,required:node.required!==false,depends_on:[...(node.depends_on||[])],source};const receipt_hash=await sha256(JSON.stringify(core));const receipt={...core,asset_refs,receipt_hash};receipts.set(id,receipt);
    }
    const rows=validated.order.map(id=>receipts.get(id)),applied=rows.filter(r=>r.status==='APPLIED').length,failed=rows.filter(r=>r.status==='FAILED').length,skipped=rows.filter(r=>r.status==='SKIPPED_DEPENDENCY').length;
    const summaryCore={schema:'janus.genesis.scene_graph.execution_receipt.v1',version:VERSION,graph_id:graph.graph_id,graph_hash:graph.graph_hash||null,source,started_at,finished_at:new Date().toISOString(),counts:{nodes:rows.length,applied,failed,skipped},node_receipts:rows,partial_failure:failed>0||skipped>0,authority:{janus_graph_is_world_authority:false,genesis_validator_executed:true}};summaryCore.receipt_hash=await sha256(JSON.stringify(summaryCore));persistGraphReceipt(summaryCore);return summaryCore;
  }

  globalThis.GENESIS_SCENE_GRAPH_EXECUTOR_R0_4=Object.freeze({version:VERSION,limits:LIMITS,validateGraph,verifyTransport,executeGraph,structuralEqual});
})();
