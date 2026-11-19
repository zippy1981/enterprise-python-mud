"""Azure Functions entry point (Python v2 programming model)."""

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from questboard.models import Quest

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger(__name__)


def _json_response(body: str, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(body, status_code=status_code, mimetype="application/json")


@app.route(route="quests", methods=["POST"])
def create_quest(req: func.HttpRequest) -> func.HttpResponse:
    try:
        quest = Quest.model_validate_json(req.get_body())
    except ValidationError as exc:
        errors = json.loads(exc.json(include_url=False))
        return _json_response(json.dumps({"errors": errors}), 400)
    logger.info("Quest posted: %s", quest.slug)
    return _json_response(quest.model_dump_json(), 201)
