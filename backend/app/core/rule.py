"""Lightweight rules engine."""
from __future__ import annotations

import asyncio
import json
import operator
from typing import Any, Awaitable, Callable

from app.utils.logger import logger

ActionHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


class RuleEngine:
    OPERATORS = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "in": lambda actual, expected: actual in expected,
        "not_in": lambda actual, expected: actual not in expected,
        "contains": lambda actual, expected: expected in actual,
    }

    def __init__(self):
        self._rules: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, ActionHandler] = {}
        self._lock = asyncio.Lock()
        self.register_action("send_command", self._send_command)
        self.register_action("log", self._log_action)
        self.register_action("save_image", self._dry_run_action)
        self.register_action("trigger_alarm", self._dry_run_action)

    def register_action(self, action_type: str, handler: ActionHandler) -> None:
        self._handlers[action_type] = handler

    async def set_rules(self, rules: list[dict[str, Any]]) -> None:
        normalized = [self._normalize(rule) for rule in rules]
        async with self._lock:
            self._rules = {rule["rule_id"]: rule for rule in normalized}

    async def add_rule(self, rule: dict[str, Any]) -> None:
        item = self._normalize(rule)
        async with self._lock:
            if item["rule_id"] in self._rules:
                raise ValueError(f"Rule [{item['rule_id']}] already exists")
            self._rules[item["rule_id"]] = item

    async def update_rule(self, rule_id: str, updates: dict[str, Any]) -> bool:
        async with self._lock:
            current = self._rules.get(rule_id)
            if not current:
                return False
            self._rules[rule_id] = self._normalize({**current, **updates, "rule_id": rule_id})
            return True

    async def remove_rule(self, rule_id: str) -> bool:
        async with self._lock:
            return self._rules.pop(rule_id, None) is not None

    async def clear(self) -> None:
        async with self._lock:
            self._rules.clear()

    def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        rule = self._rules.get(rule_id)
        return dict(rule) if rule else None

    def get_all_rules(self) -> list[dict[str, Any]]:
        return sorted([dict(rule) for rule in self._rules.values()], key=lambda r: r.get("priority", 0), reverse=True)

    async def evaluate(self, trigger_source: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        matches = []
        for rule in self.get_all_rules():
            if not rule.get("enabled", True):
                continue
            source = rule.get("trigger_source") or "*"
            if source not in {"*", trigger_source}:
                continue
            if all(self._check_condition(condition, context) for condition in rule.get("conditions", [])):
                for action in rule.get("actions", []):
                    matches.append({"rule_id": rule["rule_id"], "action": action, "context": context})
        return matches

    async def execute_actions(self, action_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for item in action_items:
            action = item.get("action") or {}
            action_type = action.get("type", "log")
            handler = self._handlers.get(action_type, self._dry_run_action)
            try:
                result = await handler(action, item.get("context") or {})
                results.append({
                    "rule_id": item.get("rule_id"),
                    "action_type": action_type,
                    "success": result.get("success", True),
                    "result": result,
                })
            except Exception as exc:
                logger.exception("Rule action failed: %s", action_type)
                results.append({
                    "rule_id": item.get("rule_id"),
                    "action_type": action_type,
                    "success": False,
                    "error": str(exc),
                })
        return results

    async def evaluate_and_execute(self, trigger_source: str, context: dict[str, Any]) -> dict[str, Any]:
        actions = await self.evaluate(trigger_source, context)
        results = await self.execute_actions(actions)
        return {"matched": len(actions), "results": results}

    def _check_condition(self, condition: dict[str, Any], context: dict[str, Any]) -> bool:
        field = condition.get("field", "")
        op = condition.get("operator", "==")
        actual = self._get_nested_value(context, field)
        expected = self._coerce_value(condition.get("value"))
        op_func = self.OPERATORS.get(op)
        if not op_func:
            return False
        try:
            return bool(op_func(actual, expected))
        except Exception:
            return False

    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for key in path.split("."):
            if not key:
                continue
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value

    def _coerce_value(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.lower() == "true":
            return True
        if text.lower() == "false":
            return False
        try:
            return json.loads(text)
        except Exception:
            pass
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return value

    def _normalize(self, rule: dict[str, Any]) -> dict[str, Any]:
        rule_id = str(rule.get("rule_id") or "").strip()
        if not rule_id:
            raise ValueError("rule_id is required")
        return {
            "rule_id": rule_id,
            "name": rule.get("name") or rule_id,
            "description": rule.get("description") or "",
            "trigger_source": rule.get("trigger_source") or "*",
            "conditions": rule.get("conditions") or [],
            "actions": rule.get("actions") or [],
            "priority": int(rule.get("priority") or 0),
            "enabled": rule.get("enabled", True) is not False,
        }

    async def _send_command(self, action: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        from app.core.device.manager import device_manager

        target = action.get("target") or ""
        params = action.get("params") or {}
        data = params.get("data") or action.get("data") or ""
        if not target:
            return await self._dry_run_action(action, context)
        ok = await device_manager.send_hex(target, data)
        return {"success": ok, "target": target, "sent": data}

    async def _log_action(self, action: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        logger.info("Rule action log: %s context=%s", action, context)
        return {"success": True, "message": (action.get("params") or {}).get("data", "")}

    async def _dry_run_action(self, action: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "dry_run": True, "action": action, "context": context}


rule_engine = RuleEngine()
