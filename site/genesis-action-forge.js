(() => {
  'use strict';

  const CONFIG = Object.freeze({
    save_key: 'janus.genesis.world_shell_r0.save.v1',
    session_result_key: 'janus.genesis.action_forge_r0.result',
    world_id: 'GENESIS_ONE_WORLD_R0',
    world_seed: 'genesis-one-world-r0',
    generator_version: 'GENESIS_WORLD_SHELL_R0.1.0',
    max_text_chars: 280,
    max_move_steps: 40,
    max_concept_chars: 64,
    max_mutations: 512,
    max_chronicle_events: 2048
  });

  const DIRECTIONS = Object.freeze({
    N: [0, -1], NE: [1, -1], E: [1, 0], SE: [1, 1],
    S: [0, 1], SW: [-1, 1], W: [-1, 0], NW: [-1, -1]
  });
  const DIRECTION_ORDER = Object.freeze(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']);
  const MIRRORS = Object.freeze(['ORIGIN', 'NOCTURNE', 'AETHER', 'EMBER']);

  const $ = id => document.getElementById(id);

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

  function hex32(value) {
    return (value >>> 0).toString(16).padStart(8, '0');
  }

  function stableValue(value) {
    if (Array.isArray(value)) return `[${value.map(stableValue).join(',')}]`;
    if (value && typeof value === 'object') {
      const keys = Object.keys(value).sort();
      return `{${keys.map(key => `${JSON.stringify(key)}:${stableValue(value[key])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFKC')
      .trim()
      .replace(/\s+/g, ' ')
      .slice(0, CONFIG.max_text_chars);
  }

  function safeNumber(value, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function readSave() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CONFIG.save_key) || 'null');
      if (parsed && parsed.world_id === CONFIG.world_id && parsed.world_seed === CONFIG.world_seed) return parsed;
    } catch (error) {
      console.warn('Action Forge could not parse World Shell save:', error);
    }
    return {
      schema: 'janus.genesis.world_shell_save.v1',
      generator_version: CONFIG.generator_version,
      world_id: CONFIG.world_id,
      world_seed: CONFIG.world_seed,
      player_position: {x: .5, y: .5},
      mirror_profile: 'ORIGIN',
      presentation_dimension: '3D',
      camera_mode: 'ISOMETRIC',
      camera_heading: -Math.PI / 4,
      discovered_chunk_coordinates: [],
      explicit_world_mutations: [],
      chronicle_hash_chain: []
    };
  }

  function canonicalSeedState(save) {
    const mutations = Array.isArray(save.explicit_world_mutations)
      ? save.explicit_world_mutations.map(item => ({
          id: String(item?.id || ''),
          type: String(item?.type || ''),
          x: safeNumber(item?.x, 0),
          y: safeNumber(item?.y, 0),
          recipe: String(item?.recipe || '')
        }))
      : [];
    const discovered = Array.isArray(save.discovered_chunk_coordinates)
      ? save.discovered_chunk_coordinates
          .filter(item => Array.isArray(item) && item.length === 2)
          .map(item => [Number(item[0]) || 0, Number(item[1]) || 0])
          .sort((a, b) => a[0] - b[0] || a[1] - b[1])
      : [];
    const chronicle = Array.isArray(save.chronicle_hash_chain) ? save.chronicle_hash_chain : [];
    return {
      world_id: CONFIG.world_id,
      world_seed: CONFIG.world_seed,
      generator_version: CONFIG.generator_version,
      player_position: {
        x: Math.round(safeNumber(save.player_position?.x, .5) * 1000) / 1000,
        y: Math.round(safeNumber(save.player_position?.y, .5) * 1000) / 1000
      },
      discovered_chunk_coordinates: discovered,
      explicit_world_mutations: mutations,
      chronicle_length: chronicle.length,
      chronicle_tip_hash: String(chronicle.at(-1)?.event_hash || 'GENESIS_ORIGIN')
    };
  }

  function worldStateHash(save) {
    return hex32(hashString(stableValue(canonicalSeedState(save))));
  }

  function actionSeed(save, normalizedText) {
    return hashString(`${stableValue(canonicalSeedState(save))}|${normalizedText.toLowerCase()}`);
  }

  function directionFromText(lower, seed) {
    const patterns = [
      ['NE', /(северо[- ]?вост|north[- ]?east|northeast)/],
      ['NW', /(северо[- ]?запад|north[- ]?west|northwest)/],
      ['SE', /(юго[- ]?вост|south[- ]?east|southeast)/],
      ['SW', /(юго[- ]?запад|south[- ]?west|southwest)/],
      ['N', /(на север|север\b|north\b)/],
      ['S', /(на юг|юг\b|south\b)/],
      ['E', /(на восток|восток\b|east\b)/],
      ['W', /(на запад|запад\b|west\b)/]
    ];
    for (const [id, pattern] of patterns) if (pattern.test(lower)) return id;
    return DIRECTION_ORDER[seed % DIRECTION_ORDER.length];
  }

  function stepsFromText(lower, seed) {
    const match = lower.match(/(\d{1,2})\s*(?:шаг\w*|steps?|tiles?)/);
    if (match) return clamp(Number(match[1]), 1, CONFIG.max_move_steps);
    return 3 + (seed % 6);
  }

  function conceptFromText(text) {
    const stripped = text
      .replace(/\b(создай|создать|построй|построить|сделай|сделать|поставь|поставить|размести|разместить|create|build|make|place)\b/gi, ' ')
      .replace(/[^\p{L}\p{N}_ -]+/gu, ' ')
      .replace(/\s+/g, ' ')
      .trim();
    return (stripped || 'ACTION ANCHOR').slice(0, CONFIG.max_concept_chars);
  }

  function compileAction(text, save) {
    const normalized = normalizeText(text);
    if (!normalized) return {ok: false, error: 'EMPTY ACTION'};
    const lower = normalized.toLowerCase();
    const seed = actionSeed(save, normalized);
    const state_hash = worldStateHash(save);
    const base = {ok: true, text: normalized, action_seed: hex32(seed), world_state_hash: state_hash};

    if (/\b(nocturne|ноктюрн)\b/.test(lower)) return {...base, intent: 'SET_MIRROR', mirror: 'NOCTURNE'};
    if (/\b(aether|эфир|аэтер)\b/.test(lower)) return {...base, intent: 'SET_MIRROR', mirror: 'AETHER'};
    if (/\b(ember|эмбер|угли|пепел)\b/.test(lower)) return {...base, intent: 'SET_MIRROR', mirror: 'EMBER'};
    if (/\b(origin|ориджин|исток)\b/.test(lower)) return {...base, intent: 'SET_MIRROR', mirror: 'ORIGIN'};

    if (/(перв\w*\s+лиц|first[- ]?person|1p\b)/.test(lower)) return {...base, intent: 'SET_CAMERA', camera: 'FIRST_PERSON'};
    if (/(треть\w*\s+лиц|third[- ]?person|3p\b)/.test(lower)) return {...base, intent: 'SET_CAMERA', camera: 'THIRD_PERSON'};
    if (/(изометр|isometric|\biso\b)/.test(lower)) return {...base, intent: 'SET_CAMERA', camera: 'ISOMETRIC'};
    if (/(\b2d\b|\b2д\b|двумер)/.test(lower)) return {...base, intent: 'SET_DIMENSION', dimension: '2D'};
    if (/(\b3d\b|\b3д\b|тр[её]хмер)/.test(lower)) return {...base, intent: 'SET_DIMENSION', dimension: '3D'};

    if (/(вернись|вернуться|домой|к очагу|к огню|hearth|first fire|return home)/.test(lower)) {
      return {...base, intent: 'RETURN_TO_HEARTH'};
    }

    if (/(поверни|повернуться|turn|rotate)/.test(lower)) {
      if (/(налево|влево|left)/.test(lower)) return {...base, intent: 'TURN_CAMERA', direction: 'LEFT'};
      if (/(направо|вправо|right)/.test(lower)) return {...base, intent: 'TURN_CAMERA', direction: 'RIGHT'};
      return {...base, intent: 'TURN_CAMERA', direction: seed % 2 ? 'RIGHT' : 'LEFT'};
    }

    if (/(оставь\s+(?:знак|метк)|поставь\s+(?:знак|метк)|leave\s+(?:a\s+)?mark|place\s+(?:a\s+)?mark)/.test(lower)) {
      return {...base, intent: 'PLACE_MARK'};
    }

    if (/\b(создай|создать|построй|построить|сделай|сделать|поставь|поставить|размести|разместить|create|build|make|place)\b/.test(lower)) {
      return {...base, intent: 'PLACE_ACTION_ANCHOR', concept: conceptFromText(normalized)};
    }

    if (/(иди|пойди|двиг|беги|шагай|исследуй|исследовать|броди|впер[её]д|walk|move|run|explore|wander|go\b)/.test(lower)) {
      const direction = directionFromText(lower, seed);
      return {...base, intent: 'MOVE', direction, steps: stepsFromText(lower, seed)};
    }

    return {
      ok: false,
      error: 'UNKNOWN ACTION // try: «иди на север 5 шагов», «построй маяк», «оставь знак», «первое лицо», «EMBER»',
      action_seed: hex32(seed),
      world_state_hash: state_hash
    };
  }

  async function sha256Hex(text) {
    if (globalThis.crypto?.subtle) {
      const bytes = new TextEncoder().encode(text);
      const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    }
    return `fnv1a32-${hex32(hashString(text))}`;
  }

  async function appendChronicle(save, payload) {
    if (!Array.isArray(save.chronicle_hash_chain)) save.chronicle_hash_chain = [];
    if (save.chronicle_hash_chain.length >= CONFIG.max_chronicle_events) return;
    const sequence = save.chronicle_hash_chain.length + 1;
    const previous_hash = save.chronicle_hash_chain.at(-1)?.event_hash || 'GENESIS_ORIGIN';
    const body = {sequence, previous_hash, ...payload};
    const event_hash = await sha256Hex(stableValue(body));
    save.chronicle_hash_chain.push({...body, event_hash});
  }

  function writeSave(save) {
    localStorage.setItem(CONFIG.save_key, JSON.stringify(save));
  }

  function queueReloadResult(message) {
    sessionStorage.setItem(CONFIG.session_result_key, message);
    location.reload();
  }

  function clickOption(containerId, target) {
    const root = $(containerId);
    if (!root) return false;
    const wanted = String(target).replaceAll('_', ' ');
    const button = Array.from(root.querySelectorAll('button')).find(node => {
      const text = node.textContent.toUpperCase();
      return text.includes(wanted) || text.includes(String(target));
    });
    if (!button) return false;
    button.click();
    return true;
  }

  function openMirrorPanel() {
    const panel = $('mirror-panel');
    if (panel?.hidden) $('mirror-toggle')?.click();
  }

  async function executePlan(plan) {
    if (!plan?.ok) throw new Error(plan?.error || 'INVALID ACTION PLAN');
    const save = readSave();

    if (plan.intent === 'MOVE') {
      const vector = DIRECTIONS[plan.direction];
      if (!vector) throw new Error('DIRECTION REJECTED');
      const length = Math.hypot(vector[0], vector[1]) || 1;
      const stepScale = 1 / length;
      save.player_position = save.player_position || {x: .5, y: .5};
      save.player_position.x = Math.round((safeNumber(save.player_position.x, .5) + vector[0] * stepScale * plan.steps) * 1000) / 1000;
      save.player_position.y = Math.round((safeNumber(save.player_position.y, .5) + vector[1] * stepScale * plan.steps) * 1000) / 1000;
      writeSave(save);
      queueReloadResult(`ACTION APPLIED // MOVE ${plan.direction} × ${plan.steps} // SEED ${plan.action_seed}`);
      return;
    }

    if (plan.intent === 'RETURN_TO_HEARTH') {
      save.player_position = {x: .5, y: .5};
      writeSave(save);
      queueReloadResult(`ACTION APPLIED // RETURN TO FIRST FIRE // SEED ${plan.action_seed}`);
      return;
    }

    if (plan.intent === 'PLACE_MARK' || plan.intent === 'PLACE_ACTION_ANCHOR') {
      if (!Array.isArray(save.explicit_world_mutations)) save.explicit_world_mutations = [];
      if (save.explicit_world_mutations.length >= CONFIG.max_mutations) throw new Error('LOCAL MUTATION CAP REACHED');
      const x = Math.round(safeNumber(save.player_position?.x, .5) * 4) / 4;
      const y = Math.round(safeNumber(save.player_position?.y, .5) * 4) / 4;
      const concept = plan.intent === 'PLACE_ACTION_ANCHOR' ? plan.concept : 'PLAYER MARK';
      const slug = concept.toUpperCase().replace(/[^A-Z0-9А-ЯЁ]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 32) || 'ANCHOR';
      const id = `action-${plan.action_seed}-${hex32(hashString(`${x}|${y}|${save.explicit_world_mutations.length}`))}`;
      const mutation = {
        id,
        type: 'PLAYER_MARK',
        x,
        y,
        recipe: plan.intent === 'PLACE_ACTION_ANCHOR' ? `GENESIS_ACTION_ANCHOR_${slug}_R0` : 'GENESIS_PLAYER_MARK_R0',
        action_forge: {
          schema: 'janus.genesis.action_intent.v1',
          intent: plan.intent,
          concept,
          action_seed: plan.action_seed,
          source_text: plan.text.slice(0, CONFIG.max_text_chars)
        }
      };
      save.explicit_world_mutations.push(mutation);
      await appendChronicle(save, {
        type: plan.intent === 'PLACE_ACTION_ANCHOR' ? 'ACTION_ANCHOR_PLACED' : 'PLAYER_MARK_PLACED',
        mutation_id: id,
        position: [x, y],
        chunk: [Math.floor(x / 10), Math.floor(y / 10)],
        action_seed: plan.action_seed
      });
      writeSave(save);
      queueReloadResult(`ACTION APPLIED // ${plan.intent === 'PLACE_ACTION_ANCHOR' ? `ANCHOR «${concept}»` : 'PLAYER MARK'} // SEED ${plan.action_seed}`);
      return;
    }

    if (plan.intent === 'TURN_CAMERA') {
      const key = plan.direction === 'LEFT' ? 'q' : 'f';
      dispatchEvent(new KeyboardEvent('keydown', {key, bubbles: true}));
      return `PRESENTATION APPLIED // TURN ${plan.direction} // WORLD FACTS UNCHANGED`;
    }

    if (plan.intent === 'SET_MIRROR') {
      if (!MIRRORS.includes(plan.mirror)) throw new Error('MIRROR REJECTED');
      openMirrorPanel();
      if (!clickOption('mirror-options', plan.mirror)) throw new Error('MIRROR CONTROL UNAVAILABLE');
      return `PRESENTATION APPLIED // MIRROR ${plan.mirror} // WORLD FACTS UNCHANGED`;
    }

    if (plan.intent === 'SET_DIMENSION') {
      openMirrorPanel();
      if (!clickOption('dimension-options', plan.dimension)) throw new Error('DIMENSION CONTROL UNAVAILABLE');
      return `PRESENTATION APPLIED // ${plan.dimension} // WORLD FACTS UNCHANGED`;
    }

    if (plan.intent === 'SET_CAMERA') {
      openMirrorPanel();
      if (!clickOption('camera-options', plan.camera)) throw new Error('CAMERA CONTROL UNAVAILABLE');
      return `PRESENTATION APPLIED // ${plan.camera.replaceAll('_', ' ')} // WORLD FACTS UNCHANGED`;
    }

    throw new Error('INTENT NOT ALLOWLISTED');
  }

  function renderPlan(plan) {
    const node = $('action-plan');
    if (!node) return;
    if (!plan.ok) {
      node.textContent = plan.error;
      node.classList.add('rejected');
      return;
    }
    node.classList.remove('rejected');
    const details = plan.intent === 'MOVE' ? ` ${plan.direction} × ${plan.steps}`
      : plan.intent === 'PLACE_ACTION_ANCHOR' ? ` «${plan.concept}»`
      : plan.intent === 'SET_MIRROR' ? ` ${plan.mirror}`
      : plan.intent === 'SET_DIMENSION' ? ` ${plan.dimension}`
      : plan.intent === 'SET_CAMERA' ? ` ${plan.camera.replaceAll('_', ' ')}`
      : plan.intent === 'TURN_CAMERA' ? ` ${plan.direction}` : '';
    node.textContent = `${plan.intent}${details} // ${plan.action_seed}`;
  }

  function updateSeedDisplay() {
    const node = $('action-state-hash');
    if (node) node.textContent = worldStateHash(readSave());
  }

  async function submitAction(event) {
    event.preventDefault();
    const input = $('action-input');
    const button = $('action-submit');
    if (!input || !button) return;
    const plan = compileAction(input.value, readSave());
    renderPlan(plan);
    if (!plan.ok) return;
    button.disabled = true;
    try {
      const message = await executePlan(plan);
      if (message) {
        $('action-result').textContent = message;
        updateSeedDisplay();
      }
      input.value = '';
    } catch (error) {
      $('action-result').textContent = `ACTION BLOCKED // ${error.message}`;
    } finally {
      button.disabled = false;
    }
  }

  function restoreReloadResult() {
    const message = sessionStorage.getItem(CONFIG.session_result_key);
    if (!message) return;
    sessionStorage.removeItem(CONFIG.session_result_key);
    const enter = $('enter-world');
    if (enter) setTimeout(() => enter.click(), 30);
    const result = $('action-result');
    if (result) result.textContent = message;
  }

  function bind() {
    $('action-form')?.addEventListener('submit', submitAction);
    $('action-input')?.addEventListener('input', event => {
      const plan = compileAction(event.target.value, readSave());
      renderPlan(plan);
    });
    updateSeedDisplay();
    restoreReloadResult();
    setInterval(updateSeedDisplay, 1200);
  }

  globalThis.GENESIS_ACTION_FORGE = Object.freeze({
    compile: text => compileAction(text, readSave()),
    stateHash: () => worldStateHash(readSave()),
    canonicalSeedState: () => canonicalSeedState(readSave())
  });

  bind();
})();
