"""Apply/restore the reviewed host patch with exact hash checks and backup."""

import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.apply and args.restore:
        parser.error("choose --apply or --restore")
    patch = Path(__file__).resolve().parents[1] / "host_patch"
    metadata = json.loads((patch / "identity.json").read_text(encoding="utf-8"))
    target = args.core_root / "vllm/v1/core/sched/scheduler.py"
    raw = target.read_bytes()
    source = raw.decode("utf-8").replace("\r\n", "\n")
    digest = hashlib.sha256(source.encode()).hexdigest()
    before, after = metadata["before_sha256"], metadata["after_sha256"]
    if digest not in {before, after}:
        raise SystemExit("Source hash differs: refusing to change " + str(target))
    backup = target.with_name("scheduler.py.utility-victim.bak")
    if not args.apply and not args.restore:
        print("PATCHED" if digest == after else "COMPATIBLE, NOT PATCHED")
        return
    if args.restore:
        if digest == before:
            print("Already original")
            return
        replacement = backup.read_bytes()
        if hashlib.sha256(replacement.decode().replace("\r\n", "\n").encode()).hexdigest() != before:
            raise SystemExit("Backup hash differs: refusing restore")
    else:
        if digest == after:
            print("Already patched")
            return
        replacement = (patch / "scheduler.after.py").read_bytes()
        if hashlib.sha256(replacement.decode().replace("\r\n", "\n").encode()).hexdigest() != after:
            raise SystemExit("Patch payload hash differs")
        if backup.exists():
            saved = backup.read_text(encoding="utf-8")
            if hashlib.sha256(saved.encode()).hexdigest() != before:
                raise SystemExit("Existing backup differs; refusing overwrite")
        else:
            with backup.open("xb") as f:
                f.write(raw)
    temporary = target.with_name("scheduler.py.utility-victim.tmp")
    with temporary.open("xb") as f:
        f.write(replacement)
    os.chmod(temporary, target.stat().st_mode)
    os.replace(temporary, target)
    print("RESTORED" if args.restore else "APPLIED; restart the vLLM process")


if __name__ == "__main__":
    main()
