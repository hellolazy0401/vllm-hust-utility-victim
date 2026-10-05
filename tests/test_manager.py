import subprocess
import sys

import pytest

from vllm_hust_utility_victim import __version__


def test_real_manager_static_discovery():
    pytest.importorskip("vllm_hust_ext")
    code = """
import sys
from vllm_hust_ext.discovery import discover_bundles
b = discover_bundles(('org.vllm-hust.utility-victim',))[0]
assert b.bundle_id == 'org.vllm-hust.utility-victim'
assert b.manifest.bundle_version == EXPECTED_VERSION
assert dict(b.manifest.activation.environment) == {'VLLM_HUST_UTILITY_VICTIM_ENABLE': '1'}
assert 'vllm_hust_utility_victim' not in sys.modules
assert 'vllm' not in sys.modules
assert 'torch' not in sys.modules
print('real manager static discovery PASS')
"""
    subprocess.run([sys.executable, "-c", code.replace("EXPECTED_VERSION", repr(__version__))], check=True)
