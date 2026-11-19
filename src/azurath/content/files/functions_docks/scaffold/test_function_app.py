import json

import azure.functions as func

import function_app

create_quest = function_app.create_quest.build().get_user_function()


def post(body: bytes) -> func.HttpResponse:
    return create_quest(func.HttpRequest(method="POST", url="/api/quests", body=body))


def test_valid_quest_is_created() -> None:
    resp = post(json.dumps({"title": "Slay the dragon", "reward": 500}).encode())
    assert resp.status_code == 201
    # TODO: check the response body has a slug


def test_invalid_quest_is_rejected() -> None:
    # TODO
    ...
