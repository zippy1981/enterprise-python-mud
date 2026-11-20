"""Azure Functions entry point (Python v2 programming model)."""

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from questboard.models import Quest

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger(__name__)


@app.route(route="quests", methods=["POST"])
def create_quest(req: func.HttpRequest) -> func.HttpResponse:
    # TODO:
    #  * Quest.model_validate_json(req.get_body())
    #  * on ValidationError: 400 with {"errors": [...]}  (hint: json.loads(exc.json(include_url=False)))
    #  * otherwise: 201 with quest.model_dump_json()
    return func.HttpResponse("TODO", status_code=501)
