(() => {
  'use strict';

  const VERSION='0.8.0';
  const CONTRACT='contracts/GENESIS_FREE_INTENT_R0_8.json';
  const base=globalThis.GENESIS_COMMAND_BRIDGE_V3;
  if(!base?.localCompile){
    console.error('[GENESIS FREE INTENT R0.8] BASE_COMPILER_UNAVAILABLE');
    return;
  }

  const STRUCTURES=Object.freeze([
    ['lighthouse',/(?:\b(?:lighthouse|маяк)\b)/u],
    ['castle',/(?:\b(?:castle|замок|фортеця)\b)/u],
    ['bridge',/(?:\b(?:bridge|мост|міст)\b)/u],
    ['tower',/(?:\b(?:tower|башня|башн|вежа|веж)\b)/u],
    ['house',/(?:\b(?:house|home|дом|будинок)\b)/u],
    ['wall',/(?:\b(?:wall|стена|стіну|стіна)\b)/u],
    ['portal',/(?:\b(?:portal|портал)\b)/u],
    ['tree',/(?:\b(?:tree|дерево|деревце)\b)/u],
    ['statue',/(?:\b(?:statue|статуя|памятник|пам'ятник)\b)/u],
    ['road',/(?:\b(?:road|дорога|шлях)\b)/u]
  ]);

  const ENTITY_RULES=Object.freeze([
    ['light_source',/(?:\b(?:fire|flame|light|огонь|пламя|свет|вогонь|полум'я|світло)\b)/u],
    ['living_entity',/(?:\b(?:person|human|animal|creature|wolf|horse|dragon|человек|людина|животное|существо|волк|конь|дракон|істота|кінь)\b)/u],
    ['artifact',/(?:\b(?:artifact|relic|crystal|артефакт|реликвия|кристалл|реліквія|кристал)\b)/u]
  ]);

  const STARTERS=Object.freeze([
    /^(?:пусть|пускай)\s+(.+)$/u,
    /^(?:нехай|хай)\s+(.+)$/u,
    /^let\s+there\s+(?:be|appear)\s+(.+)$/u
  ]);

  function norm(value){
    return String(value||'').normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();
  }

  function bodyOf(raw){
    const text=norm(raw);
    if(!text||text.length>4000)return null;
    for(const rx of STARTERS){const match=text.match(rx);if(match)return match[1]?.trim()||null;}
    return null;
  }

  function cleanConcept(body){
    return String(body||'')
      .replace(/\b(?:появится|появится|возникнет|возникни|будет|станет|загорится|з'явиться|зявиться|виникне|буде|appear|appears|arise|exists?)\b/gu,' ')
      .replace(/\b(?:один|одна|одно|одне|a|an|one)\b/gu,' ')
      .replace(/\s+/g,' ')
      .trim()
      .slice(0,120)||'semantic entity';
  }

  function structureKind(concept){for(const [kind,rx] of STRUCTURES)if(rx.test(concept))return kind;return null;}
  function entityKind(concept){for(const [kind,rx] of ENTITY_RULES)if(rx.test(concept))return kind;return 'semantic_entity';}

  function compileExistential(raw,seed){
    const body=bodyOf(raw);if(!body)return null;
    const concept=cleanConcept(body);
    if(/^(?:night|darkness|ночь|темнота|ніч|темрява)$/u.test(concept))return{kind:'SET_ATMOSPHERE',time:'NIGHT',fog:0.16,action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    if(/^(?:day|daylight|день|свет|день світло)$/u.test(concept))return{kind:'SET_ATMOSPHERE',time:'DAY',fog:0.06,action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    const sk=structureKind(concept);
    if(sk)return{kind:'GENERATE_STRUCTURE',concept,structure_kind:sk,placement:'IN_FRONT_OF_PLAYER',action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    return{kind:'SPAWN_ENTITY',concept,entity_kind:entityKind(concept),placement:'IN_FRONT_OF_PLAYER',action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
  }

  function localCompile(raw){
    const baseResult=base.localCompile(raw);
    if(baseResult?.kind!=='UNRESOLVED')return baseResult;
    return compileExistential(raw,baseResult.action_seed)||baseResult;
  }

  const wrapped=new Proxy(base,{
    get(target,property){if(property==='localCompile')return localCompile;return Reflect.get(target,property,target);},
    set(){return false;},defineProperty(){return false;},deleteProperty(){return false;}
  });
  globalThis.GENESIS_COMMAND_BRIDGE_V3=wrapped;
  globalThis.GENESIS_FREE_INTENT_R0_8=Object.freeze({version:VERSION,contract:CONTRACT,compileExistential:(raw,seed='test-seed')=>compileExistential(raw,seed),localCompile});
})();
