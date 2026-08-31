(() => {
  'use strict';

  const patternCache = new Map();
  const imageCache = new Map();
  const proceduralPalette = Object.freeze({
    stone:['#8b8e88','#737873','#a3a59f'],
    wood:['#7a5638','#9b704b','#563c29'],
    plaster:['#b7ae98','#d2c7ad','#9f9784'],
    roof:['#4a3a36','#5d4942','#302b2c'],
    metal:['#39434a','#5a6770','#232b30'],
    glass:['rgba(125,201,220,.72)','rgba(186,236,244,.78)','rgba(67,132,153,.65)'],
    road:['#6c655b','#847b6e','#554f48'],
    foliage:['#24553a','#34734a','#163a2b'],
    water:['#153c50','#1b526a','#0d2c3c'],
    meadow:['#356c49','#427b54','#27583b'],
    forest:['#204b35','#2d6240','#153728'],
    shore:['#796f55','#918468','#615a49'],
    steppe:['#716943','#84794e','#5f583a'],
    highland:['#636965','#7b817d','#4f5652'],
    void:['#171e25','#202932','#0d1218']
  });

  function hashString(value){let h=0x811c9dc5;for(const ch of String(value)){h^=ch.charCodeAt(0);h=Math.imul(h,0x01000193);}return h>>>0;}
  function mix32(v){let x=v>>>0;x^=x>>>16;x=Math.imul(x,0x7feb352d);x^=x>>>15;x=Math.imul(x,0x846ca68b);x^=x>>>16;return x>>>0;}
  function rand(seed,i){return mix32((seed>>>0)^Math.imul(i+1,0x9e3779b1))/0xffffffff;}
  function externalRef(refs){return (refs||[]).find(r=>r?.rights==='CC0'&&/^https:\/\//i.test(String(r.download_pointer||'')))||null;}
  function imageFor(ref){
    const url=String(ref?.download_pointer||'');if(!url)return null;let item=imageCache.get(url);if(item)return item;
    const img=new Image();item={status:'loading',img,url};imageCache.set(url,item);img.crossOrigin='anonymous';img.referrerPolicy='no-referrer';img.decoding='async';img.onload=()=>{item.status='ready';patternCache.clear();};img.onerror=()=>{item.status='failed';};img.src=url;return item;
  }
  function materialDNA(refs,seed,kind){
    const ref=externalRef(refs);const id=`${kind}|${seed}|${ref?.provider_id||'procedural'}|${ref?.asset_id||''}|${ref?.download_pointer||''}`;const h=hashString(id);
    return {hash:h.toString(16).padStart(8,'0'),roughness:.18+((h>>>8)&255)/255*.68,scale:.55+((h>>>16)&255)/255*1.55,external:!!ref,provider_id:ref?.provider_id||null,asset_id:ref?.asset_id||null,rights:ref?.rights||null};
  }
  function proceduralTile(kind,seed,fallback){
    const key=`proc:${kind}:${seed}:${fallback}`;if(patternCache.has(key))return patternCache.get(key);
    const c=document.createElement('canvas');c.width=96;c.height=96;const g=c.getContext('2d');const h=hashString(`${kind}|${seed}`),palette=proceduralPalette[kind]||[fallback||'#657078','#7a858c','#4f5960'];
    g.fillStyle=palette[0];g.fillRect(0,0,96,96);
    if(kind==='stone'||kind==='highland'||kind==='shore'){
      for(let y=0;y<96;y+=16){const offset=((y/16)%2)*10;for(let x=-20;x<110;x+=20){g.fillStyle=palette[1];g.globalAlpha=.18+.18*rand(h,x+y);g.fillRect(x+offset,y,18,14);g.strokeStyle='rgba(0,0,0,.22)';g.globalAlpha=.38;g.strokeRect(x+offset,y,18,14);}}
    }else if(kind==='wood'||kind==='roof'){
      for(let x=0;x<96;x+=10){g.strokeStyle=palette[1];g.globalAlpha=.32;g.lineWidth=2;g.beginPath();g.moveTo(x,0);g.lineTo(x+6,96);g.stroke();}
    }else if(kind==='metal'){
      const grad=g.createLinearGradient(0,0,96,96);grad.addColorStop(0,palette[2]);grad.addColorStop(.48,palette[1]);grad.addColorStop(.52,'rgba(255,255,255,.25)');grad.addColorStop(1,palette[0]);g.globalAlpha=.85;g.fillStyle=grad;g.fillRect(0,0,96,96);
    }else if(kind==='glass'||kind==='water'){
      const grad=g.createLinearGradient(0,0,96,96);grad.addColorStop(0,palette[0]);grad.addColorStop(.5,palette[1]);grad.addColorStop(1,palette[2]);g.fillStyle=grad;g.globalAlpha=.88;g.fillRect(0,0,96,96);g.strokeStyle='rgba(255,255,255,.24)';for(let i=0;i<5;i++){g.beginPath();g.moveTo(0,i*20+rand(h,i)*8);g.bezierCurveTo(30,i*20-4,60,i*20+8,96,i*20);g.stroke();}
    }else{
      for(let i=0;i<120;i++){const x=rand(h,i*3)*96,y=rand(h,i*3+1)*96,r=.6+rand(h,i*3+2)*2.2;g.fillStyle=palette[1+(i%2)];g.globalAlpha=.12+.28*rand(h,i+77);g.beginPath();g.arc(x,y,r,0,Math.PI*2);g.fill();}
    }
    g.globalAlpha=1;patternCache.set(key,c);return c;
  }
  function externalTile(ref,kind,seed,fallback){
    const item=imageFor(ref);if(item?.status!=='ready')return proceduralTile(kind,seed,fallback);
    const key=`ext:${item.url}:${kind}:${seed}`;if(patternCache.has(key))return patternCache.get(key);const c=document.createElement('canvas');c.width=128;c.height=128;const g=c.getContext('2d');g.drawImage(item.img,0,0,128,128);g.fillStyle='rgba(0,0,0,.08)';g.fillRect(0,0,128,128);patternCache.set(key,c);return c;
  }
  function fillFor(ctx,{kind='stone',asset_refs=[],seed='0',fallback='#657078'}={}){
    const ref=externalRef(asset_refs),tile=ref?externalTile(ref,kind,seed,fallback):proceduralTile(kind,seed,fallback),pattern=ctx.createPattern(tile,'repeat');return pattern||fallback;
  }
  function terrainFill(ctx,biome,mirror,fallback){return fillFor(ctx,{kind:biome,seed:`terrain:${biome}:${mirror}`,fallback});}
  function provenance(refs,seed,kind){const dna=materialDNA(refs,seed,kind);return{...dna,external_binary_is_canonical:false,distillation:'KRR_MATERIAL_DNA_V2'};}

  globalThis.GENESIS_ASSET_MATERIALIZER_V2=Object.freeze({version:'2.0.0',fillFor,terrainFill,materialDNA,provenance,get cacheSize(){return imageCache.size;}});
})();
