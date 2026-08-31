(() => {
  'use strict';

  const VERSION = '1.0.0';
  const GENERATOR = 'GENESIS_AUDIO_FORGE_V1';
  const STEPS = 16;
  const ALLOWED_WAVES = new Set(['sine', 'triangle', 'square', 'sawtooth']);
  const PROGRESSION = [0, 4, 5, 3];
  const PULSE_STEPS = new Set([0, 4, 8, 12]);
  const BASS_STEPS = [0, 3, 6, 8, 11, 14];
  const STAR_STEPS = new Set([5, 13]);

  const DEFAULT_RECIPE = Object.freeze({
    schema: 'janus.genesis.audio_recipe.v1',
    generator: GENERATOR,
    generator_version: VERSION,
    recipe_id: 'genesis://audio/biome/liminal-hall/v1',
    tempo_bpm: 66,
    root_midi: 50,
    scale: [0, 2, 4, 6, 7, 9, 11],
    motif: [0, 4, 2, 5, 1, 6, 4, 2],
    layers: {
      pulse: {enabled: true, density: .42, gain: .030, wave: 'sine'},
      bass: {enabled: true, density: .58, gain: .045, wave: 'triangle'},
      arp: {enabled: true, density: .70, gain: .024, wave: 'triangle'},
      pad: {enabled: true, density: 1, gain: .020, wave: 'sine'},
      bells: {enabled: true, density: .38, gain: .018, wave: 'sine'},
      drone: {enabled: true, density: 1, gain: .012, wave: 'sine'},
      noise: {enabled: true, density: .22, gain: .009, wave: 'sine'}
    }
  });

  const state = {
    enabled: false, running: false, ctx: null, master: null, filter: null,
    delay: null, feedback: null, compressor: null, noiseBuffer: null,
    timer: 0, nextStepTime: 0, step: 0, bar: 0, seed: 0,
    recipe: clone(DEFAULT_RECIPE),
    world: {entropy: 0, depth: 0, portal_energy: 0, danger: 0, weather_intensity: 0}
  };

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function clamp(value, min, max) {
    const n = Number(value);
    if (!Number.isFinite(n)) throw new TypeError('GENESIS Audio Forge expects finite numeric parameters');
    return Math.max(min, Math.min(max, n));
  }
  function midiToHz(midi) { return 440 * Math.pow(2, (Number(midi) - 69) / 12); }
  function hash32(x) {
    x |= 0; x = (x + 0x7ed55d16 + (x << 12)) | 0;
    x = (x ^ 0xc761c23c ^ (x >>> 19)) | 0;
    x = (x + 0x165667b1 + (x << 5)) | 0;
    x = (x + 0xd3a2646c) | 0; x = (x ^ (x << 9)) | 0;
    x = (x + 0xfd7046c5 + (x << 3)) | 0;
    x = (x ^ 0xb55a4f09 ^ (x >>> 16)) | 0;
    return x >>> 0;
  }
  function unitRand(step, salt = 0) {
    const mixed = (state.seed ^ Math.imul(state.bar + 1, 0x9e3779b1) ^ Math.imul(step + 1, 0x85ebca6b) ^ salt) >>> 0;
    return hash32(mixed) / 0xffffffff;
  }
  function secureSeed() {
    const a = new Uint32Array(1);
    if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(a);
    else a[0] = (Date.now() * 2654435761) >>> 0;
    return a[0] >>> 0;
  }

  function normalizeLayer(raw, fallback) {
    const source = raw && typeof raw === 'object' ? raw : fallback;
    const wave = String(source.wave || fallback.wave);
    if (!ALLOWED_WAVES.has(wave)) throw new TypeError(`Unsupported oscillator wave: ${wave}`);
    return {
      enabled: source.enabled !== false,
      density: clamp(source.density ?? fallback.density, 0, 1),
      gain: clamp(source.gain ?? fallback.gain, .0001, .2),
      wave
    };
  }

  function validateRecipe(input) {
    if (!input || typeof input !== 'object') throw new TypeError('Audio recipe must be an object');
    if (input.schema !== 'janus.genesis.audio_recipe.v1') throw new TypeError('Unsupported audio recipe schema');
    if (input.generator !== GENERATOR) throw new TypeError('Unsupported audio generator');
    if (typeof input.recipe_id !== 'string' || !input.recipe_id.startsWith('genesis://audio/')) throw new TypeError('Invalid recipe_id');
    if (!Array.isArray(input.scale) || !input.scale.length || input.scale.length > 16) throw new TypeError('Invalid scale');
    if (!Array.isArray(input.motif) || !input.motif.length || input.motif.length > 32) throw new TypeError('Invalid motif');
    const layers = {};
    for (const name of Object.keys(DEFAULT_RECIPE.layers)) layers[name] = normalizeLayer(input.layers?.[name], DEFAULT_RECIPE.layers[name]);
    return {
      schema: input.schema,
      generator: GENERATOR,
      generator_version: String(input.generator_version || VERSION),
      recipe_id: input.recipe_id,
      tempo_bpm: clamp(input.tempo_bpm ?? 66, 36, 160),
      root_midi: Math.round(clamp(input.root_midi ?? 50, 24, 84)),
      scale: input.scale.map(v => Math.round(clamp(v, -24, 24))),
      motif: input.motif.map(v => Math.round(clamp(v, -32, 32))),
      layers
    };
  }

  function setWorldState(input = {}) {
    const allowed = new Set(['entropy', 'depth', 'portal_energy', 'danger', 'weather_intensity']);
    for (const key of Object.keys(input)) if (!allowed.has(key)) throw new TypeError(`Unsupported/hidden telemetry field: ${key}`);
    for (const key of allowed) state.world[key] = clamp(input[key] ?? 0, 0, 1);
    return getState();
  }

  function impulse(ctx, seconds = 2.2, decay = 2.6) {
    const length = Math.floor(ctx.sampleRate * seconds);
    const buffer = ctx.createBuffer(2, length, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const data = buffer.getChannelData(ch);
      for (let i = 0; i < length; i++) {
        const env = Math.pow(1 - i / length, decay);
        const pseudo = (((i * 1103515245 + ch * 12345) >>> 8) & 0xffff) / 32767.5 - 1;
        data[i] = pseudo * env * .34;
      }
    }
    return buffer;
  }

  function buildNoiseBuffer(ctx) {
    const length = Math.floor(ctx.sampleRate * .7);
    const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let seed = state.seed || 0x9e3779b9;
    for (let i = 0; i < length; i++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      data[i] = seed / 0xffffffff * 2 - 1;
    }
    return buffer;
  }

  function ensureGraph() {
    if (state.ctx) return state.ctx;
    const Ctx = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!Ctx) return null;
    const ctx = new Ctx();
    const master = ctx.createGain();
    const filter = ctx.createBiquadFilter();
    const delay = ctx.createDelay(1.2);
    const feedback = ctx.createGain();
    const reverb = ctx.createConvolver();
    const compressor = ctx.createDynamicsCompressor();
    master.gain.value = .0001;
    filter.type = 'lowpass'; filter.frequency.value = 3200; filter.Q.value = .55;
    delay.delayTime.value = .285; feedback.gain.value = .20;
    reverb.buffer = impulse(ctx);
    compressor.threshold.value = -18; compressor.knee.value = 18; compressor.ratio.value = 3;
    compressor.attack.value = .008; compressor.release.value = .36;
    filter.connect(master);
    filter.connect(delay); delay.connect(feedback); feedback.connect(delay); delay.connect(master);
    filter.connect(reverb); reverb.connect(master);
    master.connect(compressor).connect(ctx.destination);
    Object.assign(state, {ctx, master, filter, delay, feedback, compressor, noiseBuffer: buildNoiseBuffer(ctx)});
    return ctx;
  }

  function pan(node, value = 0) {
    if (!state.ctx?.createStereoPanner) return node;
    const p = state.ctx.createStereoPanner(); p.pan.value = clamp(value, -1, 1); node.connect(p); return p;
  }

  function voice({freq, when, duration = .2, gain = .02, wave = 'sine', cutoff = 3200, panValue = 0, detune = 0, sweepTo = 0}) {
    if (!state.enabled || !state.ctx || !state.filter) return;
    const osc = state.ctx.createOscillator();
    const amp = state.ctx.createGain();
    const tone = state.ctx.createBiquadFilter();
    osc.type = ALLOWED_WAVES.has(wave) ? wave : 'sine';
    osc.frequency.setValueAtTime(freq, when);
    if (sweepTo > 0) osc.frequency.exponentialRampToValueAtTime(sweepTo, when + duration * .82);
    osc.detune.setValueAtTime(detune, when);
    tone.type = 'lowpass'; tone.frequency.setValueAtTime(cutoff, when); tone.Q.value = .65;
    amp.gain.setValueAtTime(.0001, when);
    amp.gain.exponentialRampToValueAtTime(Math.max(.0002, gain), when + .018);
    amp.gain.exponentialRampToValueAtTime(.0001, when + duration);
    osc.connect(tone).connect(amp);
    pan(amp, panValue).connect(state.filter);
    osc.start(when); osc.stop(when + duration + .04);
  }

  function noiseHit(when, gain, cutoff) {
    if (!state.enabled || !state.ctx || !state.noiseBuffer || !state.master) return;
    const src = state.ctx.createBufferSource();
    const hp = state.ctx.createBiquadFilter();
    const amp = state.ctx.createGain();
    src.buffer = state.noiseBuffer; hp.type = 'highpass'; hp.frequency.setValueAtTime(cutoff, when);
    amp.gain.setValueAtTime(Math.max(.0002, gain), when); amp.gain.exponentialRampToValueAtTime(.0001, when + .05);
    src.connect(hp).connect(amp).connect(state.master);
    src.start(when, Math.min(.3, unitRand(state.step, 991) * .3)); src.stop(when + .07);
  }

  function modeMidi(degree, octave = 0) {
    const scale = state.recipe.scale;
    const len = scale.length;
    const octShift = Math.floor(degree / len);
    const index = ((degree % len) + len) % len;
    return state.recipe.root_midi + scale[index] + 12 * (octave + octShift);
  }

  function effectiveBpm() {
    const w = state.world;
    return clamp(state.recipe.tempo_bpm + w.portal_energy * 18 + w.danger * 10 - w.depth * 5, 36, 180);
  }
  function stepSeconds() { return (60 / effectiveBpm()) / 4; }

  function scheduleStep(when) {
    const step = state.step;
    const root = PROGRESSION[state.bar % PROGRESSION.length];
    const w = state.world;
    const layers = state.recipe.layers;
    const register = w.depth > .70 ? -1 : (w.portal_energy > .82 ? 1 : 0);
    const filterHz = clamp(2200 + w.entropy * 2400 + w.portal_energy * 1300 - w.depth * 600, 500, 7600);
    state.filter?.frequency.setTargetAtTime(filterHz, when, .05);

    if (step === 0 && layers.drone.enabled) voice({freq: midiToHz(modeMidi(root, -2 + register)), when, duration: stepSeconds() * 15, gain: layers.drone.gain, wave: layers.drone.wave, cutoff: 900});
    if (step === 0 && layers.pad.enabled) [0, 2, 4].forEach((d, i) => voice({freq: midiToHz(modeMidi(root + d, -1 + register)), when, duration: stepSeconds() * 15.2, gain: layers.pad.gain, wave: layers.pad.wave, cutoff: 1900, panValue: (i - 1) * .35, detune: i % 2 ? 6 : -6}));

    const pulseThreshold = Math.min(1, layers.pulse.density + w.danger * .18 + w.portal_energy * .12);
    if (layers.pulse.enabled && (PULSE_STEPS.has(step) || unitRand(step, 101) < pulseThreshold * .22)) voice({freq: 86, sweepTo: 43, when, duration: .18, gain: layers.pulse.gain * (1 + w.danger * .25), wave: 'sine', cutoff: 700});

    if (layers.bass.enabled && BASS_STEPS.includes(step) && unitRand(step, 202) < Math.min(1, layers.bass.density + w.danger * .15)) {
      const degree = root + [0, 0, 2, 0, 4, 2][BASS_STEPS.indexOf(step)];
      voice({freq: midiToHz(modeMidi(degree, -2 + register)), when, duration: .24, gain: layers.bass.gain, wave: layers.bass.wave, cutoff: 760, panValue: step < 8 ? -.18 : .18});
    }

    if (layers.arp.enabled && step % 2 === 1 && unitRand(step, 303) < Math.min(1, layers.arp.density + w.portal_energy * .22 + w.entropy * .10)) {
      const degree = root + state.recipe.motif[(Math.floor(step / 2) + state.bar) % state.recipe.motif.length];
      voice({freq: midiToHz(modeMidi(degree, register)), when, duration: .18, gain: layers.arp.gain, wave: layers.arp.wave, cutoff: filterHz, panValue: unitRand(step, 304) * 1.4 - .7});
    }

    if (layers.bells.enabled && STAR_STEPS.has(step) && unitRand(step, 404) < Math.min(1, layers.bells.density + w.portal_energy * .25)) {
      const degree = root + state.recipe.motif[(step + state.bar) % state.recipe.motif.length] + 4;
      const freq = midiToHz(modeMidi(degree, 1 + register));
      voice({freq, when, duration: .72, gain: layers.bells.gain, wave: 'sine', cutoff: 6900, panValue: step < 8 ? -.55 : .55});
      voice({freq: freq * 2.01, when, duration: .42, gain: layers.bells.gain * .28, wave: 'sine', cutoff: 7600, panValue: step < 8 ? .35 : -.35});
    }

    if (layers.noise.enabled && unitRand(step, 505) < Math.min(1, layers.noise.density * .25 + w.weather_intensity * .42 + w.entropy * .08)) noiseHit(when, layers.noise.gain * (.5 + w.weather_intensity * .8), filterHz + w.weather_intensity * 900);
  }

  function scheduler() {
    if (!state.running || !state.enabled || !state.ctx) return;
    while (state.nextStepTime < state.ctx.currentTime + .14) {
      scheduleStep(state.nextStepTime);
      state.nextStepTime += stepSeconds();
      state.step += 1;
      if (state.step >= STEPS) { state.step = 0; state.bar += 1; }
    }
  }

  async function enable({seed = null, recipe = null, world_state = null} = {}) {
    if (recipe) state.recipe = validateRecipe(recipe);
    if (world_state) setWorldState(world_state);
    state.seed = seed == null ? secureSeed() : (Number(seed) >>> 0);
    const ctx = ensureGraph();
    if (!ctx) return false;
    await ctx.resume();
    state.enabled = true;
    state.master.gain.cancelScheduledValues(ctx.currentTime);
    state.master.gain.setTargetAtTime(.08, ctx.currentTime, .08);
    if (!state.running) {
      state.running = true; state.nextStepTime = ctx.currentTime + .04; state.step = 0; state.bar = 0;
      state.timer = globalThis.setInterval(scheduler, 25);
    }
    globalThis.dispatchEvent?.(new CustomEvent('genesis:audio-forge-state', {detail: getState()}));
    return true;
  }

  function disable() {
    state.enabled = false;
    if (state.master && state.ctx) state.master.gain.setTargetAtTime(.0001, state.ctx.currentTime, .06);
    return getState();
  }

  function stop() {
    state.running = false;
    if (state.timer) globalThis.clearInterval(state.timer);
    state.timer = 0;
    disable();
    return getState();
  }

  function configure(recipe) { state.recipe = validateRecipe(recipe); return getState(); }

  function cue(kind, intensity = .5) {
    if (!state.enabled || !state.ctx) return false;
    const level = clamp(intensity, 0, 1);
    const now = state.ctx.currentTime + .012;
    const root = state.recipe.root_midi;
    const recipes = {
      portal_open: [0, 7, 12, 19],
      discovery: [0, 4, 7, 14],
      danger: [0, 1, 6, 7],
      resolve: [12, 9, 5, 0]
    };
    const intervals = recipes[kind] || recipes.discovery;
    intervals.forEach((interval, i) => voice({freq: midiToHz(root + 12 + interval), when: now + i * .075, duration: .45 + level * .25, gain: .008 + level * .012, wave: i % 2 ? 'triangle' : 'sine', cutoff: 3500 + level * 3000, panValue: (i - 1.5) * .28}));
    return true;
  }

  function getState() {
    return {
      version: VERSION, generator: GENERATOR, enabled: state.enabled, running: state.running,
      seed: state.seed, recipe_id: state.recipe.recipe_id, bar: state.bar, step: state.step,
      world_state: {...state.world}, presentation_only: true, world_mutation: false,
      hidden_human_telemetry: false, network_access: false, arbitrary_code_execution: false,
      user_gesture_required: true
    };
  }

  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => {
    if (!state.master || !state.ctx) return;
    state.master.gain.setTargetAtTime(document.hidden || !state.enabled ? .0001 : .08, state.ctx.currentTime, .08);
  });

  globalThis.GENESIS_AUDIO_FORGE = Object.freeze({version: VERSION, configure, setWorldState, enable, disable, stop, cue, getState});
  globalThis.dispatchEvent?.(new CustomEvent('genesis:audio-forge-ready', {detail: {version: VERSION, generator: GENERATOR, presentation_only: true}}));
})();
