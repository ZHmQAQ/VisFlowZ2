"""VisFlowZ workflow coverage checks for VModule runtime configs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


EXPECTED = {
    "mappings": {
        "pos2_cmd": ("ED60", "D60"),
        "pos2_resp": ("EW61", "D61"),
        "pos3_cmd": ("ED62", "D62"),
        "pos3_resp": ("EW63", "D63"),
    },
    "channels": {
        "pos2": {
            "cmd_addr": "ED60",
            "status_addr": "EW61",
            "result_addr": "EW61",
            "count_addr": "EW0",
            "time_addr": "EW1",
            "commands": [1, 2, 3, 4],
            "ack_codes": [17, 18, 19, 20],
            "exposures": [30000, 30000, 30000, 30000],
        },
        "pos3": {
            "cmd_addr": "ED62",
            "status_addr": "EW63",
            "result_addr": "EW63",
            "count_addr": "EW10",
            "time_addr": "EW11",
            "commands": [1],
            "ack_codes": [17],
            "exposures": [40000],
        },
    },
    "cameras": {
        "pos2": {"camera_type": "hikvision", "serial_number": "DA8290609"},
        "pos3": {"camera_type": "hikvision", "serial_number": "DA8290709"},
    },
    "result_codes": {"ok": 7, "ng_repairable": 6, "ng_fatal": 5},
    "error_code": 255,
    "defect_priority": ["NG", "HP_NG", "QJ_NG", "RJ_NG", "LX_NG"],
    "defect_code_map": {
        "NG": "ng_fatal",
        "HP_NG": "ng_repairable",
        "QJ_NG": "ng_repairable",
        "RJ_NG": "ng_repairable",
        "LX_NG": "ng_repairable",
    },
}


def validate_visflowz_workflow(config: dict[str, Any]) -> dict[str, Any]:
    """Validate whether a VModule config covers the reference VisFlowZ flow."""

    items: list[dict[str, Any]] = []
    _check_mappings(config, items)
    _check_channels(config, items)
    _check_cameras(config, items)
    _check_actions(config, items)
    _check_rules(config, items)
    _check_strategy(config, items)

    required = [item for item in items if item["severity"] == "required"]
    warnings = [item for item in items if item["severity"] == "warning"]
    return {
        "ok": all(item["ok"] for item in required),
        "items": items,
        "advice": [item["advice"] for item in items if (not item["ok"]) and item.get("advice")],
        "summary": {
            "required_passed": sum(1 for item in required if item["ok"]),
            "required_total": len(required),
            "warning_passed": sum(1 for item in warnings if item["ok"]),
            "warning_total": len(warnings),
        },
        "expected": deepcopy(EXPECTED),
    }


def _item(
    items: list[dict[str, Any]],
    key: str,
    label: str,
    ok: bool,
    detail: str,
    *,
    expected: Any = None,
    actual: Any = None,
    severity: str = "required",
    advice: str = "",
) -> None:
    items.append({
        "key": key,
        "label": label,
        "ok": bool(ok),
        "detail": detail,
        "expected": expected,
        "actual": actual,
        "severity": severity,
        "advice": advice,
    })


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _enabled(item: dict[str, Any]) -> bool:
    return item.get("enabled", True) is not False


def _mapping_pairs(config: dict[str, Any]) -> set[tuple[str, str]]:
    pairs = set()
    for item in config.get("io_mappings") or []:
        if _enabled(item):
            pairs.add((str(item.get("vmodule_addr") or ""), str(item.get("plc_addr") or "")))
    return pairs


def _channels(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in config.get("multiframe_channels") or []:
        name = str(item.get("name") or item.get("camera_id") or "")
        camera_id = str(item.get("camera_id") or "")
        if name:
            result[name] = item
        if camera_id:
            result[camera_id] = item
    return result


def _cameras(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("camera_id") or ""): item
        for item in config.get("cameras") or []
        if item.get("camera_id")
    }


def _frame_plan(channel: dict[str, Any]) -> list[dict[str, Any]]:
    plan = channel.get("frame_plan")
    if isinstance(plan, list) and plan:
        return plan
    count = _as_int(channel.get("frame_count")) or 1
    return [{"command": index + 1, "status_code": 17 + index} for index in range(count)]


def _policy(channel: dict[str, Any]) -> dict[str, Any]:
    return channel.get("result_policy") or {}


def _result_codes(channel: dict[str, Any]) -> dict[str, Any]:
    return _policy(channel).get("result_codes") or {}


def _check_mappings(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    pairs = _mapping_pairs(config)
    for key, pair in EXPECTED["mappings"].items():
        vmodule_addr, plc_addr = pair
        _item(
            items,
            f"mapping:{key}",
            f"{key} I/O mapping",
            pair in pairs,
            f"{plc_addr} <-> {vmodule_addr}",
            expected={"plc_addr": plc_addr, "vmodule_addr": vmodule_addr},
            actual=sorted(pairs),
            advice=f"\u5728 I/O \u6620\u5c04\u4e2d\u8865\u5145 {plc_addr} <-> {vmodule_addr}",
        )


def _check_channels(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    channels = _channels(config)
    for name, expected in EXPECTED["channels"].items():
        ch = channels.get(name)
        _item(
            items,
            f"channel:{name}:exists",
            f"{name} multi-frame channel",
            bool(ch),
            "channel exists",
            expected=name,
            actual=sorted(channels),
            advice=f"\u65b0\u589e\u591a\u5e27\u901a\u9053 {name}",
        )
        if not ch:
            continue

        for field in ["cmd_addr", "status_addr", "result_addr", "count_addr", "time_addr"]:
            _item(
                items,
                f"channel:{name}:{field}",
                f"{name} {field}",
                ch.get(field) == expected[field],
                f"{field} = {expected[field]}",
                expected=expected[field],
                actual=ch.get(field),
                advice=f"\u5c06 {name} \u7684 {field} \u8bbe\u4e3a {expected[field]}",
            )

        plan = _frame_plan(ch)
        commands = [_as_int(frame.get("command")) for frame in plan]
        ack_codes = [_as_int(frame.get("status_code")) for frame in plan]
        exposures = [_as_int(frame.get("exposure")) for frame in plan]
        _item(
            items,
            f"channel:{name}:commands",
            f"{name} frame commands",
            commands == expected["commands"],
            ", ".join(str(v) for v in expected["commands"]),
            expected=expected["commands"],
            actual=commands,
            advice=f"\u5c06 {name} \u7684 frame_plan.command \u6539\u4e3a {expected['commands']}",
        )
        _item(
            items,
            f"channel:{name}:ack",
            f"{name} ACK codes",
            ack_codes == expected["ack_codes"],
            ", ".join(str(v) for v in expected["ack_codes"]),
            expected=expected["ack_codes"],
            actual=ack_codes,
            advice=f"\u5c06 {name} \u7684 ACK \u7801\u6539\u4e3a {expected['ack_codes']}",
        )
        _item(
            items,
            f"channel:{name}:exposure",
            f"{name} exposures",
            exposures == expected["exposures"],
            ", ".join(str(v) for v in expected["exposures"]),
            expected=expected["exposures"],
            actual=exposures,
            severity="warning",
            advice=f"\u5c06 {name} \u7684 exposure \u8c03\u6574\u4e3a {expected['exposures']}",
        )

        codes = _result_codes(ch)
        codes_ok = all(_as_int(codes.get(k)) == v for k, v in EXPECTED["result_codes"].items())
        error_ok = _as_int(_policy(ch).get("error_code")) == EXPECTED["error_code"]
        _item(
            items,
            f"channel:{name}:result_codes",
            f"{name} result codes",
            codes_ok and error_ok,
            "OK=7 / repairable=6 / fatal=5 / error=255",
            expected={**EXPECTED["result_codes"], "error_code": EXPECTED["error_code"]},
            actual={**codes, "error_code": _policy(ch).get("error_code")},
            advice=f"\u5c06 {name} \u7684 result_codes/error_code \u8bbe\u4e3a 7/6/5/255",
        )

        policy = _policy(ch)
        priority = policy.get("defect_priority") or []
        code_map = policy.get("defect_code_map") or {}
        _item(
            items,
            f"channel:{name}:defects",
            f"{name} defect classification",
            priority == EXPECTED["defect_priority"] and all(
                code_map.get(k) == v for k, v in EXPECTED["defect_code_map"].items()
            ),
            "NG fatal; HP/QJ/RJ/LX repairable",
            expected={
                "defect_priority": EXPECTED["defect_priority"],
                "defect_code_map": EXPECTED["defect_code_map"],
            },
            actual={"defect_priority": priority, "defect_code_map": code_map},
            advice=f"\u5c06 {name} \u7684 defect_priority \u548c defect_code_map \u5bf9\u9f50\u53c2\u8003\u6d41\u7a0b",
        )


def _check_cameras(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    cameras = _cameras(config)
    for camera_id, expected in EXPECTED["cameras"].items():
        cam = cameras.get(camera_id) or {}
        connection = (cam.get("config") or {}).get("connection") or {}
        ok = (
            cam.get("camera_type") == expected["camera_type"]
            and connection.get("serial_number") == expected["serial_number"]
        )
        _item(
            items,
            f"camera:{camera_id}",
            f"{camera_id} Hikvision camera",
            ok,
            f"{expected['camera_type']} / {expected['serial_number']}",
            expected=expected,
            actual={
                "camera_type": cam.get("camera_type"),
                "serial_number": connection.get("serial_number"),
            },
            advice=f"\u5c06 {camera_id} \u76f8\u673a\u914d\u6210 {expected['camera_type']} / SN {expected['serial_number']}",
        )


def _check_actions(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    actions = [item for item in (config.get("event_actions") or []) if _enabled(item)]
    for source in ["pos2", "pos3"]:
        value_types = {
            (item.get("action_params") or {}).get("value_type")
            for item in actions
            if item.get("event_source") == source and item.get("action_type") == "write_register"
        }
        _item(
            items,
            f"event_actions:{source}",
            f"{source} ACK/error/result actions",
            {"ack", "fixed", "result"} <= value_types,
            "write_register actions for ack, fixed error, result",
            expected=["ack", "fixed", "result"],
            actual=sorted(v for v in value_types if v),
            advice=f"\u4e3a {source} \u8865\u9f50 ack\u3001fixed(error)\u3001result \u4e09\u7c7b write_register \u4e8b\u4ef6\u52a8\u4f5c",
        )


def _check_rules(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    rules = [item for item in (config.get("rules") or []) if _enabled(item)]
    for source in ["pos2.capture_done", "pos3.capture_done"]:
        matching = [item for item in rules if item.get("trigger_source") == source]
        ok = False
        actual: list[list[str]] = []
        for rule in matching:
            action_types = [action.get("type") for action in rule.get("actions") or []]
            actual.append(action_types)
            conditions = rule.get("conditions") or []
            has_ng_condition = any(
                cond.get("field") == "is_ok"
                and cond.get("operator", "==") == "=="
                and cond.get("value") is False
                for cond in conditions
            )
            if has_ng_condition and {"save_image", "trigger_alarm"} <= set(action_types):
                ok = True
        _item(
            items,
            f"rules:{source}",
            f"{source} NG save/alarm rule",
            ok,
            "is_ok=false -> save_image + trigger_alarm",
            expected=["save_image", "trigger_alarm"],
            actual=actual,
            advice=f"\u4e3a {source} \u589e\u52a0 is_ok=false \u65f6 save_image + trigger_alarm \u89c4\u5219",
        )


def _check_strategy(config: dict[str, Any], items: list[dict[str, Any]]) -> None:
    strategy = (config.get("strategy") or {}).get("strategy_map") or {}
    trigger_map = strategy.get("trigger_camera_map") or {}
    protocol = strategy.get("vmodule_protocol_mapping") or {}
    ok = (
        trigger_map.get("0x3C") == "pos2"
        and trigger_map.get("0x3E") == "pos3"
        and _as_int(strategy.get("ack_base")) == 16
        and _as_int(strategy.get("error_code")) == 255
        and _as_int(strategy.get("response_offset")) == 1
        and (protocol.get("pos2") or {}).get("cmd_addr") == "ED60"
        and (protocol.get("pos2") or {}).get("status_addr") == "EW61"
        and (protocol.get("pos3") or {}).get("cmd_addr") == "ED62"
        and (protocol.get("pos3") or {}).get("status_addr") == "EW63"
    )
    _item(
        items,
        "strategy:protocol",
        "strategy protocol hints",
        ok,
        "0x3C/0x3E trigger map and +1 response offset",
        expected={
            "trigger_camera_map": {"0x3C": "pos2", "0x3E": "pos3"},
            "ack_base": 16,
            "error_code": 255,
            "response_offset": 1,
        },
        actual=strategy,
        severity="warning",
        advice="\u5c06 strategy_map \u4e2d\u7684 trigger_camera_map\u3001ack_base\u3001error_code\u3001response_offset \u5bf9\u9f50\u53c2\u8003\u6d41\u7a0b",
    )
