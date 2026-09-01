'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),vm=require('vm');
const ROOT=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(ROOT,'site','genesis-free-intent-r0-8.js'),'utf8');
let calls=0;
const known={kind:'GENERATE_STRUCTURE',concept:'old lighthouse',structure_kind:'lighthouse',action_seed:'seed-known',marker:'BASE_EXACT'};
const base=Object.freeze({
  version:'3.0.1+r0.5',
  localCompile(raw){calls++;if(raw==='построй маяк')return known;return{kind:'UNRESOLVED',reason:'LOCAL_DEGRADED_NEEDS_JANUS_SEMANTIC_COMPILER',player_text:raw,action_seed:`seed:${raw}`};},
  healthCheck(){},executeText(){},configureEndpoint(){},focusConsole(){},
  get online(){return false;},get endpoint(){return'';},get health(){return null;}
});
const sandbox={console,GENESIS_COMMAND_BRIDGE_V3:base,GENESIS_COMMAND_BRIDGE_V2:base,Object,String,Set,RegExp,JSON};sandbox.globalThis=sandbox;
vm.createContext(sandbox);vm.runInContext(source,sandbox,{filename:'genesis-free-intent-r0-8.js'});
const api=sandbox.GENESIS_FREE_INTENT_R0_8,wrapped=sandbox.GENESIS_COMMAND_BRIDGE_V3;
assert(api&&wrapped,'R0.8 APIs must load');
assert.strictEqual(api.version,'0.8.0');
assert.strictEqual(Object.isFrozen(wrapped),true);
const beforeCalls=calls;
const old=wrapped.localCompile('построй маяк');
assert.strictEqual(old,known,'recognized base command must be returned unchanged');
assert.strictEqual(calls,beforeCalls+1);
const birthText='пусть в темноте появится один тёплый огонь';
const birth=wrapped.localCompile(birthText);
assert.strictEqual(birth.kind,'SPAWN_ENTITY');
assert.strictEqual(birth.entity_kind,'light_source');
assert.strictEqual(birth.action_seed,`seed:${birthText}`);
assert.strictEqual(birth.semantic_origin,'EXISTENTIAL_FALLBACK_R0_8');
assert(birth.concept.includes('огонь'));
const ua=wrapped.localCompile('нехай з’явиться кристал');
assert.strictEqual(ua.kind,'SPAWN_ENTITY');
assert.strictEqual(ua.entity_kind,'artifact');
const en=wrapped.localCompile('let there be lighthouse');
assert.strictEqual(en.kind,'GENERATE_STRUCTURE');
assert.strictEqual(en.structure_kind,'lighthouse');
const night=wrapped.localCompile('пусть будет ночь');
assert.strictEqual(night.kind,'SET_ATMOSPHERE');assert.strictEqual(night.time,'NIGHT');
const unknownText='это просто мысль без команды';
const unknown=wrapped.localCompile(unknownText);
assert.strictEqual(unknown.kind,'UNRESOLVED');
assert.strictEqual(unknown.action_seed,`seed:${unknownText}`);
assert.strictEqual(api.compileExistential('обычный текст','x'),null);
assert(!source.includes('fetch('));assert(!source.includes('eval('));assert(!source.includes('new Function'));
console.log('GENESIS_FREE_INTENT_R0_8_EXECUTABLE_HARNESS_PASS');
