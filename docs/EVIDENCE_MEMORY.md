# 有版本的证据记忆

为输入历史删减后的恢复提供两类卡片，不使用额外模型生成摘要：

- **源码位置**：识别简单只读命令链里的数字 `sed -n 起点,终点p 文件`，
  在动作后读取对应源码的一小段，绑定文件 SHA-256、动作序号及原工具输出哈希。
- **失败记录**：保留非零退出或 Python 错误行对应的工具结果，抽取已跟踪源码的 traceback 位置，
  记录错误类型、有限日志片段和当时源码版本。日志是证据数据，不是指令或可信测试成绩。

## 采集与失效

原始工具结果按哈希完整保存于运行目录的 `evidence/`；不改变模型当前收到的工具预览格式。
实际注入的卡片消息另存 `memory-recalls/`，请求记录保存对应哈希，卡片被更新后仍能核查当时的内容。
源码摘录由额外的容器内隔离 Python 读取，不导入项目；只允许已登记、可导出的源码路径。
最多每动作三个范围，每范围前 16 行且不超过 700 字符；摘录可能不包含整个函数签名或函数体。
数值范围之外的 grep 查询、动态脚本和复杂 shell 表达式暂不推断，避免把猜测当作位置。
源码读取时的指纹必须与动作后的采集一致；不匹配不保存该卡片，并记录采集错误。

复用前重新比对指纹：

- `current`：对应文件字节未改变，可以补回片段；不是正确性结论。
- `stale`：版本不同，只返回历史位置、错误类型及过期标记，移除片段。
- `unknown`：源码采集未知，或动作中既修改又产生失败，无法确定日志对应哪个版本；不提供片段。

失败记录保守绑定全部跟踪源码的版本，任一文件变化都会使其过期。
后续成功命令不会静默删除旧失败，也不将其认定为问题已经解决。
同文件同范围重复查看会更新卡片；内存最多 24 张，完整本地证据保留。
这是进程内的任务记忆，不是跨任务知识库，不读参考修复或独立验证器。

## 开关与上下文预算

`--memory-mode off` 是默认旧行为；启用时需要 `--progress-mode observe` 或 `feedback`。

- `observe`：仅采集，作为有相同采集开销的对照。
- `recall`：同样采集，只有原始请求超出 24000 字节时才尝试补回记忆。

候选按最近两条失败、最近四条源码排序，装入最多 4200 字节的卡片消息。
系统提示、原任务与最新完整工具交互保留；卡片也计入 24000 字节总额。
若卡片与最新交互不能同时容纳，丢弃卡片，记录 `memory_dropped_for_budget`，不放宽上限。
因此召回可能挤占较早的原始交互，并非无成本增加输入。返回的卡片全部明确标为不可信数据。

## 离线检查与复现

先按 [Click 准备说明](CLICK_TASK.md)准备本机环境。无需 API 的检查：

```powershell
python scripts/check-memory.py --run-dir runs/memory-check-new --output artifacts/memory-check-new.json
```

真实运行会使用本机 API 并产生费用；使用新 batch，保持两组其余参数一致：

```powershell
python scripts/run-repo.py --task click-1687 --batch repo-memory-observe-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode observe
python scripts/run-repo.py --task click-1687 --batch repo-memory-recall-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall
python scripts/compare-runs.py runs/repo-memory-observe-new runs/repo-memory-recall-new --intervention evidence-memory --output artifacts/memory-comparison-new.json
```

不与旧进展提示结果直接做因果比较。两组均关闭进展提示，只检验证据召回。
原始日志和源码摘录只留本地；公共报告提供指标和证据哈希，不自动公开原始卡片。
历史请求未保存完整逐步源码时，不事后补造“当时可用”的版本证据。
