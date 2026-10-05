"""Check the current wheel in a temporary, clean venv without dependencies."""

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    wheel = ROOT / "dist/vllm_hust_utility_victim-0.1.0.dev2-py3-none-any.whl"
    with tempfile.TemporaryDirectory(prefix="utility-victim-wheel-") as directory:
        env = Path(directory) / "env"
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], check=True)
        subprocess.run([str(python), "-I", str(ROOT / "scripts/verify_wheel.py")], check=True)


if __name__ == "__main__":
    main()
