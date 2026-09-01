'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const MIRROR_SOURCE = fs.readFileSync(path.join(ROOT, 'site', 'genesis-player-mirror-r0-7.js'), 'utf8');
const STORAGE_KEY = 'janus.genesis.player_mirror_r0_7.v1';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem(key) { return map.has(key) ? map.get(key) : null; },
    setItem(key, value) { map.set(String(key), String(value)); },
    removeItem(key) { map.delete(String(key)); },
    clear() { map.clear(); },
    dump() { return Object.fromEntries(map.entries()); }
  };
}

function makeCanvas(id, registry, metrics) {
  const ctx = {
    imageSmoothingEnabled: true,
    drawImageCalls: 0,
    putImageDataCalls: 0,
    lastImageData: null,
    drawImage() { this.drawImageCalls += 1; },
    getImageData() {
      return {
        data: new Uint8ClampedArray([
          255, 255, 255, 255,
          0, 0, 0, 255,
          112, 227, 244, 255,
          160, 80, 48, 255
        ])
      };
    },
    putImageData(image) {
      this.putImageDataCalls += 1;
      this.lastImageData = new Uint8ClampedArray(image.data);
    }
  };

  const el = {
    id,
    tagName: 'CANVAS',
    style: {},
    dataset: {},
    hidden: false,
    width: 0,
    height: 0,
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getBoundingClientRect() { return { width: 160, height: 96, left: 0, top: 0, right: 160, bottom: 96 }; },
    getContext(kind) {
      assert.strictEqual(kind, '2d');
      return ctx;
    },
    insertAdjacentElement(_position, node) {
      if (node && node.id) registry.set(node.id, node);
      return node;
    },
    addEventListener() {},
  };
  metrics.canvasContexts.set(id, ctx);
  return el;
}

function makeElement(tagName, registry) {
  const el = {
    id: '',
    tagName: String(tagName).toUpperCase(),
    style: {},
    dataset: {},
    hidden: false,
    attributes: {},
    textContent: '',
    title: '',
    type: '',
    className: '',
    listeners: new Map(),
    setAttribute(name, value) { this.attributes[name] = String(value); },
    addEventListener(type, fn) { this.listeners.set(type, fn); },
    insertAdjacentElement(_position, node) {
      if (node && node.id) registry.set(node.id, node);
      return node;
    }
  };
  return el;
}

