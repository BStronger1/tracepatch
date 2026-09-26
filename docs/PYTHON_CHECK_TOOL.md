# 结构化 Python 测试执行

上一轮反馈实验中，Agent 使用成功字符串出现次数作为 shell 退出码，导致测试断言失败时外层命令却返回零。
新增可选的 `python_check(code)` 原生函数，让模型提交 Python 断言代码，由 Harness 监督执行并产生结构化进程状态。
`bash(command)` 仍负责读文件、修改源码和主动提交；旧模式默认不变。

## 执行和证据边界

- `--test-tool python` 要求原生工具与源码观测。每次回复恰好调用一个函数，参数必须符合严格 JSON 模式；不接受重复键、额外参数或截断回复。
- Harness 在既有断网 Agent 容器中启动独立 Python 子进程，不经过 shell。监督进程保留 stdout/stderr、退出码，20 秒超时后终止子进程组；正常结束也清理同组残留进程。文件大小上限为 2 MiB，避免无限输出撑满临时日志；它也限制自写测试创建的大文件。
- 状态分为 process_passed / process_failed / timed_out / unknown。信号终止属于失败；基础设施错误属于未知。stdout 中的 JSON、“成功”或提交标记不会覆盖监督结果或触发 Submitted。
- 每份自写测试保存代码、代码哈希、完整输出、输出哈希及执行前后源码集合哈希。检测到源码变化时明确标记 changed；不能把这个结果视为最后版本已通过验收。
- 工具观察最多 6000 字符。只截断输出内容，保留完整状态字段和合法 JSON，不再直接截断序列化结果。
- 普通 bash 工具行为保留，模型仍可能选择 shell 跑测试；新工具不会自动接管所有 shell 命令。

这里的 provenance 固定为 `agent-authored-python`，`acceptance_verified` 始终未知。
进程退出零可能只是空测试或显式退出零，测试预期也可能写错。它只消除 Harness 这一执行路径中的外层 shell 退出码掩盖问题，不能证明测试覆盖或补丁正确。
不抵御主动篡改容器运行环境或监督进程的恶意代码。独立验收仍在 Agent 结束后，在干净容器中运行；参考补丁和独立测试不进入模型上下文。

## 复现

无需 API 的集成验证：

```powershell
python scripts/check-python-tool.py --run-dir artifacts/python-tool-new --output artifacts/python-tool-new.json
```

真实任务：

```powershell
python scripts/run-repo.py --batch repo-forward-new --task click-1840 --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile structured --check-mode feedback --test-tool python
```

`--test-tool off` 为同一实现中的关闭条件。比较方式：

```powershell
python scripts/compare-runs.py runs/repo-forward-off runs/repo-forward-python --intervention python-test-tool --output artifacts/forward-comparison.json
```

该对照同时改变工具可用性、工具选择约束（只能 bash → 两种工具选一）及对应系统使用说明；
比较器只允许固定模板产生的说明变化，其他配置和源码快照必须相同。不是只改一个提示词的实验。
新工具模式也会占用相同 24000 字节输入额度中的更多工具说明空间，须报告实际上下文删减。
