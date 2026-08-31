import json
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "site" / "genesis-world-runtime-v5.js"
MECHANIC = ROOT / "site" / "genesis-mechanic-forge-r0-5.js"


class GenesisRuntimeV5SmokeTests(unittest.TestCase):
    def test_runtime_boot_jump_and_lod_without_canonical_drift(self):
        node = shutil.which("node")
        self.assertIsNotNone(node)
        runtime = json.dumps(str(RUNTIME))
        mechanic = json.dumps(str(MECHANIC))
        script = f"""
const fs=require('fs'),vm=require('vm'),nodeCrypto=require('crypto');
globalThis.crypto=nodeCrypto.webcrypto;
globalThis.innerWidth=1366;globalThis.innerHeight=768;globalThis.devicePixelRatio=1;
Object.defineProperty(globalThis,'navigator',{{value:{{hardwareConcurrency:8,deviceMemory:8,language:'en-US'}},configurable:true}});
globalThis.performance={{now:()=>1000}};
globalThis.requestAnimationFrame=()=>0;globalThis.addEventListener=()=>{{}};
globalThis.HTMLInputElement=class {{}};globalThis.HTMLTextAreaElement=class {{}};
const store=new Map();globalThis.localStorage={{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)}};
const noop=()=>{{}};const context=new Proxy({{}},{{get:(t,p)=>{{if(p==='createLinearGradient')return()=>({{addColorStop:noop}});if(p==='createPattern')return()=>null;if(p==='setTransform')return noop;if(p==='measureText')return()=>({{width:10}});return t[p]??noop;}},set:(t,p,v)=>{{t[p]=v;return true;}}}});
function element(id){{return{{id,hidden:false,textContent:'',innerHTML:'',classList:{{toggle:noop,add:noop,remove:noop}},style:{{}},dataset:{{}},getContext:()=>context,addEventListener:noop,setPointerCapture:noop,focus:noop,append:noop,appendChild:noop,width:180,height:180}};}}
const elements=new Map();globalThis.document={{getElementById:id=>{{if(!elements.has(id))elements.set(id,element(id));return elements.get(id);}},querySelectorAll:()=>[],createElement:()=>element('created'),activeElement:null}};
vm.runInThisContext(fs.readFileSync({mechanic},'utf8'),{{filename:'mechanic.js'}});
vm.runInThisContext(fs.readFileSync({runtime},'utf8'),{{filename:'runtime.js'}});
const rt=globalThis.GENESIS_WORLD_RUNTIME_V5;if(!rt)throw new Error('runtime missing');
const before=JSON.stringify(rt.getCanonicalState());const jump=rt.jump();if(!jump.ok)throw new Error('first jump rejected');
const after=JSON.stringify(rt.getCanonicalState());if(before!==after)throw new Error('jump changed canonical state');
const p=rt.getPresentationState();if(p.grounded!==false)throw new Error('jump did not enter airborne state');
const lod=rt.getStreamingState();if(!(lod.full<lod.near&&lod.near<lod.horizon))throw new Error('LOD ordering invalid');
if(globalThis.GENESIS_WORLD_RUNTIME_V4!==rt)throw new Error('compat alias missing');
console.log('RUNTIME_V5_SMOKE_PASS',lod.profile,lod.full,lod.near,lod.horizon);
"""
        completed = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + "\n" + completed.stderr)
        self.assertIn("RUNTIME_V5_SMOKE_PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
