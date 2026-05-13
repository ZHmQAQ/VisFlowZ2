r"""VModule 上线前一键预检脚本 (stdlib only).

用法:
    python scripts\preflight.py                  # 默认连本机 8100
    python scripts\preflight.py --base http://192.168.1.50:8100
    python scripts\preflight.py --visflowz       # 强制要求 visflowz 业务自检通过
    python scripts\preflight.py --check-plc      # 强制要求至少一条 PLC 已连接
    python scripts\preflight.py --check-cameras  # 强制要求所有相机 opened

退出码:
    0  全部通过 (GO)
    1  存在 NO-GO 项 (硬性失败,不要上线)
    2  存在 WARN 项但无 NO-GO (谨慎评估)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# 在 Windows cmd (默认 GBK) 下也能正确打印中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _http_get(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body


def _http_get_json(url: str, timeout: float = 5.0):
    status, body = _http_get(url, timeout=timeout)
    return status, json.loads(body)


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []  # (level, label, detail)

    def go(self, label: str, detail: str = "") -> None:
        self.items.append(("GO", label, detail))

    def warn(self, label: str, detail: str = "") -> None:
        self.items.append(("WARN", label, detail))

    def nogo(self, label: str, detail: str = "") -> None:
        self.items.append(("NO-GO", label, detail))

    def render(self) -> int:
        nogo = sum(1 for level, *_ in self.items if level == "NO-GO")
        warn = sum(1 for level, *_ in self.items if level == "WARN")
        go = sum(1 for level, *_ in self.items if level == "GO")
        print()
        print("=" * 70)
        print(f"  VModule 上线预检报告  GO={go}  WARN={warn}  NO-GO={nogo}")
        print("=" * 70)
        for level, label, detail in self.items:
            tag = {"GO": "[ OK ]", "WARN": "[WARN]", "NO-GO": "[FAIL]"}[level]
            print(f"  {tag}  {label}")
            if detail:
                for line in detail.splitlines():
                    print(f"           {line}")
        print("-" * 70)
        if nogo:
            print(f"  结论: NO-GO ({nogo} 个硬性失败)。不要上线。请先修复以上 [FAIL] 项。")
            return 1
        if warn:
            print(f"  结论: GO 但有 {warn} 项 WARN。请人工评估再决定是否上线。")
            return 2
        print("  结论: GO。所有预检通过。")
        return 0


def check_health(base: str, rep: Report) -> dict:
    try:
        status, data = _http_get_json(f"{base}/health", timeout=3.0)
    except Exception as exc:
        rep.nogo("后端 /health 不可达", f"URL: {base}/health\n错误: {exc!r}\n建议: 确认 startlite.bat 已启动且端口未被占用")
        return {}
    if status != 200:
        rep.nogo(f"/health HTTP {status}", "期望 200")
        return {}
    if data.get("status") != "ok":
        rep.nogo("/health status 非 ok", json.dumps(data, ensure_ascii=False))
        return {}
    rep.go(
        f"后端服务: {data.get('app','?')} v{data.get('version','?')} (Python {data.get('python','?')})",
        f"URL: {base}",
    )
    return data


def check_engine(base: str, rep: Report) -> dict:
    try:
        _, data = _http_get_json(f"{base}/api/plc/engine/status", timeout=3.0)
    except Exception as exc:
        rep.nogo("引擎状态接口失败", repr(exc))
        return {}
    if not data.get("running"):
        rep.nogo("扫描引擎未运行", json.dumps(data, ensure_ascii=False))
        return data
    cycle = data.get("last_scan_ms")
    target = data.get("target_cycle_ms")
    rep.go(
        f"扫描引擎: 运行中  扫描周期 {cycle}ms / 目标 {target}ms  累计 {data.get('scan_count')} 次",
        f"已映射 I/O: {data.get('io_mappings')} 条  程序块: {data.get('program_blocks')}",
    )
    return data


def check_plcs(base: str, rep: Report, *, strict: bool) -> None:
    try:
        _, data = _http_get_json(f"{base}/api/plc/connections", timeout=3.0)
    except Exception as exc:
        rep.nogo("PLC 列表读取失败", repr(exc))
        return
    # 兼容两种返回形态: {"PLC1": {...}, ...} (dict) 或 [{...}, ...] (list)
    if isinstance(data, dict):
        plcs = [{"name": k, **(v if isinstance(v, dict) else {})} for k, v in data.items()]
    elif isinstance(data, list):
        plcs = data
    else:
        plcs = []
    if not plcs:
        if strict:
            rep.nogo("没有配置 PLC 连接", "建议: 先导入预设或在 PLC 连接页添加")
        else:
            rep.warn("没有配置 PLC 连接", "若现场需要 PLC 联机,请先导入预设")
        return
    for plc in plcs:
        name = plc.get("name", "?")
        host = f"{plc.get('host')}:{plc.get('port')}"
        connected = bool(plc.get("connected"))
        if connected:
            rep.go(f"PLC {name} 已连接", host)
        else:
            level = rep.nogo if strict else rep.warn
            level(
                f"PLC {name} 未连接",
                f"目标: {host}\n建议: ping 该地址,确认 502 端口放行 + Modbus TCP Slave 已启用",
            )


def check_cameras(base: str, rep: Report, *, strict: bool) -> None:
    try:
        _, data = _http_get_json(f"{base}/api/camera/list", timeout=3.0)
    except Exception as exc:
        rep.warn("相机列表读取失败", repr(exc))
        return
    cams = data if isinstance(data, list) else data.get("cameras") or []
    if not cams:
        if strict:
            rep.nogo("没有配置相机", "建议: 先导入预设或在相机管理页添加")
        else:
            rep.warn("没有配置相机", "")
        return
    for cam in cams:
        cid = cam.get("camera_id", "?")
        ctype = cam.get("camera_type", "?")
        opened = bool(cam.get("opened") or cam.get("is_opened") or cam.get("is_open"))
        if opened:
            rep.go(f"相机 {cid} ({ctype}) 已打开", "")
        else:
            level = rep.nogo if strict else rep.warn
            level(
                f"相机 {cid} ({ctype}) 未打开",
                "建议: 在相机管理页点击 打开,或检查 SN/USB index/驱动",
            )


def check_visflowz(base: str, rep: Report, *, strict: bool) -> None:
    try:
        _, data = _http_get_json(f"{base}/api/config/visflowz-self-check", timeout=5.0)
    except Exception as exc:
        rep.warn("业务自检接口失败", repr(exc))
        return
    summary = data.get("summary", {})
    req_pass = summary.get("required_passed", 0)
    req_total = summary.get("required_total", 0)
    warn_pass = summary.get("warning_passed", 0)
    warn_total = summary.get("warning_total", 0)
    if data.get("ok") and req_pass == req_total:
        rep.go(
            f"VisFlowZ 业务自检通过  required {req_pass}/{req_total}  warning {warn_pass}/{warn_total}",
            "",
        )
        return
    level = rep.nogo if strict else rep.warn
    failing = [it for it in data.get("items", []) if not it.get("ok")]
    detail_lines = [
        f"required {req_pass}/{req_total}  warning {warn_pass}/{warn_total}",
        f"未通过 {len(failing)} 项 (前 5 条):",
    ]
    for it in failing[:5]:
        detail_lines.append(f"- [{it.get('severity')}] {it.get('key')}: {it.get('detail')}")
    detail_lines.append("建议: 系统设置 -> 导入完整配置 visflowz-config-vmodule-2026-05-13.json")
    level("VisFlowZ 业务自检未通过", "\n".join(detail_lines))


def check_gpu(base: str, rep: Report) -> None:
    try:
        _, data = _http_get_json(f"{base}/api/gpu", timeout=3.0)
    except Exception:
        rep.warn("GPU 状态接口未响应", "")
        return
    if data.get("available"):
        gpus = data.get("gpus") or data.get("devices") or []
        if isinstance(gpus, list) and gpus:
            names = ", ".join(
                (g.get("name") if isinstance(g, dict) else str(g)) for g in gpus
            )
        else:
            names = str(data.get("gpu_name") or "?")
        rep.go(f"GPU 可用: {names}", "")
    else:
        rep.warn("GPU 不可用,将走 CPU 推理", "若现场期望 GPU,请检查 CUDA / torch 安装")


def check_models(base: str, rep: Report) -> None:
    try:
        _, data = _http_get_json(f"{base}/api/model/list", timeout=3.0)
    except Exception as exc:
        rep.warn("模型列表读取失败", repr(exc))
        return
    models = data if isinstance(data, list) else data.get("models") or []
    if not models:
        rep.warn("没有已加载的模型", "建议: 模型管理页上传或加载模型,确认权重在 backend/data/weights/")
        return
    rep.go(f"已加载模型: {len(models)} 个", ", ".join(str(m.get("model_id") or m.get("id") or "?") for m in models))


def main() -> int:
    parser = argparse.ArgumentParser(description="VModule 上线前一键预检")
    parser.add_argument("--base", default="http://localhost:8100", help="VModule 后端基址")
    parser.add_argument("--visflowz", action="store_true", help="强制要求 visflowz 业务自检通过")
    parser.add_argument("--check-plc", action="store_true", help="强制要求至少一条 PLC 已连接")
    parser.add_argument("--check-cameras", action="store_true", help="强制要求所有已配置相机均已打开")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    rep = Report()
    print(f"[preflight] base={base}  ts={time.strftime('%Y-%m-%d %H:%M:%S')}")

    health = check_health(base, rep)
    if not health:
        return rep.render()

    check_engine(base, rep)
    check_plcs(base, rep, strict=args.check_plc)
    check_cameras(base, rep, strict=args.check_cameras)
    check_models(base, rep)
    check_gpu(base, rep)
    check_visflowz(base, rep, strict=args.visflowz)

    return rep.render()


if __name__ == "__main__":
    sys.exit(main())
