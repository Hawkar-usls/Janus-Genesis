(() => {
  'use strict';

  const WORLD_FIELDS = [
    ['entropy', 0.22],
    ['depth', 0.38],
    ['portal_energy', 0.46],
    ['danger', 0.08],
    ['weather_intensity', 0.18]
  ];

  const $ = id => document.getElementById(id);
  const fieldCanvas = $('world-field');
  const ctx = fieldCanvas.getContext('2d', {alpha: true});
  const seedInput = $('seed');
  const worldControls = $('world-controls');
  let laws = null;
  let roadmap = null;
  let visualParticles = [];
  let visualSignature = '';
  let frame = 0;

  function clamp01(value) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
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

  function rngFactory(seed) {
    let state = seed || 0x9e3779b9;
    return () => {
      state = mix32(state + 0x6d2b79f5);
      return state / 0xffffffff;
    };
  }

  function readWorld() {
    return Object.fromEntries(WORLD_FIELDS.map(([key]) => [key, clamp01($(key).value)]));
  }

  function worldHash(world) {
    const canonical = WORLD_FIELDS.map(([key]) => `${key}=${world[key].toFixed(3)}`).join('|');
    return hashString(canonical).toString(16).padStart(8, '0');
  }

  function seedU32() {
    return hashString(seedInput.value || 'genesis-pages-r0');
  }

  function renderWorldControls() {
    for (const [key, initial] of WORLD_FIELDS) {
      const row = document.createElement('div');
      row.className = 'slider-row';

      const label = document.createElement('label');
      label.htmlFor = key;
      label.textContent = key.replaceAll('_', ' ');

      const input = document.createElement('input');
      input.id = key;
      input.type = 'range';
      input.min = '0';
      input.max = '1';
      input.step = '0.01';
      input.value = String(initial);

      const output = document.createElement('output');
      output.id = `${key}-value`;
      output.htmlFor = key;
      output.textContent = Number(initial).toFixed(2);

      input.addEventListener('input', () => {
        output.textContent = Number(input.value).toFixed(2);
        refreshCauses();
      });

      row.append(label, input, output);
      worldControls.append(row);
    }
  }

  function renderRoadmap(data) {
    const grid = $('kernel-grid');
    grid.replaceChildren();
    for (const stage of data.stages) {
      const card = document.createElement('article');
      card.className = 'kernel-card';
      card.dataset.state = stage.status;

      const order = document.createElement('div');
      order.className = 'kernel-order';
      order.textContent = `R${stage.order.toString().padStart(2, '0')}`;

      const name = document.createElement('div');
      name.className = 'kernel-name';
      name.textContent = stage.kernel;

      const status = document.createElement('div');
      status.className = 'kernel-status';
      status.textContent = stage.status;

      const purpose = document.createElement('p');
      purpose.className = 'kernel-purpose';
      purpose.textContent = stage.purpose;

      card.append(order, name, status, purpose);
      grid.append(card);
    }
    $('receipt-next').textContent = data.current_front || 'UNKNOWN';
  }

  function renderLaws(data) {
    const list = $('laws-list');
    list.replaceChildren();
    for (const law of data.laws) {
      const item = document.createElement('li');
      item.className = 'law-item';

      const id = document.createElement('span');
      id.className = 'law-id';
      id.textContent = law.id;

      const body = document.createElement('div');
      const name = document.createElement('div');
      name.className = 'law-name';
      name.textContent = law.name;
      const statement = document.createElement('div');
      statement.className = 'law-statement';
      statement.textContent = law.statement;
      body.append(name, statement);
      item.append(id, body);
      list.append(item);
    }
    $('laws-count').textContent = `${data.laws.length} LAWS`;
  }

  async function fetchContract(path) {
    const response = await fetch(path, {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`contract ${path} returned HTTP ${response.status}`);
    return response.json();
  }

  async function loadContracts() {
    try {
      [laws, roadmap] = await Promise.all([
        fetchContract('./contracts/GENESIS_LAWS_V1.json'),
        fetchContract('./contracts/GENESIS_KERNEL_ROADMAP_V1.json')
      ]);
      if (laws.status !== 'FROZEN_R0' || roadmap.status !== 'FROZEN_R0') throw new Error('contracts are not frozen R0');
      renderLaws(laws);
      renderRoadmap(roadmap);
      $('contract-version').textContent = `laws ${laws.version} / roadmap ${roadmap.version}`;
      $('page-status').textContent = 'CONTROL PLANE READY';
    } catch (error) {
      $('page-status').textContent = 'CONTRACT LOAD BLOCKED';
      $('contract-version').textContent = error.message;
      console.error('Genesis Pages contract load failed:', error);
    }
  }

  function audioForge() {
    return globalThis.GENESIS_AUDIO_FORGE || null;
  }

  function renderAudioState() {
    const forge = audioForge();
    const state = forge ? forge.getState() : {
      enabled: false,
      presentation_only: true,
      world_mutation: false,
      hidden_human_telemetry: false,
      network_access: false,
      arbitrary_code_execution: false,
      user_gesture_required: true,
      runtime: 'waiting'
    };
    $('audio-state').textContent = JSON.stringify(state, null, 2);
    $('receipt-audio').textContent = state.enabled ? 'ON' : 'OFF';
    $('receipt-audio').className = state.enabled ? 'yes' : '';
    return state;
  }

  function rebuildParticles(seed, world) {
    const signature = `${seed}|${worldHash(world)}|${fieldCanvas.width}x${fieldCanvas.height}`;
    if (signature === visualSignature) return;
    visualSignature = signature;
    const random = rngFactory(seed ^ hashString(signature));
    const count = Math.round(70 + world.entropy * 90 + world.portal_energy * 45);
    visualParticles = Array.from({length: count}, (_, index) => ({
      x: random(),
      y: random(),
      depth: .2 + random() * .8,
      size: .35 + random() * (1.6 + world.portal_energy * 1.6),
      phase: random() * Math.PI * 2,
      drift: (random() - .5) * (.08 + world.weather_intensity * .32),
      lane: mix32(seed + index * 2654435761) / 0xffffffff
    }));
  }

  function resizeCanvas() {
    const ratio = Math.min(2, globalThis.devicePixelRatio || 1);
    const width = Math.max(1, Math.floor(innerWidth * ratio));
    const height = Math.max(1, Math.floor(innerHeight * ratio));
    if (fieldCanvas.width !== width || fieldCanvas.height !== height) {
      fieldCanvas.width = width;
      fieldCanvas.height = height;
      fieldCanvas.style.width = `${innerWidth}px`;
      fieldCanvas.style.height = `${innerHeight}px`;
      visualSignature = '';
    }
  }

  function drawField() {
    resizeCanvas();
    const world = readWorld();
    const seed = seedU32();
    rebuildParticles(seed, world);
    const width = fieldCanvas.width;
    const height = fieldCanvas.height;
    ctx.clearRect(0, 0, width, height);

    const time = frame / 60;
    const portalX = width * (.5 + Math.sin((seed % 1000) * .001) * .09);
    const portalY = height * (.30 + world.depth * .20);
    const portalRadius = Math.min(width, height) * (.05 + world.portal_energy * .13);
    const glow = ctx.createRadialGradient(portalX, portalY, 0, portalX, portalY, portalRadius * 2.4);
    glow.addColorStop(0, `rgba(104, 234, 255, ${.08 + world.portal_energy * .18})`);
    glow.addColorStop(.35, `rgba(80, 169, 255, ${.04 + world.portal_energy * .08})`);
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, height);

    for (const particle of visualParticles) {
      const depthScale = .45 + particle.depth * .8;
      const driftX = Math.sin(time * (.10 + world.weather_intensity * .25) + particle.phase) * width * particle.drift * .012;
      const driftY = ((time * (2 + world.depth * 4) * particle.depth) % (height * .08));
      const x = (particle.x * width + driftX + width) % width;
      const y = (particle.y * height + driftY) % height;
      const alpha = .10 + particle.depth * .32 + world.portal_energy * .14;
      ctx.beginPath();
      ctx.arc(x, y, particle.size * depthScale * (fieldCanvas.width / Math.max(1, innerWidth)), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${120 + Math.round(particle.lane * 75)}, ${205 + Math.round(particle.lane * 45)}, 255, ${alpha})`;
      ctx.fill();
    }

    const lineCount = Math.round(2 + world.entropy * 6);
    ctx.lineWidth = Math.max(1, fieldCanvas.width / Math.max(1, innerWidth) * .55);
    for (let i = 0; i < lineCount; i += 1) {
      const h = mix32(seed + i * 977);
      const y = ((h % 10000) / 10000) * height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.bezierCurveTo(width * .3, y - world.depth * 80, width * .7, y + world.portal_energy * 100, width, y - world.weather_intensity * 60);
      ctx.strokeStyle = `rgba(112, 230, 255, ${.015 + world.entropy * .035})`;
      ctx.stroke();
    }

    frame += 1;
    requestAnimationFrame(drawField);
  }

  function refreshCauses() {
    const world = readWorld();
    const seed = seedU32();
    $('seed-hash').textContent = seed.toString(16).padStart(8, '0');
    $('receipt-seed').textContent = String(seed);
    $('world-hash').textContent = worldHash(world);
    visualSignature = '';

    const forge = audioForge();
    if (forge) {
      try { forge.setWorldState(world); }
      catch (error) { $('audio-note').textContent = `World-state update rejected: ${error.message}`; }
    }
    renderAudioState();
  }

  async function enableAudio() {
    const forge = audioForge();
    if (!forge) {
      $('audio-note').textContent = 'Audio Forge runtime is unavailable.';
      return;
    }
    try {
      const enabled = await forge.enable({seed: seedU32(), world_state: readWorld()});
      $('audio-note').textContent = enabled
        ? 'Audio Forge enabled from explicit user gesture. It remains presentation-only.'
        : 'This browser does not expose WebAudio.';
    } catch (error) {
      $('audio-note').textContent = `Audio Forge blocked: ${error.message}`;
    }
    renderAudioState();
  }

  function disableAudio() {
    audioForge()?.disable();
    $('audio-note').textContent = 'Audio Forge muted. World state was not changed.';
    renderAudioState();
  }

  function cueAudio(kind) {
    const ok = audioForge()?.cue(kind, .72) || false;
    $('audio-note').textContent = ok
      ? `Cue ${kind} rendered locally; canonical world state unchanged.`
      : 'Enable Audio Forge before firing a cue.';
    renderAudioState();
  }

  renderWorldControls();
  seedInput.addEventListener('input', refreshCauses);
  $('enable-audio').addEventListener('click', enableAudio);
  $('disable-audio').addEventListener('click', disableAudio);
  document.querySelectorAll('[data-cue]').forEach(button => button.addEventListener('click', () => cueAudio(button.dataset.cue)));
  addEventListener('genesis:audio-forge-ready', renderAudioState);
  addEventListener('genesis:audio-forge-state', renderAudioState);
  addEventListener('resize', () => { visualSignature = ''; });

  refreshCauses();
  renderAudioState();
  loadContracts();
  requestAnimationFrame(drawField);
  setInterval(renderAudioState, 1000);
})();
