"""`azurath web`: the map layout, the STEP cards and the local HTTP API."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from azurath import gitcheck
from azurath.content import load_atlas, load_dungeon
from azurath.settings import AzurathSettings
from azurath.web import guided
from azurath.web.layout import layout
from azurath.web.server import WebGame, make_handler

# --- the map ------------------------------------------------------------------------------


@pytest.mark.parametrize("dungeon", load_atlas().ordered(), ids=lambda d: d.id)
def test_every_room_gets_its_own_spot(dungeon) -> None:
    spots = layout(dungeon)
    assert set(spots) == set(dungeon.rooms)
    assert len(set(spots.values())) == len(spots), "two rooms on the same spot"
    assert min(x for x, _ in spots.values()) == 0 and min(y for _, y in spots.values()) == 0


def test_exits_point_the_right_way() -> None:
    dungeon = load_dungeon("pythonwood")
    spots = layout(dungeon)
    start = dungeon.rooms[dungeon.start]
    for direction, target in start.exits.items():
        (x0, y0), (x1, y1) = spots[start.id], spots[target]
        if direction == "north":
            assert y1 < y0
        if direction == "east":
            assert x1 > x0


# --- STEP cards ---------------------------------------------------------------------------

STARTER = """\
# practice.py
x = 1

# STEP 1: make pet_name hold the text Pip.
#         One = stores a value. Pick the right line.
# pet name = "Pip"
# pet_name = "Pip"

# STEP 2: Uncomment BOTH of these lines:
#     total = 0
#     total += 1

# STEP 3: Uncomment the RIGHT test (both of its lines).
# def test_add():
#     assert add(2, 3) == 6

# def test_add():
#     assert add(2, 3) == 5

def loop(words):
    # STEP 4: Pick the loop...
    # for words in word:
    # for word in words:
    # ...and the line that adds up.
    #     total = len(word)
    #     total += len(word)
    return 0
"""


def test_steps_and_their_choices() -> None:
    steps = {s.label: s for s in guided.parse_steps(STARTER)}
    assert list(steps) == ["1", "2", "3", "4a", "4b"]
    assert [c.text for c in steps["1"].choices] == ['pet name = "Pip"', 'pet_name = "Pip"']
    assert "One = stores a value" in steps["1"].prompt  # prose, not a choice
    assert len(steps["2"].choices) == 1 and len(steps["2"].choices[0].lines) == 2  # BOTH
    assert [len(c.lines) for c in steps["3"].choices] == [2, 2]  # a def and its body
    assert [c.text.strip() for c in steps["4b"].choices] == [
        "total = len(word)",
        "total += len(word)",
    ]


def test_choosing_switches_one_card_on_and_the_others_off() -> None:
    first = guided.choose(STARTER, STARTER, "1", 0)
    assert '\npet name = "Pip"\n' in first
    second = guided.choose(STARTER, first, "1", 1)
    assert '\n# pet name = "Pip"\n' in second and '\npet_name = "Pip"\n' in second
    states = {s.label: [c.chosen for c in s.choices] for s in guided.with_state(STARTER, second)}
    assert states["1"] == [False, True] and states["2"] == [False]
    assert len(second.splitlines()) == len(STARTER.splitlines())  # never adds or drops lines


def test_choosing_keeps_indentation() -> None:
    text = guided.choose(STARTER, STARTER, "4b", 1)
    assert "\n        total += len(word)\n" in text  # 4 for the def + 4 for the loop body


def test_a_hand_edited_file_is_refused() -> None:
    with pytest.raises(guided.ChoiceError, match="added or removed"):
        guided.choose(STARTER, STARTER + "extra = 1\n", "1", 0)
    with pytest.raises(guided.ChoiceError, match="no choice 9"):
        guided.choose(STARTER, STARTER, "1", 8)


# --- the HTTP API -------------------------------------------------------------------------

TOKEN = "test-token"


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    assert gitcheck.set_global_identity("Ada Lovelace", "ada@example.com").ok
    settings = AzurathSettings(workspace=tmp_path / "proj", dungeon="pythonwood")
    web = WebGame(settings, load_dungeon("pythonwood"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(web, TOKEN))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(
    base: str, method: str, path: str, body: dict | None = None, token: str = TOKEN, host=None
):
    request = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Azurath-Token": token, "Content-Type": "application/json"},
    )
    if host:
        request.add_header("Host", host)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a proxy
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


def test_the_api_needs_the_token_and_a_local_host(server: str) -> None:
    assert call(server, "GET", "/api/state", token="wrong")[0] == 403
    assert call(server, "GET", "/api/state", host="evil.example")[0] == 403


def test_playing_through_the_api(server: str) -> None:
    status, state = call(server, "GET", "/api/state")
    assert status == 200
    snap = state["snapshot"]
    assert snap["dungeon"] == "pythonwood" and set(state["layout"]) == {
        r["id"] for r in snap["map"]
    }

    status, ran = call(server, "POST", "/api/run", {"line": "check"})
    assert status == 200 and ran["snapshot"]["check_passed"] is False
    assert "<span" in ran["result"]["html"]

    status, saved = call(server, "PUT", "/api/file", {"path": "hello.py", "content": "print(1)\n"})
    assert status == 200 and saved["saved"]
    status, read = call(server, "GET", "/api/file?path=hello.py")
    assert read["content"] == "print(1)\n"
    status, files = call(server, "GET", "/api/files")
    assert "hello.py" in files["files"]


def test_files_outside_the_project_are_refused(server: str) -> None:
    call(server, "GET", "/api/state")
    for path in ("../escape.py", "/etc/passwd", ".git/config"):
        status, body = call(server, "PUT", "/api/file", {"path": path, "content": "x"})
        assert status == 400, path
    status, _ = call(server, "GET", "/api/file?path=../../etc/passwd")
    assert status == 400


def test_static_files_are_served_without_a_token(server: str) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(server + "/", timeout=10) as response:
        page = response.read().decode()
    assert "<title>Azurath</title>" in page and "Content-Security-Policy" in page
    with pytest.raises(urllib.error.HTTPError):
        opener.open(server + "/../pyproject.toml", timeout=10)
