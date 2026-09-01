(() => {
  'use strict';

  const VERSION='0.8.0';
  const CONTRACT='contracts/GENESIS_FREE_INTENT_R0_8.json';
  const base=globalThis.GENESIS_COMMAND_BRIDGE_V3;
  if(!base?.localCompile){console.error('[GENESIS FREE INTENT R0.8] BASE_COMPILER_UNAVAILABLE');return;}

  const STRUCTURES=Object.freeze([
    ['lighthouse',['lighthouse','маяк']],['castle',['castle','замок','фортеця']],['bridge',['bridge','мост','міст']],
    ['tower',['tower','башня','башни','башню','вежа','вежі']],['house',['house','home','дом','будинок']],
    ['wall',['wall','стена','стіну','стіна']],['portal',['portal','портал']],['tree',['tree','дерево','деревце']],
    ['statue',['statue','статуя','памятник',"пам'ятник"]],['road',['road','дорога','шлях']]
  ]);
  const ENTITY_RULES=Object.freeze([
    ['light_source',['fire','flame','light','огонь','пламя','свет','вогонь',"полум'я",'світло']],
    ['living_entity',['person','human','animal','creature','wolf','horse','dragon','человек','людина','животное','существо','волк','конь','дракон','істота','кінь']],
    ['artifact',['artifact','relic','crystal','артефакт','реликвия','кристалл','реліквія','кристал']]
  ]);
  const STARTERS=Object.freeze([/^(?:пусть|пускай)\s+(.+)$/u,/^(?:нехай|хай)\s+(.+)$/u,/^let\s+there\s+(?:be|appear)\s+(.+)$/u]);
  const DROP=new Set(['появится','возникнет','возникни','будет','станет','загорится',"з'явиться",'зявиться','виникне','буде','appear','appears','arise','exist','exists','один','одна','одно','одне','a','an','one']);

  function norm(value){return String(value||'').normalize('NFKC').toLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();}
  function bodyOf(raw){const text=norm(raw);if(!text||text.length>4000)return null;for(const rx of STARTERS){const match=text.match(rx);if(match)return match[1]?.trim()||null;}return null;}
  function cleanConcept(body){return String(body||'').replace(/[.,!?;:]+/g,' ').split(/\s+/u).filter(word=>word&&!DROP.has(word)).join(' ').trim().slice(0,120)||'semantic entity';}
  function containsAny(concept,terms){return terms.some(term=>concept.includes(term));}
  function structureKind(concept){for(const [kind,terms] of STRUCTURES)if(containsAny(concept,terms))return kind;return null;}
  function entityKind(concept){for(const [kind,terms] of ENTITY_RULES)if(containsAny(concept,terms))return kind;return 'semantic_entity';}

  function compileExistential(raw,seed){
    const body=bodyOf(raw);if(!body)return null;
    const concept=cleanConcept(body);
    if(/^(?:night|darkness|ночь|темнота|ніч|темрява)$/u.test(concept))return{kind:'SET_ATMOSPHERE',time:'NIGHT',fog:0.16,action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    if(/^(?:day|daylight|день|свет|світло)$/u.test(concept))return{kind:'SET_ATMOSPHERE',time:'DAY',fog:0.06,action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    const sk=structureKind(concept);
    if(sk)return{kind:'GENERATE_STRUCTURE',concept,structure_kind:sk,placement:'IN_FRONT_OF_PLAYER',action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
    return{kind:'SPAWN_ENTITY',concept,entity_kind:entityKind(concept),placement:'IN_FRONT_OF_PLAYER',action_seed:seed,semantic_origin:'EXISTENTIAL_FALLBACK_R0_8'};
  }

  function localCompile(raw){const baseResult=base.localCompile(raw);if(baseResult?.kind!=='UNRESOLVED')return baseResult;return compileExistential(raw,baseResult.action_seed)||baseResult;}
  const wrapped=new Proxy(base,{get(target,property){if(property==='localCompile')return localCompile;return Reflect.get(target,property,target);},set(){return false;},defineProperty(){return false;},deleteProperty(){return false;}});
  globalThis.GENESIS_COMMAND_BRIDGE_V3=wrapped;
  globalThis.GENESIS_FREE_INTENT_R0_8=Object.freeze({version:VERSION,contract:CONTRACT,compileExistential:(raw,seed='test-seed')=>compileExistential(raw,seed),localCompile});
})();
