(() => {
  'use strict';

  // Source-tree compatibility bridge.
  // `site/index.html` is also useful directly under branch-based Pages or local
  // static serving, while the canonical Audio Forge intentionally lives at the
  // repository root. The custom Pages packager overwrites this bridge in
  // `_site/` with the canonical root file, so deployed runtime never depends on
  // this indirection.
  const current = document.currentScript;
  if (!current?.src) {
    throw new Error('GENESIS_AUDIO_FORGE_BRIDGE_NO_CURRENT_SCRIPT');
  }

  const canonical = new URL('../genesis-audio-forge.js', current.src).href;
  const escaped = canonical.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  document.write(`<script src="${escaped}"><\/script>`);
})();
