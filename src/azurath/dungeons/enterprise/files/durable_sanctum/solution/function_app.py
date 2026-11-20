"""Azure Functions entry point (Python v2 programming model) with Durable Functions."""

import dataclasses
import json
import logging
from typing import Any

import azure.durable_functions as df
import azure.functions as func
from pydantic import ValidationError

from questboard import orchestration
from questboard.models import Quest
from questboard.repository import Reward

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger(__name__)


def _json_response(body: str, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(body, status_code=status_code, mimetype="application/json")


def _parse_quest(req: func.HttpRequest) -> Quest | func.HttpResponse:
    try:
        return Quest.model_validate_json(req.get_body())
    except ValidationError as exc:
        errors = json.loads(exc.json(include_url=False))
        return _json_response(json.dumps({"errors": errors}), 400)


# --- HTTP ------------------------------------------------------------------------------


@app.route(route="quests", methods=["POST"])
def create_quest(req: func.HttpRequest) -> func.HttpResponse:
    quest = _parse_quest(req)
    if isinstance(quest, func.HttpResponse):
        return quest
    logger.info("Quest posted: %s", quest.slug)
    return _json_response(quest.model_dump_json(), 201)


@app.route(route="quests/process", methods=["POST"])
@app.durable_client_input(client_name="client")
async def start_quest(
    req: func.HttpRequest, client: df.DurableOrchestrationClient
) -> func.HttpResponse:
    quest = _parse_quest(req)
    if isinstance(quest, func.HttpResponse):
        return quest
    instance_id = await client.start_new(
        "process_quest_orchestrator", client_input=quest.model_dump(mode="json")
    )
    logger.info("Started orchestration %s for %s", instance_id, quest.slug)
    return client.create_check_status_response(req, instance_id)


# --- Orchestrator ------------------------------------------------------------------------


@app.orchestration_trigger(context_name="context")
def process_quest_orchestrator(context: df.DurableOrchestrationContext):
    # `yield from` forwards every yield/send to the pure generator and returns its result.
    return (yield from orchestration.process_quest(context))


# --- Activities --------------------------------------------------------------------------


@app.activity_trigger(input_name="quest")
def validate_quest(quest: dict[str, Any]) -> dict[str, Any]:
    return Quest.model_validate(quest).model_dump(mode="json")


@app.activity_trigger(input_name="notice")
def notify_guild(notice: dict[str, Any]) -> str:
    logger.info("Notifying %s about quest %s", notice["guild"], notice["quest_id"])
    return f"{notice['guild']} notified"


@app.activity_trigger(input_name="quest")
def award_reward(quest: dict[str, Any]) -> dict[str, int]:
    reward = Reward(gold=quest["reward"], xp=quest["reward"] // 10)
    return dataclasses.asdict(reward)
