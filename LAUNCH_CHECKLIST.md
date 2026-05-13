# VModule 上线现场操作清单 (2026-05-13)

> 目标: 明天现场双击几个 bat 就能完成"预检 -> 路径识别 -> 切配置 -> 验证"全流程。
> 所有工具都在 `D:\agentzone\VModule\` 根目录,双击即可。

---

## 零步骤 · 启动服务

双击 `startlite.bat` (或 `start.bat`),浏览器会自动打开 http://localhost:8100。
看到 "VModule v3.1.0" 页面即为启动成功。

---

## 一步骤 · 识别当前业务路径

双击 `detect_path.bat`。

会输出当前系统属于 A/B/C/D 哪条路径:

| 路径 | 特征 | 现场动作 |
|---|---|---|
| **A** | visflowz pos2/pos3 + D60-D63 + PLC 192.168.124.148 | 已是目标路径,跳到第三步预检 |
| **B** | 大恒 Cam1/Cam2 多曝光 + M100-M102 映射 | 如果业务目标是 visflowz,**必须先跑第二步导入** |
| **C** | 海康非 visflowz 预设 | 如果业务目标是 visflowz,**必须先跑第二步导入** |
| **D** | USB 单相机基线 | 仅适合开发,不建议直接上线 |
| **?** | 未识别自定义配置 | 请人工确认 |

---

## 二步骤 · 切到 visflowz 配置 (仅当第一步显示不是 A)

双击 `import_visflowz.bat`。

脚本会:
1. 先把当前配置备份到 `backend\data\_diag\backup-<时间戳>.json` (自动生成)
2. 导入 `visflowz-config-vmodule-2026-05-13.json` (根目录里那份)
3. 立即跑业务自检,required 必须 12/12 通过
4. 导完出现 `===> Import OK. All self-checks passed.` 才算成功

**回车前会让你确认,Ctrl+C 可取消。**

### 如果导入后自检没全通过,或想立刻回滚:
```
import_visflowz.bat --file backend\data\_diag\backup-<时间戳>.json --skip-backup -y
```
把 `<时间戳>` 换成脚本输出里显示的那串。

---

## 三步骤 · 上线前预检

双击 `preflight.bat`。

最终输出一行结论:

| 结论 | 含义 | 该怎么办 |
|---|---|---|
| **===> GO. Ready to launch.** | 全部通过 | 可以上线 |
| **===> GO with WARN. ...** | 有 WARN 但无 FAIL | 人工评估 WARN 项后再决定 |
| **===> NO-GO. Fix [FAIL] items ...** | 有硬性失败 | 不要上线,先修 [FAIL] |

### 关键 WARN 的处理优先级 (按现场价值)

1. `PLC ... 未连接` -> ping 目标 IP,确认 502 端口放行 + PLC 的 Modbus TCP Slave 已启用
2. `相机 ... 未打开` -> 相机管理页点"打开"。如果 SN 是 CHANGE_ME 占位符,必须先改成真实 SN
3. `没有已加载的模型` -> 模型管理页上传权重到 `backend\data\weights\`
4. `GPU 不可用` -> 只要现场能接受 CPU 推理就不用管;要 GPU 则检查 CUDA / torch 安装
5. `VisFlowZ 业务自检未通过` -> 回第二步导入配置

### 想让某些 WARN 变成硬性 NO-GO (更严格):
```
preflight.bat --visflowz --check-plc --check-cameras
```
分别表示:
- `--visflowz`: visflowz 自检未通过直接 NO-GO
- `--check-plc`: 任何 PLC 未连接直接 NO-GO
- `--check-cameras`: 任何相机未打开直接 NO-GO

---

## 常见问题速查

### Q: detect_path.bat 说 Path B 种子模板,但现场想走大恒
A: 把相机管理页里的 SN 从 `CHANGE_ME_CAM1/2` 改成真实海康/大恒相机 SN,把 PLC 连接页的 IP 改成现场 PLC 实际 IP,再跑 preflight。

### Q: import_visflowz.bat 报 "后端 /health 不可达"
A: 先确认 startlite.bat 已启动且浏览器能打开 http://localhost:8100。

### Q: preflight.bat 说 "VisFlowZ 业务自检未通过,required 0/12"
A: 说明当前不是 visflowz 路径。要么跑 import_visflowz.bat 切过去,要么把 preflight 参数里的 `--visflowz` 去掉。

### Q: 导完发现用错了配置
A: 在 import_visflowz.bat 的输出里找一行 "已备份到: ..." 的路径,然后:
```
import_visflowz.bat --file "那条备份路径" --skip-backup -y
```

### Q: 相机 SN / PLC IP 怎么对齐到 visflowz 参考的 DA8290609/709 和 192.168.124.148?
A: visflowz-config-vmodule-2026-05-13.json 里已经写死了这些值。如果现场实物不是这个 SN/IP,**必须**在相机管理页 + PLC 连接页手动改成实际值,然后再跑一次 preflight 确认。

---

## 工具文件清单

| 文件 | 用途 |
|---|---|
| `detect_path.bat` | 识别当前业务路径 |
| `import_visflowz.bat` | 切到 visflowz 配置,带自动备份 + 回滚 |
| `preflight.bat` | 上线前综合健康检查 |
| `scripts\detect_path.py` | detect_path 的 Python 本体 |
| `scripts\import_visflowz.py` | import_visflowz 的 Python 本体 |
| `scripts\preflight.py` | preflight 的 Python 本体 |
| `visflowz-config-vmodule-2026-05-13.json` | visflowz 参考配置 (导入目标) |
| `backend\data\_diag\backup-*.json` | 自动备份的配置快照 |

---

## 紧急回滚 (5 分钟内恢复之前状态)

```
import_visflowz.bat --file backend\data\_diag\backup-<最新时间戳>.json --skip-backup -y
```

执行后:
- 配置立即回滚
- 会再跑一次 self-check (原配置不是 visflowz 的话自检会显示 [FAIL],但脚本会明确提示"若此次是回滚到非 visflowz 配置,这是预期行为,可忽略")
- 看到 `===> Import OK ...` (无论后面有没有 with WARN) 就说明配置已经切回去了
- 真正的导入失败会显示 `===> Import FAILED.`,这种情况下配置没动
