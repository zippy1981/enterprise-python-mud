import json

import azure.functions as func
import pytest

import function_app

create_quest = function_app.create_quest.build().get_user_function()


def post(body: bytes) -> func.HttpResponse:
    return create_quest(func.HttpRequest(method="POST", url="/api/quests", body=body))


def test_valid_quest_is_created() -> None:
    resp = post(json.dumps({"title": "Slay the dragon", "reward": 500}).encode())
    assert resp.status_code == 201
    body = json.loads(resp.get_body())
    assert body["slug"] == "slay-the-dragon"
    assert body["id"]


@pytest.mark.parametrize(
    "body",
    [b'{"title": "x", "reward": 1}', b'{"title": "Rats", "reward": -5}', b"not json", b""],
)
def test_invalid_quests_are_rejected(body: bytes) -> None:
    resp = post(body)
    assert resp.status_code == 400
    assert json.loads(resp.get_body())["errors"]
