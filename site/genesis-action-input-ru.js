(() => {
  'use strict';

  function normalizeRussianAction(value) {
    let text = String(value || '');
    text = text
      .replace(/ноктюрн/gi, 'nocturne')
      .replace(/(?:аэтер|эфир)/gi, 'aether')
      .replace(/(?:эмбер|угли|пепел)/gi, 'ember')
      .replace(/(?:ориджин|исток)/gi, 'origin')
      .replace(/2д/gi, '2d')
      .replace(/3д/gi, '3d');

    if (!/(метк|знак)/i.test(text)) {
      text = text.replace(/(?:создай|создать|построй|построить|сделай|сделать|поставь|поставить|размести|разместить)/gi, 'create');
    }
    return text;
  }

  function isActionInput(target) {
    return target instanceof HTMLInputElement && target.id === 'action-input';
  }

  for (const type of ['keydown', 'keyup', 'keypress']) {
    document.addEventListener(type, event => {
      if (isActionInput(event.target)) event.stopPropagation();
    }, true);
  }

  document.addEventListener('submit', event => {
    if (event.target?.id !== 'action-form') return;
    const input = document.getElementById('action-input');
    if (!input) return;
    const normalized = normalizeRussianAction(input.value);
    if (normalized !== input.value) {
      input.dataset.explicitOriginal = input.value;
      input.value = normalized;
    }
  }, true);

  globalThis.GENESIS_ACTION_LOCALE_RU = Object.freeze({normalize: normalizeRussianAction});
})();
