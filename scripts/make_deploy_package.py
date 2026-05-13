"""VModule 最小可部署包打包脚本.

目标:
    生成一个 zip,拷到上位机解压后,双击 setuplite.bat -> startlite.bat
    -> import_visflowz.bat 即可上线 visflowz 流程。

包内容:
    backend/app/**        - 后端代码
    backend/requirements.txt / run.py / pyinstaller.spec
    frontend/dist/**      - 前端构建产物 (dist-only 模式)
    presets/*.json        - 各种预设
    scripts/*.py          - preflight / import_visflowz / detect_path 三件套
    visflowz-config-vmodule-2026-05-13.json
    setuplite.bat / startlite.bat / preflight.bat / import_visflowz.bat
    detect_path.bat / load_preset.bat / setup.bat / start.bat
    LAUNCH_CHECKLIST.md / QUICKSTART.md / DEPLOY_README.md
    backend/data/{weights,logs,cycles,_diag}/  - 空目录占位

不打包:
    .venv / node_modules / .git / __pycache__ / *.pyc
    backend/data/vmodule.db (生产从空库启动)
    backend/data/config-runtime-*.json (调试快照)
    backend/data/_diag/* (诊断文件)
    backend/tests/ / frontend/src/ / frontend/node_modules/
    NO-GO 文件 (历史污染)

用法:
    python scripts/make_deploy_package.py
    python scripts/make_deploy_package.py --output D:\\share\\VModule-deploy.zip
    python scripts/make_deploy_package.py --tag prod-v1
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import zipfile
from pathlib import Path

# 在 Windows cmd (默认 GBK) 下也能正确打印中文
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


REPO = Path(__file__).resolve().parent.parent

# 白名单: 整目录拷贝 (相对 REPO)
INCLUDE_DIRS: list[tuple[str, list[str]]] = [
    # (源目录, 排除的子路径模式)
    ("backend/app", ["__pycache__", "*.pyc"]),
    ("frontend/dist", []),
    ("presets", []),
    ("scripts", ["__pycache__", "*.pyc"]),
]

# 白名单: 单文件拷贝
INCLUDE_FILES: list[str] = [
    "backend/requirements.txt",
    "backend/run.py",
    "backend/pyinstaller.spec",
    "visflowz-config-vmodule-2026-05-13.json",
    "setuplite.bat",
    "startlite.bat",
    "setup.bat",
    "start.bat",
    "preflight.bat",
    "import_visflowz.bat",
    "detect_path.bat",
    "load_preset.bat",
    "LAUNCH_CHECKLIST.md",
    "QUICKSTART.md",
]

# 部署后需要存在的空目录(setuplite 会再 mkdir 一次,但提前建好更稳)
EMPTY_DIRS: list[str] = [
    "backend/data",
    "backend/data/weights",
    "backend/data/logs",
    "backend/data/cycles",
    "backend/data/_diag",
    "backend/knowledge",
]


DEPLOY_README = """# VModule 最小可部署包

> 生成时间: {ts}
> 来源: {src}

## 适用场景

上位机首次安装,目标业务: visflowz pos2/pos3 (海康 DA8290609/709 + PLC 192.168.124.148)。

## 前置条件 (上位机)

- Windows 10/11
- Python 3.10+ 或已安装 Conda (二选一,setuplite 会自动检测)
- 可访问公网(走清华源 + npmmirror,设置内网代理也行)
- 若需要前端可视化训练:Node.js 18+(本包已带 dist,默认不需要)

## 部署步骤(全程双击,共 3 步)

1. **解压** 本 zip 到 `D:\\agentzone\\VModule` (或任意路径)。
2. **双击 setuplite.bat** 安装依赖。脚本会:
   - 检测 conda env (`envVModule` / `vmodule` / `envVisFlowZ` / `visf`),
     找到就复用,找不到就建 `envVModule` (Python 3.10)
   - 没有 conda 时退回 `.venv` 模式(需本机 Python 3.10+)
   - 走清华源装 backend/requirements.txt
   - 检测到 `frontend/dist/index.html`,跳过 npm build (本包已带 dist)
   - 在 `backend/data/` 下建 weights / logs / cycles 三个空目录
3. **双击 startlite.bat** 启动后端。浏览器自动打开 http://localhost:8100。
4. **(关键) 在另一窗口双击 import_visflowz.bat** 把 visflowz 配置导进去:
   - 自动备份当前(空)配置到 `backend/data/_diag/backup-<时间戳>.json`
   - 调 `/api/config/import` 灌入 `visflowz-config-vmodule-2026-05-13.json`
   - 自动跑业务自检,显示 `required 30/30 + warning 3/3` 才算成功
5. **双击 preflight.bat** 做最后健康检查。看到 `===> GO ...` 即可上线。

## 现场参数对齐

`visflowz-config-vmodule-2026-05-13.json` 内置参数:

- PLC: `192.168.124.148:502`
- 相机:
  - `pos2` 海康 SN `DA8290609` 4 帧 30000us 曝光
  - `pos3` 海康 SN `DA8290709` 1 帧 40000us 曝光
- 寄存器映射: D60/D62 命令, D61/D63 ACK, D200/D201 pos2 缺陷数+耗时, D210/D211 pos3 缺陷数+耗时
- 结果码: ok=7 / ng_repairable=6 / ng_fatal=5 / 错误=255

**若现场实际硬件参数不同**: 启动后在 UI 里改(相机管理页改 SN, PLC 连接页改 IP),
或编辑 `visflowz-config-vmodule-2026-05-13.json` 后再 `import_visflowz.bat`。

## 应急回滚

