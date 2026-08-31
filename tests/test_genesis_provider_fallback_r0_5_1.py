import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
C = ROOT / '.janus' / 'GENESIS_PROVIDER_FALLBACK_R0_5_1.json'
P = ROOT / 'contracts' / 'GENESIS_PROVIDER_FALLBACK_R0_5_1.json'
PUBLIC = ROOT / 'site' / 'genesis-public-provider-fallback-r0-5-1.js'
TRUNK = ROOT / 'site' / 'genesis-asset-trunk-r0-5-1.js'
MAT = ROOT / 'site' / 'genesis-asset-materializer-v3.js'
AUDIO = ROOT / 'site' / 'genesis-audio-asset-runtime-r0-5-1.js'
EXECUTOR = ROOT / 'site' / 'genesis-scene-graph-executor-r0-5-1.js'

class ProviderFallbackR051Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads(C.read_text(encoding='utf-8')); cls.p=json.loads(P.read_text(encoding='utf-8'))
        cls.public=PUBLIC.read_text(encoding='utf-8'); cls.trunk=TRUNK.read_text(encoding='utf-8')
        cls.mat=MAT.read_text(encoding='utf-8'); cls.audio=AUDIO.read_text(encoding='utf-8'); cls.executor=EXECUTOR.read_text(encoding='utf-8')
    def test_contract_mirror_and_janus_first(self):
        self.assertEqual(self.c,self.p); self.assertTrue(self.c['janus_home_is_preferred_control_plane'])
        self.assertEqual(self.c['fallback']['providers'],['poly_haven','wikimedia_commons'])
    def test_rights_fail_closed_and_no_slime_bytes(self):
        for token in ('CC0','PUBLIC_DOMAIN','CC-BY','CC-BY-SA'): self.assertIn(token,self.public+self.mat)
        self.assertFalse(self.c['fallback']['binary_bytes_through_slime']); self.assertFalse(self.c['fallback']['canonical_world_contains_provider_binary'])
        self.assertIn("binary_transport:'DIRECT_PROVIDER_CDN_NOT_SLIME'",self.public)
    def test_wikimedia_uses_anonymous_cors(self):
        self.assertIn("origin:'*'",self.public); self.assertIn('commons.wikimedia.org/w/api.php',self.public)
    def test_poly_haven_direct_fallback_is_official_api_path(self):
        self.assertIn('api.polyhaven.com/assets',self.public); self.assertIn('api.polyhaven.com/files',self.public)
        self.assertIn('janus_preferred:true',self.trunk); self.assertIn('direct_public_fallback:true',self.trunk)
    def test_attribution_ledger_for_attribution_licenses(self):
        self.assertIn('janus.genesis.asset_attribution_r0_5_1',self.mat)
        self.assertIn("rights==='CC-BY'||rights==='CC-BY-SA'",self.mat)
        self.assertIn('license_url',self.mat); self.assertIn('author',self.mat)
    def test_external_audio_is_bounded_and_user_gesture_gated(self):
        self.assertIn('GENESIS_AUDIO_RUNTIME?.enabled',self.audio); self.assertIn('max_seconds=12',self.audio)
        self.assertIn('Math.min(20',self.audio); self.assertIn('SOUND',self.executor)
    def test_foreign_code_and_eval_absent(self):
        surface=self.public+self.trunk+self.mat+self.audio+self.executor
        for token in ('eval(','new Function','Function('): self.assertNotIn(token,surface)
        self.assertFalse(self.c['authority']['foreign_code_execution'])

if __name__=='__main__': unittest.main()
