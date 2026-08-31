(() => {
  'use strict';

  const CONFIG = Object.freeze({
    schema: 'janus.genesis.world_shell_save.v1',
    generator_version: 'GENESIS_WORLD_SHELL_R0.1.0',
    world_id: 'GENESIS_ONE_WORLD_R0',
    world_seed: 'genesis-one-world-r0',
    chunk_size: 10,
    visible_radius: 2,
    prewarm_radius: 4,
    save_key: 'janus.genesis.world_shell_r0.save.v1',
    max_mutations: 512,
    max_chronicle_events: 2048,
    max_discovered_chunks: 8192
  });

  const MIRRORS = Object.freeze({
    ORIGIN: {
      label: 'ORIGIN',
      description: 'Clear dawn, natural stone, green living systems.',
      sky_top: '#07131b', sky_bottom: '#182d31', fog: 'rgba(122,205,216,.10)',
      water: '#173b4d', shore: '#746f55', meadow: '#3c704f', forest: '#244c3a', steppe: '#6c6847', highland: '#5b6463', void: '#162229',
      accent: '#73ecff', glow: '#8ef7b8', shadow: '#0a1012', audio_bias: 0.00, form: 'organic'
    },
    NOCTURNE: {
      label: 'NOCTURNE',
      description: 'Cold moon, silver edges, deeper contrast and long shadows.',
      sky_top: '#030611', sky_bottom: '#11192d', fog: 'rgba(91,120,190,.12)',
      water: '#101b3d', shore: '#49475b', meadow: '#263b50', forest: '#172b3d', steppe: '#4e4a5c', highland: '#4e5568', void: '#111525',
      accent: '#9bc4ff', glow: '#d7e8ff', shadow: '#050710', audio_bias: -0.08, form: 'spires'
    },
    AETHER: {
      label: 'AETHER',
      description: 'Iridescent matter, cyan-violet energy and crystalline silhouettes.',
      sky_top: '#080616', sky_bottom: '#142634', fog: 'rgba(131,108,255,.12)',
      water: '#173454', shore: '#6a5876', meadow: '#315b69', forest: '#244653', steppe: '#67526f', highland: '#556579', void: '#15152a',
      accent: '#7af8ff', glow: '#d18cff', shadow: '#090713', audio_bias: 0.08, form: 'crystal'
    },
    EMBER: {
      label: 'EMBER',
      description: 'Warm ash, copper light, red-gold horizons and heavy stone.',
      sky_top: '#150907', sky_bottom: '#3a241d', fog: 'rgba(255,157,98,.10)',
      water: '#25394a', shore: '#80634a', meadow: '#6a5e3f', forest: '#403f31', steppe: '#806445', highland: '#6d5b52', void: '#211712',
      accent: '#ffc27a', glow: '#ff826b', shadow: '#120806', audio_bias: 0.05, form: 'monumental'
    }
  });

  const DIMENSIONS = Object.freeze(['2D', '3D']);
  const CAMERAS = Object.freeze({
    FIRST_PERSON: {label: 'FIRST PERSON', requires_3d: true},
    THIRD_PERSON: {label: 'THIRD PERSON', requires_3d: true},
    ISOMETRIC: {label: 'ISOMETRIC', requires_3d: false}
  });

  const $ = id => document.getElementById(id);
  const canvas = $('genesis-world');
  const ctx = canvas.getContext('2d', {alpha: false});
  const minimap = $('minimap');
  const mapCtx = minimap.getContext('2d');
  const keys = new Set();
  const touchDirections = new Set();
  const chunkCache = new Map();

  let contract = null;
  let entered = false;
  let lastFrame = performance.now();
  let lastChunkKey = '';
  let lastPersistAt = 0;
  let toastTimer = 0;
  let chronicleQueue = Promise.resolve();
  let viewport = {width: innerWidth, height: innerHeight, dpr: 1};
  let dragLook = {active: false, pointerId: null, lastX: 0};

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function hashString(value) {
    let hash = 0x811c9dc5;
    const text = String(value);
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193);
    }
    return hash >>> 0;
  }

  function mix32(value) {
    let x = value >>> 0;
    x ^= x >>> 16;
    x = Math.imul(x, 0x7feb352d);
    x ^= x >>> 15;
    x = Math.imul(x, 0x846ca68b);
    x ^= x >>> 16;
    return x >>> 0;
  }

  const WORLD_SEED_U32 = hashString(CONFIG.world_seed);

  function hash2(ix, iy, salt = 0) {
    const a = Math.imul(ix | 0, 0x1f123bb5);
    const b = Math.imul(iy | 0, 0x5f356495);
    return mix32(WORLD_SEED_U32 ^ a ^ b ^ (salt >>> 0));
  }

  function unitHash(ix, iy, salt = 0) {
    return hash2(ix, iy, salt) / 0xffffffff;
  }

  function smooth(value) {
    return value * value * (3 - 2 * value);
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function valueNoise(x, y, scale, salt) {
    const gx = x / scale;
    const gy = y / scale;
    const x0 = Math.floor(gx);
    const y0 = Math.floor(gy);
    const tx = smooth(gx - x0);
    const ty = smooth(gy - y0);
    const a = lerp(unitHash(x0, y0, salt), unitHash(x0 + 1, y0, salt), tx);
    const b = lerp(unitHash(x0, y0 + 1, salt), unitHash(x0 + 1, y0 + 1, salt), tx);
    return lerp(a, b, ty);
  }

  function fbm(x, y, salt) {
    return (
      valueNoise(x, y, 34, salt) * .46 +
      valueNoise(x, y, 17, salt + 101) * .27 +
      valueNoise(x, y, 8.5, salt + 211) * .17 +
      valueNoise(x, y, 4.25, salt + 307) * .10
    );
  }

  function quantize(value, steps = 1000) {
    return Math.round(value * steps) / steps;
  }

  function canonicalTilePlan(x, y) {
    const elevationNoise = fbm(x, y, 0x1201);
    const moistureNoise = fbm(x + 311, y - 173, 0x2402);
    const weirdNoise = fbm(x - 97, y + 251, 0x3603);
    const hearthDistance = Math.hypot(x, y);
    const hearthLift = Math.max(0, 1 - hearthDistance / 24) * .18;
    const height = quantize(clamp(.12 + elevationNoise * .72 + hearthLift, 0, 1));
    const moisture = quantize(moistureNoise);
    const weirdness = quantize(weirdNoise);
    let biome = 'meadow';
    if (height < .285) biome = 'water';
    else if (height < .345) biome = 'shore';
    else if (height > .79) biome = 'highland';
    else if (weirdness > .84 && height > .52) biome = 'void';
    else if (moisture > .63) biome = 'forest';
    else if (moisture < .29) biome = 'steppe';
    return Object.freeze({
      x, y, height, moisture, weirdness, biome,
      material_recipe: `GENESIS_MATERIAL_${biome.toUpperCase()}_R0`
    });
  }

  function stableValue(value) {
    if (Array.isArray(value)) return `[${value.map(stableValue).join(',')}]`;
    if (value && typeof value === 'object') {
      const keysSorted = Object.keys(value).sort();
      return `{${keysSorted.map(key => `${JSON.stringify(key)}:${stableValue(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function hex32(value) {
    return (value >>> 0).toString(16).padStart(8, '0');
  }

  function objectTypeFor(tile, roll) {
    if (tile.weirdness > .87 && roll > .42) return 'CRYSTAL';
    if (roll > .965) return 'RUIN';
    if (tile.biome === 'forest') return roll < .78 ? 'TREE' : 'ROCK';
    if (tile.biome === 'highland' || tile.biome === 'void') return roll < .72 ? 'ROCK' : 'CRYSTAL';
    if (tile.biome === 'steppe') return roll < .52 ? 'ROCK' : 'TREE';
    if (tile.biome === 'shore') return 'ROCK';
    return roll < .60 ? 'TREE' : 'ROCK';
  }

  function canonicalChunkPlan(cx, cy) {
    const key = `${cx},${cy}`;
    const cached = chunkCache.get(key);
    if (cached) return cached;

    const objects = [];
    const baseX = cx * CONFIG.chunk_size;
    const baseY = cy * CONFIG.chunk_size;

    for (let i = 0; i < 14; i += 1) {
      const px = baseX + Math.floor(unitHash(cx, cy, 0x5000 + i * 13) * CONFIG.chunk_size);
      const py = baseY + Math.floor(unitHash(cx, cy, 0x6000 + i * 17) * CONFIG.chunk_size);
      const tile = canonicalTilePlan(px, py);
      if (tile.biome === 'water') continue;
      const density = tile.biome === 'forest' ? .84 : tile.biome === 'highland' ? .58 : tile.biome === 'void' ? .48 : tile.biome === 'meadow' ? .40 : .27;
      if (unitHash(cx, cy, 0x7000 + i * 19) > density) continue;
      const roll = unitHash(cx, cy, 0x8000 + i * 23);
      const type = objectTypeFor(tile, roll);
      const x = quantize(px + .14 + unitHash(cx, cy, 0x9000 + i * 29) * .72, 100);
      const y = quantize(py + .14 + unitHash(cx, cy, 0xa000 + i * 31) * .72, 100);
      objects.push({id: `${key}:${i}`, type, x, y, recipe: `GENESIS_MESH_${type}_R0`});
    }

    const landmarks = [];
    if (cx === 0 && cy === 0) {
      landmarks.push({id: 'first-fire', type: 'FIRST_FIRE', x: .5, y: .5, recipe: 'GENESIS_ARCH_FIRST_FIRE_R0'});
    } else if (unitHash(cx, cy, 0xb701) < .055) {
      const type = unitHash(cx, cy, 0xb702) < .5 ? 'ARCH' : 'OBELISK';
      landmarks.push({
        id: `landmark:${key}`,
        type,
        x: quantize(baseX + 2 + unitHash(cx, cy, 0xb703) * 6, 100),
        y: quantize(baseY + 2 + unitHash(cx, cy, 0xb704) * 6, 100),
        recipe: `GENESIS_ARCH_${type}_R0`
      });
    }

    const samples = [
      canonicalTilePlan(baseX, baseY),
      canonicalTilePlan(baseX + CONFIG.chunk_size - 1, baseY),
      canonicalTilePlan(baseX, baseY + CONFIG.chunk_size - 1),
      canonicalTilePlan(baseX + CONFIG.chunk_size - 1, baseY + CONFIG.chunk_size - 1),
      canonicalTilePlan(baseX + Math.floor(CONFIG.chunk_size / 2), baseY + Math.floor(CONFIG.chunk_size / 2))
    ].map(tile => [tile.height, tile.moisture, tile.weirdness, tile.biome]);

    const fingerprintInput = {
      generator_version: CONFIG.generator_version,
      world_seed: CONFIG.world_seed,
      chunk: [cx, cy],
      samples,
      objects,
      landmarks
    };

    const plan = Object.freeze({
      key, cx, cy,
      objects: Object.freeze(objects),
      landmarks: Object.freeze(landmarks),
      fact_hash: hex32(hashString(stableValue(fingerprintInput)))
    });
    chunkCache.set(key, plan);
    return plan;
  }

  function defaultSave() {
    return {
      schema: CONFIG.schema,
      generator_version: CONFIG.generator_version,
      world_id: CONFIG.world_id,
      world_seed: CONFIG.world_seed,
      player_position: {x: 0.5, y: 0.5},
      mirror_profile: 'ORIGIN',
      presentation_dimension: '3D',
      camera_mode: 'ISOMETRIC',
      camera_heading: -Math.PI / 4,
      discovered_chunk_coordinates: [],
      explicit_world_mutations: [],
      chronicle_hash_chain: []
    };
  }

  function finiteNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function loadCauses() {
    const fallback = defaultSave();
    try {
      const parsed = JSON.parse(localStorage.getItem(CONFIG.save_key) || 'null');
      if (!parsed || parsed.schema !== CONFIG.schema || parsed.world_id !== CONFIG.world_id || parsed.world_seed !== CONFIG.world_seed) return fallback;
      const mirror = MIRRORS[parsed.mirror_profile] ? parsed.mirror_profile : 'ORIGIN';
      const dimension = DIMENSIONS.includes(parsed.presentation_dimension) ? parsed.presentation_dimension : '3D';
      const camera = CAMERAS[parsed.camera_mode] ? parsed.camera_mode : 'ISOMETRIC';
      const normalizedCamera = dimension === '2D' && CAMERAS[camera].requires_3d ? 'ISOMETRIC' : camera;
      const discovered = Array.isArray(parsed.discovered_chunk_coordinates)
        ? parsed.discovered_chunk_coordinates
          .filter(item => Array.isArray(item) && item.length === 2 && Number.isInteger(item[0]) && Number.isInteger(item[1]))
          .slice(-CONFIG.max_discovered_chunks)
        : [];
      const mutations = Array.isArray(parsed.explicit_world_mutations)
        ? parsed.explicit_world_mutations
          .filter(item => item && item.type === 'PLAYER_MARK' && Number.isFinite(item.x) && Number.isFinite(item.y))
          .slice(-CONFIG.max_mutations)
        : [];
      const chronicle = Array.isArray(parsed.chronicle_hash_chain)
        ? parsed.chronicle_hash_chain
          .filter(item => item && Number.isInteger(item.sequence) && typeof item.event_hash === 'string')
          .slice(-CONFIG.max_chronicle_events)
        : [];
      return {
        schema: CONFIG.schema,
        generator_version: CONFIG.generator_version,
        world_id: CONFIG.world_id,
        world_seed: CONFIG.world_seed,
        player_position: {
          x: finiteNumber(parsed.player_position?.x, .5),
          y: finiteNumber(parsed.player_position?.y, .5)
        },
        mirror_profile: mirror,
        presentation_dimension: dimension,
        camera_mode: normalizedCamera,
        camera_heading: finiteNumber(parsed.camera_heading, -Math.PI / 4),
        discovered_chunk_coordinates: discovered,
        explicit_world_mutations: mutations,
        chronicle_hash_chain: chronicle
      };
    } catch (error) {
      console.warn('Genesis cause save could not be loaded:', error);
      return fallback;
    }
  }

  const save = loadCauses();
  const player = {x: save.player_position.x, y: save.player_position.y};

  function persistCauses() {
    save.player_position = {x: quantize(player.x, 1000), y: quantize(player.y, 1000)};
    save.generator_version = CONFIG.generator_version;
    save.camera_heading = quantize(save.camera_heading, 100000);
    try {
      localStorage.setItem(CONFIG.save_key, JSON.stringify(save));
    } catch (error) {
      showToast(`CAUSE SAVE BLOCKED // ${error.message}`);
    }
  }

  function discoveredSet() {
    return new Set(save.discovered_chunk_coordinates.map(([cx, cy]) => `${cx},${cy}`));
  }

  function currentChunk() {
    return {
      cx: Math.floor(player.x / CONFIG.chunk_size),
      cy: Math.floor(player.y / CONFIG.chunk_size)
    };
  }

  function resize() {
    const dpr = Math.min(2, globalThis.devicePixelRatio || 1);
    viewport = {width: innerWidth, height: innerHeight, dpr};
    const width = Math.max(1, Math.floor(innerWidth * dpr));
    const height = Math.max(1, Math.floor(innerHeight * dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
      canvas.style.width = `${innerWidth}px`;
      canvas.style.height = `${innerHeight}px`;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function mirror() {
    return MIRRORS[save.mirror_profile] || MIRRORS.ORIGIN;
  }

  function colorForBiome(biome) {
    return mirror()[biome] || mirror().meadow;
  }

  function shadeHex(hex, factor) {
    const value = parseInt(hex.slice(1), 16);
    const r = clamp(Math.round(((value >> 16) & 255) * factor), 0, 255);
    const g = clamp(Math.round(((value >> 8) & 255) * factor), 0, 255);
    const b = clamp(Math.round((value & 255) * factor), 0, 255);
    return `rgb(${r},${g},${b})`;
  }

  function mirrorMaterial(tile) {
    const base = colorForBiome(tile.biome);
    const elevationShade = .76 + tile.height * .34;
    const moistureShade = .94 + (tile.moisture - .5) * .08;
    return {
      top: shadeHex(base, elevationShade * moistureShade),
      side: shadeHex(base, .48 + tile.height * .16),
      edge: `${mirror().accent}18`
    };
  }

  function tileMetrics() {
    const base = clamp(Math.min(viewport.width / 24, viewport.height / 15), 28, 52);
    return {tw: base * 1.72, th: base * .86, lift: base * .52};
  }

  function isoPoint(wx, wy, height, flat = false) {
    const {tw, th, lift} = tileMetrics();
    const dx = wx - player.x;
    const dy = wy - player.y;
    return {
      x: viewport.width * .5 + (dx - dy) * tw * .5,
      y: viewport.height * .54 + (dx + dy) * th * .5 - (flat ? 0 : height * lift)
    };
  }

  function drawSky(now) {
    const profile = mirror();
    const gradient = ctx.createLinearGradient(0, 0, 0, viewport.height);
    gradient.addColorStop(0, profile.sky_top);
    gradient.addColorStop(.62, profile.sky_bottom);
    gradient.addColorStop(1, shadeHex(profile.sky_bottom, .55));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, viewport.width, viewport.height);

    const phase = (now / 60000) % 1;
    const glowX = viewport.width * (.18 + phase * .64);
    const glowY = viewport.height * .16;
    const glow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, Math.max(180, viewport.width * .28));
    glow.addColorStop(0, `${profile.accent}22`);
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, viewport.width, viewport.height);
  }

  function visibleChunkBounds() {
    const {cx, cy} = currentChunk();
    return {
      minCx: cx - CONFIG.visible_radius,
      maxCx: cx + CONFIG.visible_radius,
      minCy: cy - CONFIG.visible_radius,
      maxCy: cy + CONFIG.visible_radius
    };
  }

  function visibleObjects() {
    const bounds = visibleChunkBounds();
    const objects = [];
    for (let cy = bounds.minCy; cy <= bounds.maxCy; cy += 1) {
      for (let cx = bounds.minCx; cx <= bounds.maxCx; cx += 1) {
        const plan = canonicalChunkPlan(cx, cy);
        objects.push(...plan.objects, ...plan.landmarks);
      }
    }
    for (const mutation of save.explicit_world_mutations) {
      const cx = Math.floor(mutation.x / CONFIG.chunk_size);
      const cy = Math.floor(mutation.y / CONFIG.chunk_size);
      if (cx >= bounds.minCx && cx <= bounds.maxCx && cy >= bounds.minCy && cy <= bounds.maxCy) objects.push(mutation);
    }
    return objects;
  }

  function drawIsoTile(tile, flat) {
    const material = mirrorMaterial(tile);
    const p0 = isoPoint(tile.x, tile.y, tile.height, flat);
    const p1 = isoPoint(tile.x + 1, tile.y, tile.height, flat);
    const p2 = isoPoint(tile.x + 1, tile.y + 1, tile.height, flat);
    const p3 = isoPoint(tile.x, tile.y + 1, tile.height, flat);
    const sideDrop = flat ? 0 : 3 + tile.height * 8;

    if (!flat && tile.biome !== 'water') {
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineTo(p2.x, p2.y + sideDrop);
      ctx.lineTo(p1.x, p1.y + sideDrop);
      ctx.closePath();
      ctx.fillStyle = material.side;
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(p3.x, p3.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineTo(p2.x, p2.y + sideDrop);
      ctx.lineTo(p3.x, p3.y + sideDrop);
      ctx.closePath();
      ctx.fillStyle = shadeHex(colorForBiome(tile.biome), .38 + tile.height * .12);
      ctx.fill();
    }

    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y);
    ctx.lineTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.lineTo(p3.x, p3.y);
    ctx.closePath();
    ctx.fillStyle = material.top;
    ctx.fill();
    ctx.strokeStyle = flat ? `${mirror().accent}10` : material.edge;
    ctx.lineWidth = flat ? .32 : .45;
    ctx.stroke();

    if (tile.biome === 'water') {
      ctx.strokeStyle = `${mirror().accent}22`;
      ctx.beginPath();
      ctx.moveTo(lerp(p0.x, p3.x, .32), lerp(p0.y, p3.y, .32));
      ctx.lineTo(lerp(p1.x, p2.x, .32), lerp(p1.y, p2.y, .32));
      ctx.stroke();
    }
  }

  function drawIsoTerrain(flat) {
    const bounds = visibleChunkBounds();
    const minX = bounds.minCx * CONFIG.chunk_size;
    const maxX = (bounds.maxCx + 1) * CONFIG.chunk_size - 1;
    const minY = bounds.minCy * CONFIG.chunk_size;
    const maxY = (bounds.maxCy + 1) * CONFIG.chunk_size - 1;
    const minSum = minX + minY;
    const maxSum = maxX + maxY;
    for (let sum = minSum; sum <= maxSum; sum += 1) {
      const startX = Math.max(minX, sum - maxY);
      const endX = Math.min(maxX, sum - minY);
      for (let x = startX; x <= endX; x += 1) {
        drawIsoTile(canonicalTilePlan(x, sum - x), flat);
      }
    }
  }

  function objectHeight(object) {
    return canonicalTilePlan(Math.floor(object.x), Math.floor(object.y)).height;
  }

  function drawIsoObject(object, flat) {
    const profile = mirror();
    const base = isoPoint(object.x, object.y, objectHeight(object), flat);
    const {tw} = tileMetrics();
    const scale = tw / 70;
    ctx.save();
    ctx.translate(base.x, base.y);

    if (flat) {
      const radius = object.type === 'FIRST_FIRE' ? 9 : object.type === 'PLAYER_MARK' ? 6 : 4.5;
      ctx.strokeStyle = object.type === 'PLAYER_MARK' ? profile.glow : profile.accent;
      ctx.fillStyle = object.type === 'FIRST_FIRE' ? profile.glow : `${profile.accent}55`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      if (object.type === 'TREE') {
        ctx.moveTo(0, -radius); ctx.lineTo(radius, radius); ctx.lineTo(-radius, radius); ctx.closePath();
      } else if (object.type === 'CRYSTAL') {
        ctx.moveTo(0, -radius * 1.3); ctx.lineTo(radius, 0); ctx.lineTo(0, radius * 1.3); ctx.lineTo(-radius, 0); ctx.closePath();
      } else {
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
      }
      ctx.fill(); ctx.stroke();
      ctx.restore();
      return;
    }

    ctx.beginPath();
    ctx.ellipse(0, 3, 8 * scale, 3 * scale, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,.24)';
    ctx.fill();

    if (object.type === 'TREE') {
      ctx.strokeStyle = shadeHex(profile.steppe, .58);
      ctx.lineWidth = 3 * scale;
      ctx.beginPath(); ctx.moveTo(0, 2); ctx.lineTo(0, -18 * scale); ctx.stroke();
      ctx.fillStyle = shadeHex(profile.forest, 1.18);
      ctx.beginPath();
      ctx.moveTo(0, -39 * scale); ctx.lineTo(15 * scale, -15 * scale); ctx.lineTo(7 * scale, -15 * scale);
      ctx.lineTo(17 * scale, -3 * scale); ctx.lineTo(-17 * scale, -3 * scale); ctx.lineTo(-7 * scale, -15 * scale);
      ctx.lineTo(-15 * scale, -15 * scale); ctx.closePath(); ctx.fill();
    } else if (object.type === 'ROCK') {
      ctx.fillStyle = shadeHex(profile.highland, 1.12);
      ctx.strokeStyle = `${profile.accent}44`;
      ctx.beginPath(); ctx.moveTo(-11 * scale, 0); ctx.lineTo(-7 * scale, -12 * scale); ctx.lineTo(2 * scale, -17 * scale); ctx.lineTo(12 * scale, -8 * scale); ctx.lineTo(10 * scale, 0); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (object.type === 'CRYSTAL') {
      ctx.fillStyle = `${profile.glow}aa`;
      ctx.strokeStyle = `${profile.accent}dd`;
      ctx.beginPath(); ctx.moveTo(0, -28 * scale); ctx.lineTo(9 * scale, -8 * scale); ctx.lineTo(4 * scale, 0); ctx.lineTo(-6 * scale, -2 * scale); ctx.lineTo(-10 * scale, -11 * scale); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (object.type === 'RUIN') {
      ctx.strokeStyle = shadeHex(profile.highland, 1.28); ctx.lineWidth = 4 * scale;
      ctx.beginPath(); ctx.moveTo(-10 * scale, 0); ctx.lineTo(-10 * scale, -27 * scale); ctx.lineTo(-2 * scale, -31 * scale); ctx.moveTo(9 * scale, 0); ctx.lineTo(9 * scale, -18 * scale); ctx.stroke();
    } else if (object.type === 'ARCH') {
      ctx.strokeStyle = shadeHex(profile.highland, 1.3); ctx.lineWidth = 5 * scale;
      ctx.beginPath(); ctx.moveTo(-13 * scale, 0); ctx.lineTo(-13 * scale, -29 * scale); ctx.quadraticCurveTo(0, -42 * scale, 13 * scale, -29 * scale); ctx.lineTo(13 * scale, 0); ctx.stroke();
    } else if (object.type === 'OBELISK') {
      ctx.fillStyle = shadeHex(profile.highland, 1.26); ctx.strokeStyle = `${profile.accent}88`;
      ctx.beginPath(); ctx.moveTo(0, -48 * scale); ctx.lineTo(9 * scale, -34 * scale); ctx.lineTo(7 * scale, 0); ctx.lineTo(-7 * scale, 0); ctx.lineTo(-9 * scale, -34 * scale); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (object.type === 'FIRST_FIRE') {
      const radius = 18 * scale;
      const glow = ctx.createRadialGradient(0, -5 * scale, 0, 0, -5 * scale, radius * 2.2);
      glow.addColorStop(0, `${profile.glow}cc`); glow.addColorStop(.4, `${profile.accent}55`); glow.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = glow; ctx.fillRect(-radius * 2.2, -radius * 2.6, radius * 4.4, radius * 4.4);
      ctx.fillStyle = profile.glow;
      ctx.beginPath(); ctx.moveTo(0, -29 * scale); ctx.quadraticCurveTo(14 * scale, -12 * scale, 0, -3 * scale); ctx.quadraticCurveTo(-12 * scale, -12 * scale, 0, -29 * scale); ctx.fill();
    } else if (object.type === 'PLAYER_MARK') {
      ctx.strokeStyle = profile.accent; ctx.lineWidth = 2.3 * scale;
      ctx.beginPath(); ctx.arc(0, -8 * scale, 8 * scale, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, 1); ctx.lineTo(0, -25 * scale); ctx.stroke();
      ctx.fillStyle = profile.glow; ctx.beginPath(); ctx.arc(0, -26 * scale, 2.8 * scale, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  function drawIsoPlayer(flat) {
    const tile = canonicalTilePlan(Math.floor(player.x), Math.floor(player.y));
    const point = isoPoint(player.x, player.y, tile.height, flat);
    const profile = mirror();
    ctx.save();
    ctx.translate(point.x, point.y);
    if (flat) {
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = profile.accent;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(0, 0, 6, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      const dx = Math.cos(save.camera_heading) * 12;
      const dy = Math.sin(save.camera_heading) * 12;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(dx, dy); ctx.stroke();
    } else {
      ctx.fillStyle = 'rgba(0,0,0,.34)';
      ctx.beginPath(); ctx.ellipse(0, 5, 12, 4, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#f4fbff'; ctx.lineWidth = 2.2;
      ctx.beginPath(); ctx.arc(0, -21, 5, 0, Math.PI * 2); ctx.moveTo(0, -16); ctx.lineTo(0, -2); ctx.moveTo(0, -11); ctx.lineTo(-8, -5); ctx.moveTo(0, -11); ctx.lineTo(8, -5); ctx.moveTo(0, -2); ctx.lineTo(-6, 7); ctx.moveTo(0, -2); ctx.lineTo(6, 7); ctx.stroke();
      ctx.fillStyle = profile.accent; ctx.beginPath(); ctx.arc(0, -21, 2, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  const TERRAIN_Z_SCALE = 3.2;

  function cameraState() {
    const heading = save.camera_heading;
    const forward = {x: Math.cos(heading), y: Math.sin(heading)};
    const tile = canonicalTilePlan(Math.floor(player.x), Math.floor(player.y));
    const groundZ = tile.height * TERRAIN_Z_SCALE;

    if (save.camera_mode === 'FIRST_PERSON') {
      return {
        x: player.x,
        y: player.y,
        z: groundZ + 1.62,
        heading,
        pitch: .06,
        focal: Math.max(360, viewport.width * .78),
        horizon: viewport.height * .51
      };
    }

    if (save.camera_mode === 'THIRD_PERSON') {
      return {
        x: player.x - forward.x * 6.2,
        y: player.y - forward.y * 6.2,
        z: groundZ + 4.8,
        heading,
        pitch: .42,
        focal: Math.max(340, viewport.width * .72),
        horizon: viewport.height * .48
      };
    }

    return null;
  }

  function projectPerspective(wx, wy, wz, camera) {
    const dx = wx - camera.x;
    const dy = wy - camera.y;
    const dz = wz - camera.z;
    const forwardX = Math.cos(camera.heading);
    const forwardY = Math.sin(camera.heading);
    const rightX = -forwardY;
    const rightY = forwardX;
    const cosPitch = Math.cos(camera.pitch);
    const sinPitch = Math.sin(camera.pitch);
    const horizontalForward = dx * forwardX + dy * forwardY;
    const horizontalRight = dx * rightX + dy * rightY;
    const depth = horizontalForward * cosPitch - dz * sinPitch;
    const vertical = horizontalForward * sinPitch + dz * cosPitch;
    if (depth <= .18) return null;
    return {
      x: viewport.width * .5 + camera.focal * horizontalRight / depth,
      y: camera.horizon - camera.focal * vertical / depth,
      depth
    };
  }

  function terrainRenderRadius() {
    return save.camera_mode === 'FIRST_PERSON' ? 20 : 18;
  }

  function perspectiveTiles(camera) {
    const radius = terrainRenderRadius();
    const minX = Math.floor(player.x) - radius;
    const maxX = Math.floor(player.x) + radius;
    const minY = Math.floor(player.y) - radius;
    const maxY = Math.floor(player.y) + radius;
    const tiles = [];
    for (let y = minY; y <= maxY; y += 1) {
      for (let x = minX; x <= maxX; x += 1) {
        const tile = canonicalTilePlan(x, y);
        const center = projectPerspective(x + .5, y + .5, tile.height * TERRAIN_Z_SCALE, camera);
        if (!center || center.depth > 42) continue;
        tiles.push({tile, depth: center.depth});
      }
    }
    tiles.sort((a, b) => b.depth - a.depth);
    return tiles;
  }

  function drawPerspectiveTile(tile, camera) {
    const z = tile.height * TERRAIN_Z_SCALE;
    const p0 = projectPerspective(tile.x, tile.y, z, camera);
    const p1 = projectPerspective(tile.x + 1, tile.y, z, camera);
    const p2 = projectPerspective(tile.x + 1, tile.y + 1, z, camera);
    const p3 = projectPerspective(tile.x, tile.y + 1, z, camera);
    if (!p0 || !p1 || !p2 || !p3) return;
    const material = mirrorMaterial(tile);

    const screenPoints = [p0, p1, p2, p3];
    if (screenPoints.every(point => point.x < -100 || point.x > viewport.width + 100 || point.y < -100 || point.y > viewport.height + 100)) return;

    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(p3.x, p3.y); ctx.closePath();
    ctx.fillStyle = material.top;
    ctx.fill();
    ctx.strokeStyle = `${mirror().accent}12`;
    ctx.lineWidth = .45;
    ctx.stroke();

    if (tile.biome !== 'water') {
      const lowerZ = Math.max(0, z - .35 - tile.height * .5);
      const q1 = projectPerspective(tile.x + 1, tile.y, lowerZ, camera);
      const q2 = projectPerspective(tile.x + 1, tile.y + 1, lowerZ, camera);
      if (q1 && q2) {
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.lineTo(q2.x, q2.y); ctx.lineTo(q1.x, q1.y); ctx.closePath();
        ctx.fillStyle = material.side;
        ctx.fill();
      }
    }
  }

  function objectVisualHeight(type) {
    if (type === 'TREE') return 2.8;
    if (type === 'OBELISK') return 3.4;
    if (type === 'ARCH') return 2.8;
    if (type === 'FIRST_FIRE') return 1.8;
    if (type === 'CRYSTAL') return 2.0;
    if (type === 'RUIN') return 2.2;
    if (type === 'PLAYER_MARK') return 1.6;
    return 1.1;
  }

  function drawPerspectiveObject(object, camera) {
    const tile = canonicalTilePlan(Math.floor(object.x), Math.floor(object.y));
    const ground = tile.height * TERRAIN_Z_SCALE;
    const top = ground + objectVisualHeight(object.type);
    const baseP = projectPerspective(object.x, object.y, ground, camera);
    const topP = projectPerspective(object.x, object.y, top, camera);
    if (!baseP || !topP || baseP.depth > 36) return;
    if (baseP.x < -150 || baseP.x > viewport.width + 150 || baseP.y < -200 || baseP.y > viewport.height + 200) return;

    const profile = mirror();
    const size = clamp(camera.focal / baseP.depth * .055, 2.5, 70);
    ctx.save();

    if (object.type === 'TREE') {
      ctx.strokeStyle = shadeHex(profile.steppe, .65);
      ctx.lineWidth = clamp(size * .17, 1, 9);
      ctx.beginPath(); ctx.moveTo(baseP.x, baseP.y); ctx.lineTo(topP.x, topP.y + size * .4); ctx.stroke();
      ctx.fillStyle = shadeHex(profile.forest, 1.18);
      ctx.beginPath();
      ctx.moveTo(topP.x, topP.y);
      ctx.lineTo(topP.x + size * .8, topP.y + size * 1.45);
      ctx.lineTo(topP.x - size * .8, topP.y + size * 1.45);
      ctx.closePath(); ctx.fill();
    } else if (object.type === 'ROCK') {
      ctx.fillStyle = shadeHex(profile.highland, 1.12);
      ctx.beginPath();
      ctx.ellipse(baseP.x, baseP.y - size * .25, size * .72, size * .48, 0, 0, Math.PI * 2);
      ctx.fill();
    } else if (object.type === 'CRYSTAL') {
      ctx.fillStyle = `${profile.glow}bb`;
      ctx.strokeStyle = profile.accent;
      ctx.beginPath();
      ctx.moveTo(topP.x, topP.y);
      ctx.lineTo(baseP.x + size * .55, baseP.y);
      ctx.lineTo(baseP.x, baseP.y + size * .18);
      ctx.lineTo(baseP.x - size * .55, baseP.y);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (object.type === 'ARCH') {
      ctx.strokeStyle = shadeHex(profile.highland, 1.3);
      ctx.lineWidth = clamp(size * .22, 2, 12);
      ctx.beginPath();
      ctx.moveTo(baseP.x - size * .7, baseP.y);
      ctx.lineTo(baseP.x - size * .7, topP.y + size * .45);
      ctx.quadraticCurveTo(baseP.x, topP.y - size * .2, baseP.x + size * .7, topP.y + size * .45);
      ctx.lineTo(baseP.x + size * .7, baseP.y);
      ctx.stroke();
    } else if (object.type === 'OBELISK') {
      ctx.fillStyle = shadeHex(profile.highland, 1.25);
      ctx.strokeStyle = `${profile.accent}aa`;
      ctx.beginPath();
      ctx.moveTo(topP.x, topP.y);
      ctx.lineTo(baseP.x + size * .35, baseP.y - size * .3);
      ctx.lineTo(baseP.x + size * .28, baseP.y);
      ctx.lineTo(baseP.x - size * .28, baseP.y);
      ctx.lineTo(baseP.x - size * .35, baseP.y - size * .3);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (object.type === 'FIRST_FIRE') {
      const glow = ctx.createRadialGradient(baseP.x, topP.y + size * .4, 0, baseP.x, topP.y + size * .4, size * 2.4);
      glow.addColorStop(0, `${profile.glow}dd`); glow.addColorStop(.42, `${profile.accent}66`); glow.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = glow; ctx.fillRect(baseP.x - size * 2.4, topP.y - size * 1.6, size * 4.8, size * 4.8);
      ctx.fillStyle = profile.glow;
      ctx.beginPath(); ctx.moveTo(topP.x, topP.y); ctx.quadraticCurveTo(baseP.x + size, baseP.y - size, baseP.x, baseP.y); ctx.quadraticCurveTo(baseP.x - size, baseP.y - size, topP.x, topP.y); ctx.fill();
    } else if (object.type === 'PLAYER_MARK') {
      ctx.strokeStyle = profile.accent;
      ctx.lineWidth = clamp(size * .12, 1.2, 6);
      ctx.beginPath(); ctx.moveTo(baseP.x, baseP.y); ctx.lineTo(topP.x, topP.y); ctx.stroke();
      ctx.beginPath(); ctx.arc(topP.x, topP.y, size * .38, 0, Math.PI * 2); ctx.stroke();
    } else {
      ctx.strokeStyle = shadeHex(profile.highland, 1.2);
      ctx.lineWidth = clamp(size * .16, 1, 8);
      ctx.beginPath(); ctx.moveTo(baseP.x, baseP.y); ctx.lineTo(topP.x, topP.y); ctx.stroke();
    }

    ctx.restore();
  }

  function drawPerspectivePlayer(camera) {
    if (save.camera_mode !== 'THIRD_PERSON') return;
    const tile = canonicalTilePlan(Math.floor(player.x), Math.floor(player.y));
    const ground = tile.height * TERRAIN_Z_SCALE;
    const foot = projectPerspective(player.x, player.y, ground, camera);
    const head = projectPerspective(player.x, player.y, ground + 1.75, camera);
    if (!foot || !head) return;
    const profile = mirror();
    const radius = clamp(camera.focal / foot.depth * .028, 3, 18);
    ctx.strokeStyle = '#f4fbff';
    ctx.lineWidth = clamp(radius * .22, 1.5, 5);
    ctx.beginPath();
    ctx.arc(head.x, head.y, radius * .34, 0, Math.PI * 2);
    ctx.moveTo((head.x + foot.x) / 2, (head.y + foot.y) / 2);
    ctx.lineTo(foot.x, foot.y);
    ctx.stroke();
    ctx.fillStyle = profile.accent;
    ctx.beginPath(); ctx.arc(head.x, head.y, radius * .13, 0, Math.PI * 2); ctx.fill();
  }

  function drawReticle() {
    if (save.camera_mode !== 'FIRST_PERSON') return;
    const profile = mirror();
    const x = viewport.width / 2;
    const y = viewport.height / 2;
    ctx.strokeStyle = `${profile.accent}88`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x - 8, y); ctx.lineTo(x - 3, y);
    ctx.moveTo(x + 3, y); ctx.lineTo(x + 8, y);
    ctx.moveTo(x, y - 8); ctx.lineTo(x, y - 3);
    ctx.moveTo(x, y + 3); ctx.lineTo(x, y + 8);
    ctx.stroke();
  }

  function drawAtmosphere(now, perspective = false) {
    const profile = mirror();
    const tile = canonicalTilePlan(Math.floor(player.x), Math.floor(player.y));
    const fog = ctx.createLinearGradient(0, viewport.height * .2, 0, viewport.height);
    fog.addColorStop(0, 'rgba(0,0,0,0)');
    fog.addColorStop(.72, profile.fog);
    fog.addColorStop(1, `${profile.shadow}${perspective ? 'aa' : '88'}`);
    ctx.fillStyle = fog;
    ctx.fillRect(0, 0, viewport.width, viewport.height);

    if (tile.moisture > .64) {
      ctx.strokeStyle = `${profile.accent}22`;
      ctx.lineWidth = 1;
      const count = Math.round(8 + tile.moisture * 18);
      for (let i = 0; i < count; i += 1) {
        const h = mix32(WORLD_SEED_U32 + i * 977);
        const x = ((h % 10000) / 10000 * viewport.width + now * .018 * (i % 3 + 1)) % viewport.width;
        const y = ((mix32(h + 71) % 10000) / 10000 * viewport.height + now * .045) % viewport.height;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 5, y + 10); ctx.stroke();
      }
    }
  }

  function renderIsometric(now, flat) {
    drawSky(now);
    drawIsoTerrain(flat);
    const objects = visibleObjects().sort((a, b) => (a.x + a.y) - (b.x + b.y));
    for (const object of objects) drawIsoObject(object, flat);
    drawIsoPlayer(flat);
    drawAtmosphere(now, false);
  }

  function renderPerspective(now) {
    drawSky(now);
    const camera = cameraState();
    if (!camera) return renderIsometric(now, false);
    for (const item of perspectiveTiles(camera)) drawPerspectiveTile(item.tile, camera);

    const objects = visibleObjects()
      .map(object => {
        const ground = objectHeight(object) * TERRAIN_Z_SCALE;
        const point = projectPerspective(object.x, object.y, ground, camera);
        return {object, depth: point?.depth ?? -1};
      })
      .filter(item => item.depth > 0 && item.depth < 38)
      .sort((a, b) => b.depth - a.depth);

    for (const item of objects) drawPerspectiveObject(item.object, camera);
    drawPerspectivePlayer(camera);
    drawAtmosphere(now, true);
    drawReticle();
  }

  function render(now) {
    resize();
    if (save.presentation_dimension === '2D') {
      renderIsometric(now, true);
      return;
    }
    if (save.camera_mode === 'ISOMETRIC') {
      renderIsometric(now, false);
      return;
    }
    renderPerspective(now);
  }

  function prewarmAround(cx, cy) {
    for (let oy = -CONFIG.prewarm_radius; oy <= CONFIG.prewarm_radius; oy += 1) {
      for (let ox = -CONFIG.prewarm_radius; ox <= CONFIG.prewarm_radius; ox += 1) {
        canonicalChunkPlan(cx + ox, cy + oy);
      }
    }
    while (chunkCache.size > 640) {
      const first = chunkCache.keys().next().value;
      chunkCache.delete(first);
    }
  }

  async function sha256Hex(text) {
    if (globalThis.crypto?.subtle) {
      const bytes = new TextEncoder().encode(text);
      const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    }
    return `fnv1a32-${hex32(hashString(text))}`;
  }

  function appendChronicleEvent(payload) {
    chronicleQueue = chronicleQueue.then(async () => {
      if (save.chronicle_hash_chain.length >= CONFIG.max_chronicle_events) return;
      const sequence = save.chronicle_hash_chain.length + 1;
      const previous_hash = save.chronicle_hash_chain.at(-1)?.event_hash || 'GENESIS_ORIGIN';
      const body = {sequence, previous_hash, ...payload};
      const event_hash = await sha256Hex(stableValue(body));
      save.chronicle_hash_chain.push({...body, event_hash});
      persistCauses();
      renderChronicle();
    }).catch(error => console.error('Genesis Chronicle append failed:', error));
    return chronicleQueue;
  }

  function discoverChunk(cx, cy) {
    const key = `${cx},${cy}`;
    const known = discoveredSet();
    if (known.has(key) || save.discovered_chunk_coordinates.length >= CONFIG.max_discovered_chunks) return false;
    const plan = canonicalChunkPlan(cx, cy);
    save.discovered_chunk_coordinates.push([cx, cy]);
    persistCauses();
    appendChronicleEvent({type: 'CHUNK_DISCOVERED', chunk: [cx, cy], fact_hash: plan.fact_hash});
    $('discovered-count').textContent = String(save.discovered_chunk_coordinates.length);
    audioForge()?.cue('discovery', .55);
    showToast(`WORLD REMEMBERS // CHUNK ${key} // ${plan.fact_hash}`);
    return true;
  }

  function placeMark() {
    if (!entered) return showToast('ENTER GENESIS BEFORE WRITING A MARK');
    if (save.explicit_world_mutations.length >= CONFIG.max_mutations) return showToast('LOCAL MUTATION CAP REACHED');
    const x = quantize(Math.round(player.x * 4) / 4, 100);
    const y = quantize(Math.round(player.y * 4) / 4, 100);
    const sequence = save.explicit_world_mutations.length + 1;
    const id = `mark-${hex32(hashString(`${CONFIG.world_seed}|${sequence}|${x}|${y}`))}`;
    if (save.explicit_world_mutations.some(item => item.id === id)) return;
    const mutation = {id, type: 'PLAYER_MARK', x, y, recipe: 'GENESIS_PLAYER_MARK_R0'};
    save.explicit_world_mutations.push(mutation);
    persistCauses();
    appendChronicleEvent({
      type: 'PLAYER_MARK_PLACED',
      mutation_id: id,
      position: [x, y],
      chunk: [Math.floor(x / CONFIG.chunk_size), Math.floor(y / CONFIG.chunk_size)]
    });
    audioForge()?.cue('resolve', .65);
    showToast(`MARK WRITTEN AS CAUSE // ${id.toUpperCase()}`);
  }

  function returnToHearth() {
    player.x = .5;
    player.y = .5;
    persistCauses();
    lastChunkKey = '';
    showToast('RETURNED TO FIRST FIRE // HISTORY PRESERVED');
  }

  function deriveAudioState() {
    const tile = canonicalTilePlan(Math.floor(player.x), Math.floor(player.y));
    const plan = canonicalChunkPlan(currentChunk().cx, currentChunk().cy);
    const objectDensity = clamp((plan.objects.length + plan.landmarks.length) / 12, 0, 1);
    const hearth = clamp(1 - Math.hypot(player.x, player.y) / 60, 0, 1);
    const bias = mirror().audio_bias;
    return {
      entropy: clamp(.12 + objectDensity * .58 + tile.weirdness * .22 + bias, 0, 1),
      depth: clamp(.18 + tile.height * .72 - bias * .2, 0, 1),
      portal_energy: clamp(.12 + hearth * .68 + tile.weirdness * .16 + bias, 0, 1),
      danger: clamp((tile.biome === 'void' ? .55 : tile.biome === 'highland' ? .24 : .08) + tile.weirdness * .18, 0, 1),
      weather_intensity: clamp(.10 + tile.moisture * .62 + Math.abs(bias), 0, 1)
    };
  }

  function audioForge() {
    return globalThis.GENESIS_AUDIO_FORGE || null;
  }

  function updateAudioPresentation() {
    const forge = audioForge();
    if (!forge) return;
    try {
      forge.setWorldState(deriveAudioState());
    } catch (error) {
      console.warn('Audio presentation update rejected:', error);
    }
    const state = forge.getState();
    $('audio-toggle').textContent = state.enabled ? 'AUDIO: ON' : 'AUDIO: OFF';
    $('audio-toggle').classList.toggle('active', Boolean(state.enabled));
  }

  async function toggleAudio() {
    const forge = audioForge();
    if (!forge) return showToast('AUDIO FORGE RUNTIME UNAVAILABLE');
    const state = forge.getState();
    if (state.enabled) {
      forge.disable();
      updateAudioPresentation();
      showToast('AUDIO MIRROR MUTED // WORLD UNCHANGED');
      return;
    }
    try {
      const enabled = await forge.enable({
        seed: hashString(`${CONFIG.world_seed}|${save.mirror_profile}`),
        world_state: deriveAudioState()
      });
      updateAudioPresentation();
      showToast(enabled ? 'HELIOS-DERIVED AUDIO FORGE ONLINE' : 'WEB AUDIO NOT AVAILABLE');
    } catch (error) {
      showToast(`AUDIO FORGE BLOCKED // ${error.message}`);
    }
  }

  function renderMirrorOptions() {
    const root = $('mirror-options');
    root.replaceChildren();
    for (const [id, profile] of Object.entries(MIRRORS)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'mirror-option';
      button.classList.toggle('selected', save.mirror_profile === id);
      const title = document.createElement('strong');
      title.textContent = profile.label;
      const description = document.createElement('span');
      description.textContent = profile.description;
      button.append(title, description);
      button.addEventListener('click', () => setMirror(id));
      root.append(button);
    }
  }

  function renderViewOptions() {
    const dimensionRoot = $('dimension-options');
    const cameraRoot = $('camera-options');
    dimensionRoot.replaceChildren();
    cameraRoot.replaceChildren();

    for (const dimension of DIMENSIONS) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'view-option';
      button.textContent = dimension;
      button.classList.toggle('selected', save.presentation_dimension === dimension);
      button.addEventListener('click', () => setDimension(dimension));
      dimensionRoot.append(button);
    }

    for (const [cameraId, camera] of Object.entries(CAMERAS)) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'view-option';
      button.textContent = camera.label;
      button.classList.toggle('selected', save.camera_mode === cameraId);
      button.addEventListener('click', () => setCamera(cameraId));
      cameraRoot.append(button);
    }

    $('view-combination').textContent = `${save.presentation_dimension} / ${CAMERAS[save.camera_mode].label}`;
  }

  function canonicalFactHashNow() {
    const {cx, cy} = currentChunk();
    return canonicalChunkPlan(cx, cy).fact_hash;
  }

  function verifyPresentationOnlyChange(before, label) {
    const after = canonicalFactHashNow();
    $('mirror-fact-hash').textContent = after;
    updateWorldHud();
    renderViewOptions();
    persistCauses();
    showToast(`${label} // FACTS ${before === after ? 'UNCHANGED' : 'INTEGRITY ERROR'}`);
  }

  function setMirror(id) {
    if (!MIRRORS[id] || id === save.mirror_profile) return;
    const before = canonicalFactHashNow();
    save.mirror_profile = id;
    renderMirrorOptions();
    updateAudioPresentation();
    verifyPresentationOnlyChange(before, `MIRROR ${id}`);
  }

  function setDimension(dimension) {
    if (!DIMENSIONS.includes(dimension) || dimension === save.presentation_dimension) return;
    const before = canonicalFactHashNow();
    save.presentation_dimension = dimension;
    if (dimension === '2D' && CAMERAS[save.camera_mode].requires_3d) save.camera_mode = 'ISOMETRIC';
    verifyPresentationOnlyChange(before, `DIMENSION ${dimension}`);
  }

  function setCamera(cameraId) {
    if (!CAMERAS[cameraId] || cameraId === save.camera_mode) return;
    const before = canonicalFactHashNow();
    save.camera_mode = cameraId;
    if (CAMERAS[cameraId].requires_3d) save.presentation_dimension = '3D';
    verifyPresentationOnlyChange(before, `CAMERA ${CAMERAS[cameraId].label}`);
  }

  function rotateCamera(delta) {
    if (save.camera_mode === 'ISOMETRIC') return;
    save.camera_heading += delta;
    if (save.camera_heading > Math.PI) save.camera_heading -= Math.PI * 2;
    if (save.camera_heading < -Math.PI) save.camera_heading += Math.PI * 2;
    persistCauses();
    updateWorldHud();
  }

  function renderChronicle() {
    const root = $('chronicle-list');
    root.replaceChildren();
    const events = save.chronicle_hash_chain.slice(-18).reverse();
    if (!events.length) {
      const empty = document.createElement('li');
      empty.innerHTML = '<span class="seq">00</span><div><span class="event">NO EVENTS YET</span><span class="meta">Walk into the first chunk or leave a mark.</span></div><span class="hash">—</span>';
      root.append(empty);
      return;
    }
    for (const event of events) {
      const item = document.createElement('li');
      const seq = document.createElement('span');
      seq.className = 'seq';
      seq.textContent = String(event.sequence).padStart(2, '0');
      const body = document.createElement('div');
      const type = document.createElement('span');
      type.className = 'event';
      type.textContent = event.type;
      const meta = document.createElement('span');
      meta.className = 'meta';
      meta.textContent = event.chunk ? `chunk ${event.chunk.join(',')}` : event.position ? `position ${event.position.join(',')}` : 'world event';
      body.append(type, meta);
      const hash = document.createElement('span');
      hash.className = 'hash';
      hash.textContent = String(event.event_hash).slice(0, 10);
      item.append(seq, body, hash);
      root.append(item);
    }
  }

  function updateWorldHud() {
    const {cx, cy} = currentChunk();
    const plan = canonicalChunkPlan(cx, cy);
    $('world-id').textContent = CONFIG.world_id;
    $('chunk-coords').textContent = `${cx},${cy}`;
    $('fact-hash').textContent = plan.fact_hash;
    $('mirror-name').textContent = save.mirror_profile;
    $('dimension-name').textContent = save.presentation_dimension;
    $('camera-name').textContent = CAMERAS[save.camera_mode].label;
    $('visible-count').textContent = String((CONFIG.visible_radius * 2 + 1) ** 2);
    $('prewarm-count').textContent = String((CONFIG.prewarm_radius * 2 + 1) ** 2);
    $('discovered-count').textContent = String(save.discovered_chunk_coordinates.length);
    $('view-toggle').textContent = `VIEW: ${save.presentation_dimension}/${save.camera_mode === 'ISOMETRIC' ? 'ISO' : save.camera_mode === 'FIRST_PERSON' ? '1P' : '3P'}`;
  }

  function drawMinimap() {
    const profile = mirror();
    const width = minimap.width;
    const height = minimap.height;
    const {cx, cy} = currentChunk();
    const unit = 13;
    mapCtx.clearRect(0, 0, width, height);
    const bg = mapCtx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, width * .7);
    bg.addColorStop(0, `${profile.sky_bottom}ee`);
    bg.addColorStop(1, '#020406');
    mapCtx.fillStyle = bg;
    mapCtx.fillRect(0, 0, width, height);

    const discovered = discoveredSet();
    for (const key of discovered) {
      const [dx, dy] = key.split(',').map(Number);
      const sx = width / 2 + (dx - cx) * unit;
      const sy = height / 2 + (dy - cy) * unit;
      if (sx < -unit || sy < -unit || sx > width + unit || sy > height + unit) continue;
      mapCtx.fillStyle = `${profile.accent}55`;
      mapCtx.fillRect(sx - 4, sy - 4, 8, 8);
    }

    mapCtx.strokeStyle = `${profile.glow}55`;
    mapCtx.strokeRect(
      width / 2 - CONFIG.visible_radius * unit - unit / 2,
      height / 2 - CONFIG.visible_radius * unit - unit / 2,
      (CONFIG.visible_radius * 2 + 1) * unit,
      (CONFIG.visible_radius * 2 + 1) * unit
    );

    for (const mutation of save.explicit_world_mutations) {
      const mx = Math.floor(mutation.x / CONFIG.chunk_size);
      const my = Math.floor(mutation.y / CONFIG.chunk_size);
      const sx = width / 2 + (mx - cx) * unit;
      const sy = height / 2 + (my - cy) * unit;
      mapCtx.fillStyle = profile.glow;
      mapCtx.beginPath(); mapCtx.arc(sx, sy, 2.3, 0, Math.PI * 2); mapCtx.fill();
    }

    mapCtx.fillStyle = '#ffffff';
    mapCtx.beginPath(); mapCtx.arc(width / 2, height / 2, 3.2, 0, Math.PI * 2); mapCtx.fill();

    if (save.camera_mode !== 'ISOMETRIC') {
      mapCtx.strokeStyle = profile.accent;
      mapCtx.beginPath();
      mapCtx.moveTo(width / 2, height / 2);
      mapCtx.lineTo(
        width / 2 + Math.cos(save.camera_heading) * 15,
        height / 2 + Math.sin(save.camera_heading) * 15
      );
      mapCtx.stroke();
    }
  }

  function checkChunkTransition() {
    const {cx, cy} = currentChunk();
    const key = `${cx},${cy}`;
    if (key === lastChunkKey) return;
    lastChunkKey = key;
    prewarmAround(cx, cy);
    discoverChunk(cx, cy);
    updateWorldHud();
    drawMinimap();
    updateAudioPresentation();
  }

  function screenMovementVector() {
    let sx = 0;
    let sy = 0;
    if (keys.has('w') || keys.has('arrowup') || touchDirections.has('up')) sy -= 1;
    if (keys.has('s') || keys.has('arrowdown') || touchDirections.has('down')) sy += 1;
    if (keys.has('a') || keys.has('arrowleft') || touchDirections.has('left')) sx -= 1;
    if (keys.has('d') || keys.has('arrowright') || touchDirections.has('right')) sx += 1;
    if (!sx && !sy) return {x: 0, y: 0};
    const length = Math.hypot(sx, sy) || 1;
    return {x: sx / length, y: sy / length};
  }

  function movementVector() {
    const input = screenMovementVector();
    if (!input.x && !input.y) return input;

    if (save.presentation_dimension === '3D' && save.camera_mode !== 'ISOMETRIC') {
      const forward = {x: Math.cos(save.camera_heading), y: Math.sin(save.camera_heading)};
      const right = {x: -forward.y, y: forward.x};
      return {
        x: forward.x * (-input.y) + right.x * input.x,
        y: forward.y * (-input.y) + right.y * input.x
      };
    }

    return {
      x: (input.x + input.y) * .70710678,
      y: (input.y - input.x) * .70710678
    };
  }

  function update(dt, now) {
    if (!entered) return;
    const vector = movementVector();
    if (vector.x || vector.y) {
      const speed = keys.has('shift') ? 7.2 : 4.2;
      player.x += vector.x * speed * dt;
      player.y += vector.y * speed * dt;
      checkChunkTransition();
      if (now - lastPersistAt > 900) {
        persistCauses();
        lastPersistAt = now;
      }
    }
  }

  function frame(now) {
    const dt = clamp((now - lastFrame) / 1000, 0, .05);
    lastFrame = now;
    update(dt, now);
    render(now);
    if ((Math.floor(now / 250) % 2) === 0) drawMinimap();
    requestAnimationFrame(frame);
  }

  function showToast(message) {
    const node = $('toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove('show'), 2400);
  }

  function toggleDrawer(id) {
    const target = $(id);
    const opening = target.hidden;
    document.querySelectorAll('.drawer').forEach(drawer => { drawer.hidden = true; });
    target.hidden = !opening;
    if (opening && id === 'chronicle-panel') renderChronicle();
    if (opening && id === 'mirror-panel') {
      renderMirrorOptions();
      renderViewOptions();
      $('mirror-fact-hash').textContent = canonicalFactHashNow();
    }
  }

  async function loadContract() {
    try {
      const response = await fetch('./contracts/GENESIS_WORLD_SHELL_R0.json', {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.schema !== 'janus.genesis.world_shell.v1' || data.world_model?.world_id !== CONFIG.world_id || data.world_model?.world_seed !== CONFIG.world_seed) {
        throw new Error('world shell contract mismatch');
      }
      if (data.authority_boundary?.renderer_is_authority !== false || data.authority_boundary?.mirror_is_authority !== false) {
        throw new Error('authority boundary mismatch');
      }
      if (!data.personal_mirror?.dimensions?.includes('2D') || !data.personal_mirror?.dimensions?.includes('3D')) {
        throw new Error('dimension contract missing');
      }
      for (const camera of ['FIRST_PERSON', 'THIRD_PERSON', 'ISOMETRIC']) {
        if (!data.personal_mirror?.camera_modes?.includes(camera)) throw new Error(`camera ${camera} contract missing`);
      }
      contract = data;
      $('generator-state').textContent = `WORLD SHELL READY // CONTRACT ${data.version}`;
    } catch (error) {
      $('generator-state').textContent = `CONTRACT LOAD BLOCKED // ${error.message}`;
      $('generator-state').style.color = 'var(--red)';
      $('leave-mark').disabled = true;
      console.error('Genesis World Shell contract failed closed:', error);
    }
  }

  function enterWorld() {
    entered = true;
    $('welcome').classList.add('dismissed');
    setTimeout(() => { $('welcome').hidden = true; }, 700);
    checkChunkTransition();
    showToast('WORLD SHELL ACTIVE // WALK TO MATERIALIZE HISTORY');
  }

  function bindLookControls() {
    canvas.addEventListener('pointerdown', event => {
      if (save.camera_mode === 'ISOMETRIC') return;
      dragLook = {active: true, pointerId: event.pointerId, lastX: event.clientX};
      canvas.setPointerCapture?.(event.pointerId);
    });

    canvas.addEventListener('pointermove', event => {
      if (!dragLook.active || dragLook.pointerId !== event.pointerId || save.camera_mode === 'ISOMETRIC') return;
      const delta = event.clientX - dragLook.lastX;
      dragLook.lastX = event.clientX;
      rotateCamera(delta * .006);
    });

    const stop = event => {
      if (dragLook.pointerId !== null && event.pointerId !== undefined && dragLook.pointerId !== event.pointerId) return;
      dragLook = {active: false, pointerId: null, lastX: 0};
    };
    canvas.addEventListener('pointerup', stop);
    canvas.addEventListener('pointercancel', stop);
  }

  function bindInputs() {
    addEventListener('keydown', event => {
      const key = event.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright', 'shift'].includes(key)) {
        keys.add(key);
        if (key.startsWith('arrow')) event.preventDefault();
      }
      if (key === 'e' && !event.repeat) placeMark();
      if (key === 'r' && !event.repeat) returnToHearth();
      if (key === 'm' && !event.repeat) toggleDrawer('mirror-panel');
      if (key === 'c' && !event.repeat) toggleDrawer('chronicle-panel');
      if (key === 'v' && !event.repeat) toggleDrawer('mirror-panel');
      if (key === 'q' && !event.repeat && save.camera_mode !== 'ISOMETRIC') rotateCamera(-.16);
      if (key === 'f' && !event.repeat && save.camera_mode !== 'ISOMETRIC') rotateCamera(.16);
    });

    addEventListener('keyup', event => keys.delete(event.key.toLowerCase()));
    addEventListener('blur', () => {
      keys.clear();
      touchDirections.clear();
      dragLook = {active: false, pointerId: null, lastX: 0};
    });

    document.querySelectorAll('[data-move]').forEach(button => {
      const direction = button.dataset.move;
      const start = event => {
        event.preventDefault();
        touchDirections.add(direction);
        if (!entered) enterWorld();
      };
      const stop = event => {
        event.preventDefault();
        touchDirections.delete(direction);
      };
      button.addEventListener('pointerdown', start);
      button.addEventListener('pointerup', stop);
      button.addEventListener('pointercancel', stop);
      button.addEventListener('pointerleave', stop);
    });

    $('enter-world').addEventListener('click', enterWorld);
    $('leave-mark').addEventListener('click', placeMark);
    $('reset-view').addEventListener('click', returnToHearth);
    $('audio-toggle').addEventListener('click', toggleAudio);
    $('mirror-toggle').addEventListener('click', () => toggleDrawer('mirror-panel'));
    $('view-toggle').addEventListener('click', () => toggleDrawer('mirror-panel'));
    $('chronicle-toggle').addEventListener('click', () => toggleDrawer('chronicle-panel'));
    document.querySelectorAll('[data-close]').forEach(button => {
      button.addEventListener('click', () => { $(button.dataset.close).hidden = true; });
    });
    addEventListener('genesis:audio-forge-ready', updateAudioPresentation);
    addEventListener('genesis:audio-forge-state', updateAudioPresentation);
    addEventListener('resize', resize);
    addEventListener('beforeunload', persistCauses);
    bindLookControls();
  }

  function boot() {
    resize();
    bindInputs();
    renderMirrorOptions();
    renderViewOptions();
    renderChronicle();
    const {cx, cy} = currentChunk();
    prewarmAround(cx, cy);
    updateWorldHud();
    drawMinimap();
    updateAudioPresentation();
    loadContract();
    requestAnimationFrame(frame);
  }

  boot();
})();