```
import_visflowz.bat --file backend\\data\\_diag\\backup-<时间戳>.json --skip-backup -y
```

## 工具速查

| 双击文件 | 用途 |
|---|---|
| `setuplite.bat` | 第一次安装依赖 |
| `startlite.bat` | 启动后端 |
| `import_visflowz.bat` | 切到 visflowz 配置 (带备份) |
| `preflight.bat` | 上线前健康检查 |
| `detect_path.bat` | 识别当前业务路径 |
| `load_preset.bat` | 加载其他 presets/ 里的预设(可选) |

## 已知坑位 (装机时可能遇到)

- **conda env 不存在且没装 conda**: setuplite 退回 .venv,确保系统装了 Python 3.10+
- **清华源拉不动**: 检查代理,或编辑 `setuplite.bat` 里 `pypi.tuna.tsinghua.edu.cn` 改成内网源
- **8100 端口被占**: 改 `backend/run.py` 里的 PORT,同步改 startlite.bat 里 URL
- **PLC 连不上**: ping 192.168.124.148,确认 502 端口放行 + 启用 Modbus TCP Slave
- **海康相机 SN 不匹配**: 在 UI 相机管理页把 SN 改成现场实际值

## 版本

- VModule v3.1.0
- 配置文件: visflowz-config-vmodule-2026-05-13.json (required 30/30 + warning 3/3 全绿)
- 打包时间: {ts}

详见: `LAUNCH_CHECKLIST.md`
"""


def should_skip(path: Path, patterns: list[str]) -> bool:
    """检查路径是否匹配排除模式"""
    name = path.name
    for pat in patterns:
        if pat == name:
            return True
        if pat.startswith("*.") and name.endswith(pat[1:]):
            return True
    return False


def copy_tree(src: Path, dst: Path, exclude: list[str]) -> int:
    """递归拷贝,带排除规则,返回文件数"""
    count = 0
    for item in src.rglob("*"):
        # 跳过排除项 (检查路径中的任意一段)
        if any(should_skip(p, exclude) for p in item.parents):
            continue
        if should_skip(item, exclude):
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="VModule 最小可部署包打包")
    parser.add_argument("--output", help="输出 zip 路径 (默认 dist/VModule-deploy-<ts>.zip)")
    parser.add_argument("--tag", help="附加到 zip 文件名的标签 (如 prod-v1)")
    parser.add_argument("--no-zip", action="store_true", help="只生成 staging 目录,不打 zip")
    args = parser.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    tag_part = f"-{args.tag}" if args.tag else ""
    stage_name = f"VModule-deploy-{ts}{tag_part}"
    out_root = REPO / "dist"
    out_root.mkdir(exist_ok=True)
    stage_dir = out_root / stage_name

    if stage_dir.exists():
        print(f"[INFO] 清理旧 staging 目录: {stage_dir}")
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    print(f"[INFO] Staging dir: {stage_dir}")
    total_files = 0

    # 1) 整目录拷贝
    for src_rel, exclude in INCLUDE_DIRS:
        src = REPO / src_rel
        if not src.exists():
            print(f"[WARN] 跳过不存在的目录: {src_rel}")
            continue
        dst = stage_dir / src_rel
        n = copy_tree(src, dst, exclude)
        size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())
        print(f"  + {src_rel}/   ({n} 个文件, {size/1024:.1f} KB)")
        total_files += n

    # 2) 单文件拷贝
    for src_rel in INCLUDE_FILES:
        src = REPO / src_rel
        if not src.exists():
            print(f"[WARN] 跳过不存在的文件: {src_rel}")
            continue
        dst = stage_dir / src_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        size = src.stat().st_size
        print(f"  + {src_rel}   ({size/1024:.1f} KB)")
        total_files += 1

    # 3) 建空目录(包含 .gitkeep 占位避免 zip 丢失)
    for d in EMPTY_DIRS:
        target = stage_dir / d
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitkeep").touch()

    # 4) 写部署 README
    readme_path = stage_dir / "DEPLOY_README.md"
    readme_path.write_text(
        DEPLOY_README.format(ts=ts, src=str(REPO)),
        encoding="utf-8",
    )
    print(f"  + DEPLOY_README.md   ({readme_path.stat().st_size/1024:.1f} KB)")
    total_files += 1

    # 5) 计算总大小
    total_size = sum(f.stat().st_size for f in stage_dir.rglob("*") if f.is_file())
    print()
    print(f"[OK] Staging 完成: {total_files} 个文件, {total_size/1024/1024:.2f} MB")

    # 6) 打 zip
    if args.no_zip:
        print(f"[INFO] --no-zip,跳过压缩。staging 路径: {stage_dir}")
        return 0

    zip_path = Path(args.output) if args.output else (out_root / f"{stage_name}.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 压缩到: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in stage_dir.rglob("*"):
            if f.is_file():
                arc = f.relative_to(stage_dir.parent)
                zf.write(f, arc)
    zip_size = zip_path.stat().st_size
    print(f"[OK] zip 完成: {zip_size/1024/1024:.2f} MB ({zip_size/total_size*100:.1f}% 压缩率)")
    print()
    print("=" * 70)
    print(f"  部署包就绪: {zip_path}")
    print("=" * 70)
    print("  上位机操作:")
    print("    1. 解压 zip 到目标目录")
    print("    2. 双击 setuplite.bat (装依赖)")
    print("    3. 双击 startlite.bat (启动后端,自动开浏览器)")
    print("    4. 双击 import_visflowz.bat (切到 visflowz 配置)")
    print("    5. 双击 preflight.bat (确认 GO)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
