# Azurath for VS Code (preview)

Play Azurath in a side panel, next to the code you're writing, instead of in a terminal.

- **The game in the activity bar.** You get the room, the mentor, the quest's live
  checklist, buttons for exits and common commands, a clickable map and a command box.
  Every typed command still works.
- **Checks become squiggles.** When `check` finds a problem in a file at a line
  (`hello.py line 3`, `mood.py line 7 is pushed in by 2 spaces`), it's underlined in the
  editor and listed under Problems.
- **Check on save** (`azurath.checkOnSave`, on by default), plus **Ctrl+Alt+C** and a
  status-bar button.
- **`edit hello.py` opens the file in a VS Code tab** instead of launching an editor.

It talks to the game through `python -m azurath.session`, the JSON-lines API in
`src/azurath/session.py`. There's no build step: the extension is plain JavaScript.

## Try it

1. Open **this folder** (`vscode-extension/`) in VS Code and press **F5** ("Run the Azurath
   extension"). A second VS Code window opens with the extension loaded.
2. In that window, open your **project folder** (for example `critter-quest/`).
3. Point the extension at the game. In settings, set `azurath.command` to
   `["uv", "run", "--project", "/path/to/enterprise-python-mud", "python", "-m", "azurath.session"]`.
   The default, `python -m azurath.session`, works if `azurath` is installed in the
   Python on your PATH.
4. Click the Azurath icon in the activity bar.

## Tests

```bash
cd vscode-extension
npm test   # node --test: the diagnostics parser, and a real game over JSON lines
```

The client test starts the game with `uv run --project <repo> python -m azurath.session`.
Set `AZURATH_SESSION_CMD` (a JSON array) to use another command.

## Not yet

- Packaging (`vsce package`) and the Marketplace
- Choosing a dungeon from a picker (set `azurath.dungeon` for now)
- Answering the game's questions: they take their defaults
- Guided rooms: "uncomment this choice" CodeLens buttons above each STEP
