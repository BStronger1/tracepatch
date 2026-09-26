# 有来源与版本的公开检查

Agent 自写测试也可能写错：上一轮候选通过十组独立回归，却被自写测试中 `'/q' == 'q'` 的错误预期卡住。
同时，`python test.py; cat log` 的外层退出码可能为 0，即使测试已经失败。

新增 `--check-mode off|observe|feedback`，默认关闭。启用时必须同时开启源码观测和公开复现：

```powershell
python scripts/run-repo.py --batch repo-checks-new --task requests-2527-v2 --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile structured --check-mode feedback
```

## 检查边界

1. 将公开复现脚本复制到宿主机实验目录并记录哈希。Agent 容器不能改动这份副本。
2. 初始版本及每个新的源码指纹各检查一次。只从 Agent 容器导出允许的既有 Python 文件，覆盖干净基线；自写测试、修改后的公开脚本及新增文件不导出。
3. 在新建的断网容器中直接运行 Python 检查进程。绑定源码集合哈希与脚本哈希，保留退出码和完整输出的哈希。提示不包含测试输出，避免将输出中的成功字样或指令当作控制信息。
4. 源码采集缺失、哈希不一致或基础设施异常记录为 unknown。相同指纹复用结果，包括 unknown，不自动重试；恢复旧指纹可复用该版本结果。这依赖本项目固定镜像、固定脚本和确定性公开检查，不用于任意有状态测试。
5. observe 与 feedback 都执行相同检查。仅 feedback 把当前证据与提交提醒追加到请求，仍受 24,000 字节输入上限约束；请求记录保留实际提示。检查耗时计入运行墙钟时间；两组行为不同可能产生不同版本数与检查开销。

公开复现通过只表明这个窄检查进程正常退出，不等于十组独立回归通过，也不能证明所有要求满足。Agent 自写测试失败仍需检查，不能一概忽略。独立验证器和参考修复仍只用于预检查及运行后验收，不进入 Agent 提示。

这不是对恶意候选代码的防篡改证明：候选代码仍可影响其进程，例如提前退出。新增能力保证脚本来源、版本绑定和执行隔离，不解决恶意测试规避问题。异常退出、超时等不能记为通过。

提交协议保持不变：只有 Agent 主动执行单独的提交动作才能形成 Submitted，公开检查不会替它提交或更改验收成绩。反馈同时包含证据说明、检查冲突复查建议和收尾提示，因此配对实验评估的是这一组反馈，不能归因于其中单句话。

## 不调用 API 的集成验证

```powershell
python scripts/check-public-checks.py --run-dir artifacts/public-checks-new --output artifacts/public-checks-new.json
```

验证错误基线失败、参考版通过、Agent 篡改公开脚本不影响检查、外层 shell 退出零不会覆盖失败，以及宿主机冻结脚本变化会使新版本检查未知。输出路径必须全新。

公开实验保留单题、每组一次的范围限制。不得将这轮开发对照写成通用成功率提升。
