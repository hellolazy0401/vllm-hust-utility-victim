"""Run after an isolated wheel install, with no source-tree PYTHONPATH."""

import json
import sys
from importlib import metadata, resources

import vllm_hust_utility_victim as package

assert metadata.version("vllm-hust-utility-victim") == package.__version__
eps = metadata.entry_points(group="vllm.general_plugins")
plugin = next(ep for ep in eps if ep.name == "utility_victim")
plugin.load()()
assert not any(x == "vllm" or x.startswith(("vllm.", "vllm_ascend", "torch")) for x in sys.modules)
bundle = next(ep for ep in metadata.entry_points(group="vllm_hust.extension_bundles")
              if ep.name == "org.vllm-hust.utility-victim")
resource = resources.files(bundle.load()).joinpath("vllm-hust-extension-v0.2.json")
manifest = json.loads(resource.read_text())
assert manifest["extension_version"] == package.__version__
assert manifest["extension_id"] == bundle.name
assert resources.files(package).joinpath("host_fingerprints.json").is_file()
print("isolated wheel: version, both entry points, manifest, fingerprint, default-off import PASS")
print("installed path:", package.__file__)
