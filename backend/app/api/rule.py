"""Rules API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.persistence import schedule_save
from app.core.rule import rule_engine

router = APIRouter(prefix="/rules", tags=["Rules"])


class RuleCondition(BaseModel):
    field: str
    operator: str = "=="
    value: Any = None


class RuleAction(BaseModel):
    type: str = "log"
    target: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class RuleCreate(BaseModel):
    rule_id: str = Field(..., min_length=1)
    name: str = ""
    description: str = ""
    trigger_source: str = "*"
    conditions: list[RuleCondition] = Field(default_factory=list)
    actions: list[RuleAction] = Field(default_factory=list)
    priority: int = 0
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_source: str | None = None
    conditions: list[RuleCondition] | None = None
    actions: list[RuleAction] | None = None
    priority: int | None = None
    enabled: bool | None = None


class RuleEvaluateRequest(BaseModel):
    trigger_source: str = "*"
    context: dict[str, Any] = Field(default_factory=dict)
    execute: bool = False


def _auto_save():
    try:
        schedule_save()
    except Exception:
        pass


@router.get("")
async def list_rules():
    return rule_engine.get_all_rules()


@router.post("")
async def add_rule(rule: RuleCreate):
    try:
        await rule_engine.add_rule(rule.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _auto_save()
    return {"ok": True, "rule_id": rule.rule_id}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    rule = rule_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(404, f"Rule [{rule_id}] not found")
    return rule


@router.put("/{rule_id}")
async def update_rule(rule_id: str, updates: RuleUpdate):
    data = updates.model_dump(exclude_none=True)
    if "conditions" in data:
        data["conditions"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in data["conditions"]]
    if "actions" in data:
        data["actions"] = [a.model_dump() if hasattr(a, "model_dump") else a for a in data["actions"]]
    try:
        ok = await rule_engine.update_rule(rule_id, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not ok:
        raise HTTPException(404, f"Rule [{rule_id}] not found")
    _auto_save()
    return {"ok": True, "rule_id": rule_id}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    ok = await rule_engine.remove_rule(rule_id)
    if not ok:
        raise HTTPException(404, f"Rule [{rule_id}] not found")
    _auto_save()
    return {"ok": True, "rule_id": rule_id}


@router.post("/{rule_id}/enable")
async def enable_rule(rule_id: str):
    ok = await rule_engine.update_rule(rule_id, {"enabled": True})
    if not ok:
        raise HTTPException(404, f"Rule [{rule_id}] not found")
    _auto_save()
    return {"ok": True, "rule_id": rule_id, "enabled": True}


@router.post("/{rule_id}/disable")
async def disable_rule(rule_id: str):
    ok = await rule_engine.update_rule(rule_id, {"enabled": False})
    if not ok:
        raise HTTPException(404, f"Rule [{rule_id}] not found")
    _auto_save()
    return {"ok": True, "rule_id": rule_id, "enabled": False}


@router.post("/evaluate")
async def evaluate_rules(req: RuleEvaluateRequest):
    actions = await rule_engine.evaluate(req.trigger_source, req.context)
    if not req.execute:
        return {"ok": True, "matched": len(actions), "actions": actions}
    results = await rule_engine.execute_actions(actions)
    return {"ok": True, "matched": len(actions), "results": results}
