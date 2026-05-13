r"""VModule 业务路径识别 (stdlib only).

根据当前 /api/config/export 的配置内容,识别当前系统属于哪条业务路径:
  A - visflowz pos2/pos3 (海康 DA8290609/709, D60-D63 映射, PLC 192.168.124.148)
  B - 大恒多曝光检测 (6 通道 Cam1/Cam2-Exp1/2/3, M100-M102/M110-M112)
  C - 海康检测 (其他海康预设)
  D - USB 基线 (usb:0 单相机)
  ? - 自定义/未识别

用法:
    python scripts\detect_path.py
    python scripts\detect_path.py --base http://192.168.1.50:8100
    python scripts\detect_path.py --file backup.json

退出码:
    0  识别出有效路径
    1  无法联通或解析
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

# 在 Windows cmd (默认 GBK) 下也能正确打印中文/符号
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _http_get_json(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def identify(cfg: dict) -> tuple[str, str, list[str]]:
    plcs = cfg.get("plc_connections") or []
    io = cfg.get("io_mappings") or []
    chs = cfg.get("detection_channels") or []
    mfc = cfg.get("multiframe_channels") or []
    cams = cfg.get("cameras") or []

    plc_hosts = [f"{p.get('host')}:{p.get('port')}" for p in plcs]
    plc_addrs = {m.get("plc_addr") for m in io}
    vm_addrs = {m.get("vmodule_addr") for m in io}
    ch_names = {(ch.get("name") or "").lower() for ch in chs}
    mfc_names = {(mf.get("name") or "").lower() for mf in mfc}
    cam_types = {c.get("camera_type") for c in cams}
    cam_serials = {str(c.get("config", {}).get("serial_number", "")).upper() for c in cams}

    details = [
        f"PLC: {', '.join(plc_hosts) or '(none)'}",
        f"I/O mappings: {len(io)}  detection channels: {len(chs)}  multiframe: {len(mfc)}  cameras: {len(cams)}",
        f"camera types: {', '.join(sorted(t for t in cam_types if t)) or '(none)'}",
    ]

    # Path A: visflowz pos2/pos3
    if {"pos2", "pos3"}.issubset(mfc_names) and {"ED60", "ED62"}.issubset(vm_addrs):
        extra = []
        if any("192.168.124.148" in h for h in plc_hosts):
            extra.append("PLC IP 匹配 visflowz (192.168.124.148)")
        if any(sn in {"DA8290609", "DA8290709"} for sn in cam_serials):
            extra.append("海康 DA8290609/709 已配置")
        return (
            "A",
            "visflowz pos2/pos3 多帧业务路径",
            details + extra,
        )

    # Path B: Daheng multi-exposure (6 单帧通道 Cam1/Cam2 x Exp1/2/3)
    if "daheng" in cam_types and any("exp" in n for n in ch_names) and {"M100", "M101", "M102"}.issubset(plc_addrs):
        extra = []
        placeholder = any("CHANGE_ME" in sn for sn in cam_serials)
        if placeholder:
            extra.append("[!] 相机 SN 为 CHANGE_ME 占位符,未绑定真实硬件(种子模板状态)")
        return (
            "B",
            "大恒多曝光检测路径 (Cam1/Cam2 x Exp1/2/3)",
            details + extra,
        )

    # Path C: Hikvision inspection (non-visflowz)
    if "hikvision" in cam_types and not ({"pos2", "pos3"}.issubset(mfc_names)):
        return (
            "C",
            "海康检测路径 (非 visflowz)",
            details,
        )

    # Path D: USB baseline
    if cam_types == {"usb"} and len(cams) == 1:
        return (
            "D",
            "USB 基线单相机路径",
            details,
        )

    return (
        "?",
        "自定义 / 未识别配置",
        details,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="VModule 业务路径识别")
    parser.add_argument("--base", default="http://localhost:8100", help="VModule 后端基址")
    parser.add_argument("--file", help="从本地 JSON 文件识别(跳过 HTTP)")
    args = parser.parse_args()

    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[ERROR] 文件不存在: {p}")
            return 1
        cfg = json.loads(p.read_text(encoding="utf-8"))
        source = str(p)
    else:
        base = args.base.rstrip("/")
        try:
            cfg = _http_get_json(f"{base}/api/config/export", timeout=10.0)
        except Exception as exc:
            print(f"[ERROR] 无法读取 {base}/api/config/export : {exc!r}")
            return 1
        source = f"{base}/api/config/export"

    code, label, details = identify(cfg)
    print("=" * 70)
    print(f"  VModule 路径识别: {code}  -  {label}")
    print("=" * 70)
    print(f"  来源: {source}")
    for line in details:
        print(f"    {line}")
    print()
    # 针对每条路径给出"现场该做什么"提示
    hints = {
        "A": [
            "现场核对: PLC IP = 192.168.124.148  相机 SN = DA8290609 / DA8290709",
            "若业务目标是 visflowz,当前配置已匹配,直接 preflight.bat --visflowz",
        ],
        "B": [
            "现场核对: PLC IP 是否为实际设备 IP  相机 SN 是否已替换 CHANGE_ME 占位符",
            "若相机 SN 仍为占位符,必须在相机管理页改成真实 SN 再打开",
            "若业务目标是 visflowz,需要先导入 visflowz-config-vmodule-2026-05-13.json",
        ],
        "C": [
            "海康检测路径,按该路径的验收清单走",
            "若业务目标是 visflowz,需要先导入 visflowz-config-vmodule-2026-05-13.json",
        ],
        "D": [
            "USB 单相机基线,适合开发调试,不建议直接上线",
            "实际上线应导入对应业务的完整配置预设",
        ],
        "?": [
            "未识别的自定义配置,请人工确认后再决定是否上线",
            "可对比 visflowz-config-vmodule-2026-05-13.json 的参考结构",
        ],
    }
    print("  建议:")
    for h in hints[code]:
        print(f"    - {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
