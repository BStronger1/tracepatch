# 五分钟项目演示

该演示调用项目真实模块，使用人为编写的小文件展示机制，不运行模型，不依赖 Docker，
也不执行候选源码。所有验收状态均为模拟输入，不能将演示当作 Agent 修复成功证据。
只需 Python 3.12+，无第三方包、API Key 或服务器。

## 一条命令运行

在仓库根目录执行；输出目录必须不存在，再次演示换一个后缀即可。

```powershell
python scripts/demo-interview.py --output-dir artifacts/interview-demo-001
```

本项目已有虚拟环境时，可将 `python` 换成 `.\.venv\Scripts\python.exe`。
打开生成的 `WALKTHROUGH.md` 看四个步骤，`demo-report.json` 包含具体状态、哈希与字节统计。
最后出现 `PASS` 说明演示内置检查通过；出现异常时先查看报错，不把未完成的输出当作成功。
已有目录会报错，不会清空或覆盖历史结果。

## 五分钟顺序

| 时间 | 展示 | 要讲清的事情 |
|---|---|---|
| 0:00–0:40 | README 与项目目标 | 模型提出动作，底座执行循环，TracePatch 管理工具、上下文、记录和独立验证。 |
| 0:40–1:40 | 命令输出 EDIT | 换行不同会使精确匹配失败；兼容处理保留源码格式，语法错误不会落盘。编辑成功不等于逻辑正确。 |
| 1:40–2:40 | MEMORY 与 CONTEXT | 代码变化使旧证据失效；重新读取才补回新版本，证据仍占用同一个输入预算。 |
| 2:40–3:30 | OUTCOMES 与 JSON | 正常提交、验收结果是两件事，缺失验收保留未知。本段输入是模拟的。 |
| 3:30–4:30 | [真实实验报告](../reports/edit-study-001.md) | 48 次真实 API 请求，两组均未修复；工具组两次失败暴露换行兼容缺陷，后续回归验证修正。 |
| 4:30–5:00 | 对应源码 | 打开一个核心函数解释实现，并说明已实现内容与评估限制。 |

演示的小文件用于让机制可观察；真实实验报告用于说明实际证据。不要把两者数字混在一起。

## 简历条目与代码入口

| 简历内容 | 首先读的入口 | 对应证据 |
|---|---|---|
| 本地隔离执行、独立验证 | [run-repo.py](../scripts/run-repo.py)：`environment`、`verify`、`main` | [真实仓库实验](../reports/model-study-001.md) |
| 输入控制与版本化证据 | [window.py](../src/tracepatch/window.py)：`request_payload`；[memory.py](../src/tracepatch/memory.py)：`observe`、`recall` | 演示 current → stale → current；[记忆实验](../reports/memory-study-001.md) |
| 编辑故障定位和修复 | [editing.py](../src/tracepatch/editing.py)：`replace_source` | [字节审计](../reports/edit-newlines-001.json)、[Docker 回归](../reports/edit-docker-002.json) |
| 提交与正确性分开报告 | [lifecycle.py](../src/tracepatch/lifecycle.py)：`completion_status` | 演示四种状态、真实报告中的独立验收与提交列 |

## 不依赖背诵的练习

先读 [第五课](LESSON_05.md)。在本地副本里将演示的 `return 7` 成对改成 `return 9`，
并更新对应预期字节和证据断言，再用新输出目录运行。解释为什么哈希变化，但“编辑成功不等于验收通过”仍成立。
这是尚待本人完成的学习练习，项目文档不将它写成已经完成的个人贡献。