function bootMirror({ corruptOn = null, storedProfile = null, unborn = false } = {}) {
  const registry = new Map();
  const metrics = {
    scheduledFrames: [],
    dispatchedEvents: [],
    setMirrorCalls: [],
    canvasContexts: new Map()
  };
  const storage = makeStorage(storedProfile ? {
    [STORAGE_KEY]: JSON.stringify({
      schema: 'janus.genesis.player_mirror_state.v1',
      version: '0.7.0',
      scope: 'PLAYER_LOCAL_PRESENTATION',
      profile: storedProfile
    })
  } : {});

  const sourceCanvas = makeCanvas('genesis-world', registry, metrics);
  registry.set('genesis-world', sourceCanvas);
  const mirrorChip = makeElement('span', registry);
  mirrorChip.id = 'mirror-chip';
  registry.set('mirror-chip', mirrorChip);

  const documentElement = { dataset: {} };
  const body = {
    appendChild(node) {
      if (node && node.id) registry.set(node.id, node);
      return node;
    }
  };
  const document = {
    documentElement,
    body,
    getElementById(id) { return registry.get(id) || null; },
    createElement(tag) {
      if (String(tag).toLowerCase() === 'canvas') return makeCanvas('', registry, metrics);
      return makeElement(tag, registry);
    }
  };

  let canonical = {
    world_id: 'GENESIS_ONE_WORLD_R0',
    world_seed: 'genesis-one-world-r0',
    player_position: { x: 0.5, y: 0.5 },
    world_settings: { time: 'DAY', fog: 0.08, weather: 'CLEAR' },
    discovered_chunk_coordinates: [[0, 0]],
    explicit_world_mutations: [],
    chronicle_tip_hash: 'tip-001'
  };
  let factHash = 'fact-001';
  let presentation = { mirror_profile: 'ORIGIN', camera_mode: 'THIRD_PERSON' };

  const runtime = {
    getFactHash() { return factHash; },
    getCanonicalState() { return clone(canonical); },
    getPresentationState() { return clone(presentation); },
    setMirror(name) {
      metrics.setMirrorCalls.push(name);
      presentation.mirror_profile = name;
      if (name === corruptOn) {
        canonical = { ...canonical, player_position: { x: 999, y: 999 } };
        factHash = 'fact-TAMPERED';
      }
      return true;
    }
  };

  class CustomEvent {
    constructor(type, init = {}) { this.type = type; this.detail = init.detail; }
  }

  const sandbox = {
    console,
    document,
    localStorage: storage,
    CustomEvent,
    GENESIS_WORLD_RUNTIME_V5: runtime,
    GENESIS_BIRTH_R0_6: { isUnborn: () => unborn },
    dispatchEvent(event) { metrics.dispatchedEvents.push(event); return true; },
    requestAnimationFrame(callback) {
      metrics.scheduledFrames.push(callback);
      return metrics.scheduledFrames.length;
    },
    Uint8Array,
    Uint8ClampedArray,
    Object,
    JSON,
    String,
    Math,
    Infinity,
    parseInt,
    setTimeout,
    clearTimeout
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(MIRROR_SOURCE, sandbox, { filename: 'genesis-player-mirror-r0-7.js' });

  return {
    api: sandbox.GENESIS_PLAYER_MIRROR_R0_7,
    runtime,
    storage,
    sourceCanvas,
    registry,
    metrics,
    documentElement,
    canonical: () => clone(canonical),
    factHash: () => factHash,
    presentation: () => clone(presentation),
    runNextFrame(now = 1000) {
      const callback = metrics.scheduledFrames.shift();
      assert(callback, 'expected a scheduled animation frame');
      callback(now);
    }
  };
}

function assertPaletteMembership(pixelData, paletteHex) {
  const allowed = new Set(paletteHex.map(hex => hex.toLowerCase()));
  for (let i = 0; i < pixelData.length; i += 4) {
    const hex = '#' + [pixelData[i], pixelData[i + 1], pixelData[i + 2]]
      .map(value => Number(value).toString(16).padStart(2, '0')).join('');
    assert(allowed.has(hex), `quantized pixel ${hex} is outside JANUS_16 palette`);
  }
}

(function happyPathKeepsCanonicalRealityInvariant() {
  const h = bootMirror();
  assert(h.api, 'mirror API must be exported');
  assert.strictEqual(h.api.version, '0.7.0');
  assert.deepStrictEqual(Array.from(h.api.profiles), ['ORIGIN', 'JANUS_16', 'NOCTURNE', 'AETHER', 'EMBER']);

  const beforeState = h.canonical();
  const beforeHash = h.factHash();
  const janus16 = h.api.setProfile('JANUS_16');
  assert.strictEqual(janus16.ok, true);
  assert.strictEqual(h.api.getProfile(), 'JANUS_16');
  assert.strictEqual(h.factHash(), beforeHash);
  assert.deepStrictEqual(h.canonical(), beforeState);
  assert.strictEqual(janus16.proof.canonical_equal, true);
  assert.strictEqual(janus16.proof.fact_hash_before, janus16.proof.fact_hash_after);
  assert.strictEqual(janus16.proof.chronicle_tip_before, janus16.proof.chronicle_tip_after);
  assert.strictEqual(JSON.parse(h.storage.getItem(STORAGE_KEY)).profile, 'JANUS_16');
  assert.strictEqual(h.sourceCanvas.style.visibility, 'hidden');

  h.runNextFrame(1000);
  const output = h.registry.get('genesis-player-mirror-output-r0-7');
  assert(output, 'JANUS_16 must create a player-local presentation canvas');
  const ctx = h.metrics.canvasContexts.get('');
  assert(ctx, 'presentation canvas context must exist');
  assert(ctx.drawImageCalls > 0, 'canonical frame must be sampled');
  assert(ctx.putImageDataCalls > 0, 'quantized frame must be written');
  assertPaletteMembership(ctx.lastImageData, Array.from(h.api.palette));

  const nocturne = h.api.setProfile('NOCTURNE');
  assert.strictEqual(nocturne.ok, true);
  assert.strictEqual(h.presentation().mirror_profile, 'NOCTURNE');
  assert.strictEqual(h.sourceCanvas.style.visibility, '');
  assert.strictEqual(output.hidden, true);
  assert.strictEqual(h.factHash(), beforeHash);
  assert.deepStrictEqual(h.canonical(), beforeState);
  assert(h.metrics.dispatchedEvents.some(event => event.type === 'genesis:mirror-changed'));
})();

(function invalidProfileFailsBeforeAnyWorldTouch() {
  const h = bootMirror();
  const before = h.canonical();
  const result = h.api.setProfile('NOT_A_REAL_MIRROR');
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.reason, 'MIRROR_PROFILE_NOT_ALLOWLISTED');
  assert.deepStrictEqual(h.canonical(), before);
  assert.strictEqual(h.metrics.setMirrorCalls.length, 0);
  assert.strictEqual(h.storage.getItem(STORAGE_KEY), null);
})();

(function canonicalTamperIsDetectedAndProfileIsNotCommitted() {
  const h = bootMirror({ corruptOn: 'EMBER' });
  const result = h.api.setProfile('EMBER');
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.reason, 'CANONICAL_INVARIANCE_BREACH');
  assert.strictEqual(h.api.getProfile(), 'ORIGIN');
  assert.strictEqual(h.presentation().mirror_profile, 'ORIGIN');
  assert.strictEqual(h.storage.getItem(STORAGE_KEY), null, 'failed profile must never be persisted');
  assert(h.metrics.setMirrorCalls.includes('EMBER'));
  assert(h.metrics.setMirrorCalls.includes('ORIGIN'), 'presentation must roll back after detected breach');
})();

(function unbornAuthoritySuppressesConstrainedFrameProjection() {
  const h = bootMirror({ unborn: true });
  const result = h.api.setProfile('JANUS_16');
  assert.strictEqual(result.ok, true);
  h.runNextFrame(1000);
  const ctx = h.metrics.canvasContexts.get('');
  assert(ctx, 'presentation surface may be allocated while unborn');
  assert.strictEqual(ctx.drawImageCalls, 0, 'unborn Birth veil must remain authoritative over Mirror rendering');
  assert.strictEqual(ctx.putImageDataCalls, 0);
})();

console.log('GENESIS_PLAYER_MIRROR_R0_7_EXECUTABLE_HARNESS_PASS');
