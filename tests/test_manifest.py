import json
import tomllib
from importlib import resources

from conftest import ROOT
from vllm_hust_utility_victim import __version__


def test_manifest_entrypoints_and_provenance():
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    manifest = json.loads(resources.files('vllm_hust_utility_victim.manifests').joinpath(
        'vllm-hust-extension-v0.2.json').read_text())
    assert config['project']['entry-points']['vllm_hust.extension_bundles'][
        manifest['extension_id']] == 'vllm_hust_utility_victim.manifests'
    assert manifest['extension_version'] == __version__
    assert config['project']['entry-points']['vllm.general_plugins']['utility_victim'].endswith(':register')
    assert manifest['activation']['environment'] == {'VLLM_HUST_UTILITY_VICTIM_ENABLE': '1'}
    provenance = manifest['activation']['additional_config']['utility_victim_mod_provenance']
    assert len(provenance['source_ascend']) == 40
    assert len(provenance['source_core']) == 40
    assert provenance['performance_verified'] is False
