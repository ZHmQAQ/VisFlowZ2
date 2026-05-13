from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.visflowz_check import validate_visflowz_workflow


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_CONFIG = ROOT / "visflowz-config-vmodule-2026-05-13.json"


def test_reference_vmodule_config_covers_reference_workflow():
    config = json.loads(REFERENCE_CONFIG.read_text(encoding="utf-8"))
    result = validate_visflowz_workflow(config)

    assert result["ok"] is True
    required_failures = [item for item in result["items"] if item["severity"] == "required" and not item["ok"]]
    assert required_failures == []


def test_missing_required_mapping_fails_check():
    config = json.loads(REFERENCE_CONFIG.read_text(encoding="utf-8"))
    config["io_mappings"] = [
        item for item in config["io_mappings"]
        if not (item.get("vmodule_addr") == "EW61" and item.get("plc_addr") == "D61")
    ]

    result = validate_visflowz_workflow(config)

    assert result["ok"] is False
    failed_keys = {item["key"] for item in result["items"] if not item["ok"]}
    assert "mapping:pos2_resp" in failed_keys


def test_wrong_ack_code_fails_required_check():
    config = json.loads(REFERENCE_CONFIG.read_text(encoding="utf-8"))
    pos2 = next(item for item in config["multiframe_channels"] if item["name"] == "pos2")
    pos2["frame_plan"][2]["status_code"] = 99

    result = validate_visflowz_workflow(config)

    assert result["ok"] is False
    failed = {item["key"]: item for item in result["items"] if not item["ok"]}
    assert "channel:pos2:ack" in failed


def test_failed_item_contains_actionable_advice():
    config = json.loads(REFERENCE_CONFIG.read_text(encoding="utf-8"))
    config["io_mappings"] = [
        item for item in config["io_mappings"]
        if not (item.get("vmodule_addr") == "EW63" and item.get("plc_addr") == "D63")
    ]

    result = validate_visflowz_workflow(config)

    failed = next(item for item in result["items"] if item["key"] == "mapping:pos3_resp")
    assert failed["ok"] is False
    assert "EW63" in failed["advice"]
    assert result["advice"]
