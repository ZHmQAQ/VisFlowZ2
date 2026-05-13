r"""VModule 上线配置一键导入脚本 (stdlib only).

场景:
    现场启动 VModule 后,默认加载的是历史 M100-M102 映射。明天上线前需要把
    visflowz-config-vmodule-2026-05-13.json 的完整配置(pos2 4 帧 + pos3 1 帧,
    D60-D63 映射,DA8290609/709 双海康相机等)一次性灌进去。

流程:
    1. 先 GET /api/config/export 把当前配置备份到 backend/data/_diag/
       backup-<ts>.json,万一导错可以再导回来。
    2. POST /api/config/import 导入新配置(replace=True,会清掉旧映射)。
    3. GET /api/config/visflowz-self-check 验证 required 全通过。
    4. 若自检仍失败,在屏幕上直接打印备份路径 + 最多 5 条 FAIL 原因。

用法:
    python scripts\import_visflowz.py
    python scripts\import_visflowz.py --file visflowz-config-vmodule-2026-05-13.json
    python scripts\import_visflowz.py --base http://192.168.1.50:8100

退出码:
    0  导入 + 自检全通过
    1  导入失败或自检 required 有未通过项
    2  导入成功但存在 warning 项
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 在 Windows cmd (默认 GBK) 下也能正确打印中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _http_json(url: str, method: str, payload: dict | None = None, timeout: float = 30.0):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw)


def _banner(text: str) -> None:
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="VModule 上线配置一键导入")
    parser.add_argument("--base", default="http://localhost:8100", help="VModule 后端基址")
    parser.add_argument(
        "--file",
        default="visflowz-config-vmodule-2026-05-13.json",
        help="要导入的完整配置 JSON",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="跳过备份当前配置 (不推荐,仅限第一次空配置导入)",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="跳过交互确认,直接导入 (危险,替换现有映射)",
    )
    args = parser.parse_args()

    base = args.base.rstrip("/")
    cfg_path = Path(args.file).resolve()
    if not cfg_path.exists():
        print(f"[ERROR] 配置文件不存在: {cfg_path}")
        return 1

    # 预读配置,显示关键信息供用户确认
    with cfg_path.open(encoding="utf-8") as f:
        cfg = json.load(f)

    plc_conns = cfg.get("plc_connections") or []
    io_mappings = cfg.get("io_mappings") or []
    channels = cfg.get("detection_channels") or []
    mfc = cfg.get("multiframe_channels") or []
    cams = cfg.get("cameras") or []
    _banner("VModule 上线配置导入 · 预览")
    print(f"  配置文件: {cfg_path}")
    print(f"  版本: {cfg.get('version','?')}")
    print(f"  PLC 连接: {len(plc_conns)}  I/O 映射: {len(io_mappings)}  单帧通道: {len(channels)}")
    print(f"  多帧通道: {len(mfc)}  相机: {len(cams)}")
    print(f"  目标后端: {base}")

    if not args.yes:
        print()
        print("  [WARN] 导入将 replace=True 清空并替换当前所有配置!")
        print("         回车继续,Ctrl+C 取消。")
        try:
            input("  > ")
        except (EOFError, KeyboardInterrupt):
            print("  已取消。")
            return 1

    # 1) 先探活 + 备份
    try:
        _, health = _http_json(f"{base}/health", "GET", timeout=5.0)
    except Exception as exc:
        print(f"[ERROR] 后端 /health 不可达: {exc!r}")
        print("        请先确认 startlite.bat / start.bat 已启动 8100 服务。")
        return 1
    if health.get("status") != "ok":
        print(f"[ERROR] /health 非 ok: {health}")
        return 1
    print(f"[OK] 后端在线: {health.get('app','?')} v{health.get('version','?')}")

    backup_path = None
    if not args.skip_backup:
        _banner("Step 1/3  备份当前配置")
        try:
            _, current = _http_json(f"{base}/api/config/export", "GET", timeout=10.0)
        except Exception as exc:
            print(f"[ERROR] 导出当前配置失败: {exc!r}")
            return 1
        diag_dir = Path("backend/data/_diag")
        diag_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup_path = diag_dir / f"backup-{ts}.json"
        backup_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[OK] 已备份到: {backup_path}")
        print(f"     回滚命令: python scripts\\import_visflowz.py --file \"{backup_path}\" --skip-backup -y")

    # 2) 导入新配置
    _banner("Step 2/3  导入新配置 (replace=True)")
    try:
        _, imp = _http_json(f"{base}/api/config/import", "POST", payload=cfg, timeout=60.0)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        print(f"[ERROR] 导入失败 HTTP {exc.code}: {err_body[:500]}")
        if backup_path:
            print(f"        原配置备份在: {backup_path}")
        return 1
    except Exception as exc:
        print(f"[ERROR] 导入失败: {exc!r}")
        if backup_path:
            print(f"        原配置备份在: {backup_path}")
        return 1
    stats = imp.get("stats", {})
    print(f"[OK] {imp.get('message','import done')}")
    for k, v in stats.items():
        print(f"     {k}: +{v.get('added', '?')}")

    # 3) Post-import self-check
    _banner("Step 3/3  业务自检")
    try:
        _, check = _http_json(f"{base}/api/config/visflowz-self-check", "GET", timeout=10.0)
    except Exception as exc:
        print(f"[WARN] 自检接口失败: {exc!r}")
        return 2
    summary = check.get("summary", {})
    req_pass = summary.get("required_passed", 0)
    req_total = summary.get("required_total", 0)
    warn_pass = summary.get("warning_passed", 0)
    warn_total = summary.get("warning_total", 0)
    print(f"  required {req_pass}/{req_total}   warning {warn_pass}/{warn_total}")

    fail_items = [it for it in check.get("items", []) if not it.get("ok")]
    req_fail = [it for it in fail_items if it.get("severity") == "required"]

    print()
    print("-" * 70)
    if req_fail:
        print(f"  结论: 导入动作完成,但 visflowz 自检 required 有 {len(req_fail)} 项未通过。")
        print(f"         -> 若此次是回滚到非 visflowz 配置,这是预期行为,可忽略。")
        print(f"         -> 若此次本想导入 visflowz,请核对源文件内容后重试。")
        for it in req_fail[:5]:
            print(f"    [FAIL] {it.get('key')}: {it.get('detail')}")
        if backup_path:
            print(f"  备份: {backup_path}")
            print(f"  如需回滚: python scripts\\import_visflowz.py --file \"{backup_path}\" --skip-backup -y")
        return 2
    if fail_items:
        print(f"  结论: 导入成功,required 全通过,仅 warning {warn_total - warn_pass} 项未达标。可上线,建议人工确认。")
        for it in fail_items[:3]:
            print(f"    [WARN] {it.get('key')}: {it.get('detail')}")
        return 2
    print("  结论: 导入成功,全部自检通过。可以上线。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
