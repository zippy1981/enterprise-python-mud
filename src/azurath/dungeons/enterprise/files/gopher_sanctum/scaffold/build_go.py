"""Build questboard's Go extensions.

    uv run python scripts/build_go.py           # every target whose folder exists
    uv run python scripts/build_go.py rewards   # goext/   -> questboard/librewards.so (ctypes)
    uv run python scripts/build_go.py goquest   # goquest/ -> questboard/_goquest*.so  (C-API)

Run it with the *project's* interpreter (`uv run`): a CPython extension module
must be compiled against the same Python version that will import it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "questboard"


def shared_library_name(stem: str) -> str:
    """librewards.so on Linux, librewards.dylib on macOS, rewards.dll on Windows."""
    if sys.platform == "win32":
        return f"{stem}.dll"
    if sys.platform == "darwin":
        return f"lib{stem}.dylib"
    return f"lib{stem}.so"


def go_build(source: Path, output: Path, extra_env: dict[str, str] | None = None) -> Path:
    env = {**os.environ, "CGO_ENABLED": "1", **(extra_env or {})}
    cmd = ["go", "build", "-buildmode=c-shared", "-o", str(output), "."]
    print("$", " ".join(cmd), f"  (in {source.relative_to(ROOT)})", flush=True)
    subprocess.run(cmd, cwd=source, env=env, check=True)
    # cgo also writes a C header next to the library; Python doesn't need it.
    output.with_suffix(".h").unlink(missing_ok=True)
    return output


def build_rewards() -> Path:
    return go_build(ROOT / "goext", PACKAGE / shared_library_name("rewards"))


def build_goquest() -> Path:
    include = Path(sysconfig.get_paths()["include"])
    if not (include / "Python.h").exists():
        raise SystemExit(
            f"Python.h not found in {include}.\n"
            "Install the dev headers (e.g. `sudo apt install python3-dev`)\n"
            "or use a uv-managed Python (they ship with headers)."
        )
    suffix = sysconfig.get_config_var("EXT_SUFFIX")  # e.g. .cpython-313-x86_64-linux-gnu.so
    env = {"CGO_CFLAGS": f"-I{include}"}
    if sys.platform == "darwin":
        # Extension modules resolve Python's symbols from the interpreter at load time.
        env["CGO_LDFLAGS"] = "-undefined dynamic_lookup"
    elif sys.platform == "win32":
        libs = Path(sys.base_prefix) / "libs"
        env["CGO_LDFLAGS"] = f"-L{libs} -lpython{sys.version_info.major}{sys.version_info.minor}"
    return go_build(ROOT / "goquest", PACKAGE / f"_goquest{suffix}", env)


TARGETS: dict[str, tuple[Path, Callable[[], Path]]] = {
    "rewards": (ROOT / "goext", build_rewards),
    "goquest": (ROOT / "goquest", build_goquest),
}


def main(argv: list[str]) -> int:
    if shutil.which("go") is None:
        print("Go isn't installed (https://go.dev/dl/).", file=sys.stderr)
        return 1
    names = argv or [name for name, (src, _) in TARGETS.items() if (src / "go.mod").exists()]
    for name in names:
        if name not in TARGETS:
            print(f"unknown target {name!r}; choose from {', '.join(TARGETS)}", file=sys.stderr)
            return 2
        try:
            built = TARGETS[name][1]()
        except subprocess.CalledProcessError as exc:
            print(f"go build failed for {name} (exit {exc.returncode})", file=sys.stderr)
            return exc.returncode or 1
        print(f"built {built.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
