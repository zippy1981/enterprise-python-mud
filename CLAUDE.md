# Working on Azurath

Azurath is a Python MUD that teaches Python by having the player build a real project.
The game, its dungeons, and the players' projects all have to work on **Windows, macOS
and Linux** (CI runs all three), so follow these rules.

## Rules

- **No symbolic links. Ever.** Don't commit symlinks, and don't create them in code,
  tests, scripts or the reference solutions (`os.symlink`, `Path.symlink_to`,
  `ln -s`, `mklink`). On Windows, creating a symlink needs admin rights or Developer
  Mode, and git checks them out as plain text files unless `core.symlinks` is on.
  Instead:
  - to put a command on PATH, use `azurath.workspace.write_python_shim()` (it writes a
    `python.cmd` on Windows and an executable `sh` script elsewhere)
  - to share a file between places, copy it, or read it from its one real location
  - `tests/test_portability.py` fails if a symlink is tracked or a symlink call
    appears in the code
- **Delete folders with `azurath.workspace.remove_tree()`**, not `shutil.rmtree()`. git
  marks its object files read-only, and Windows refuses to delete read-only files.
- **Shell commands differ per OS.** Player-facing `!` commands run in PowerShell on
  Windows and `$SHELL` elsewhere. Tests that rely on POSIX shell syntax must be skipped
  on Windows (`@pytest.mark.skipif(sys.platform == "win32", ...)`), and lesson text
  should give PowerShell variants.
- **Paths:** use `pathlib`, always open text files with `encoding="utf-8"`, and never
  hard-code `/` or `\\` separators in paths you build.

- **YAML schemas are JSON Schema**, in `src/azurath/schemas/*.schema.json`, not Python
  code. Every tracked `.yaml`/`.yml` needs a rule in `tests/test_yaml_schemas.py`. Load
  YAML with `azurath.yamlstrict` (rejects duplicate keys) and validate with
  `azurath.yamlschema`.
- **Refresh dungeon checksums after any dungeon change.** Each dungeon's checksum is
  stored in `src/azurath/dungeons/<id>/checksum.py`; the game warns players when the files
  don't match it, and `tests/test_checksums.py` fails. Run
  `uv run python -m azurath.checksums` and commit the result. On a merge conflict in a
  `checksum.py`, take either side and rerun the command.

## Checks before you finish

```bash
uv run python -m azurath.checksums   # after changing any dungeon file
uv run ruff check . && uv run ruff format --check .
uv run pytest -q          # fast tests
uv run pytest -m slow -q  # plays every dungeon with the reference solutions
```

Content work has its own skills and agents in `.claude/` (`add-room`, `verify-room`,
`playtest`, `lesson-reviewer`, `playtester`, `quest-breaker`). See `docs/dungeons.md`
for how dungeons are laid out.
