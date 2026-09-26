# 逐步源码变化与恢复提示

`progress.py` 在每个实际执行的动作后采集源码 SHA-256，不依赖命令文本是否重复。
跟踪范围与候选导出相同：冻结基础版本中已有的包内 Python 文件。
初始采集必须与宿主机基础源码逐文件一致；不一致时不调用模型。

## 三种模式

- `off`：默认行为，不增加采集或提示。
- `observe`：保存逐步证据，不给模型额外提示。
- `feedback`：同样采集；每连续 6 个动作未改变所跟踪源码时，在下一次请求添加一次复查提示。

两种启用模式都有相同采集开销。格式拒绝不执行动作，不增加动作序号。
同一个信号不因格式拒绝而反复发送；提示写入请求元数据，不伪造工具返回。
提示和已有预算提醒一起进入原有上下文额度；它可能影响历史保留量，这是干预的一部分。

每步记录命令哈希、源码快照摘要、变化文件、相对起始版本的净变化文件、
工具退出码和连续未变化动作数。返回起始版本与从未修改分别可见。
采集失败记为 `unknown`，打断连续计数；下一次成功只重新建立比较基点，
不虚构缺失期间的变化。Submitted 异常仍向上传递，最后一步采集仍保留。

## 不能据此判断什么

源码未变可能是在合理阅读或测试，源码改变也可能引入错误。
同一命令内部改后撤回、临时脚本、新增文件、非 Python 文件不在观测范围。
工具退出码只表示外层命令结果，可能被后续命令掩盖，**不是可信测试成绩**；
`test_passed` 保持未知，补丁是否正确仍由独立验证器判断。
采集使用容器内隔离 Python 的标准库，不导入待修复项目，但容器允许 Agent 写入，
因此不把传感器视为对恶意篡改完全可靠的安全边界。

此前 Click 失败轨迹没有逐步源码快照，不能事后补造。
其前 21 个动作主要查看源码，是开发该功能的线索，不是本检测器已经命中的历史成绩。

## 离线验证与模型对照

准备步骤沿用 [Click 环境](CLICK_TASK.md)。以下集成检查不调用模型：

```powershell
python scripts/check-progress.py --output artifacts/progress-check-new.json
```

固定任务、模型、上下文规则、输出额度、调用上限及实现快照，
仅改变 `--progress-mode observe` / `--progress-mode feedback`：

```powershell
python scripts/run-repo.py --task click-1687 --batch repo-progress-observe-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe
python scripts/run-repo.py --task click-1687 --batch repo-progress-feedback-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode feedback
python scripts/compare-runs.py runs/repo-progress-observe-new runs/repo-progress-feedback-new --intervention progress-feedback --output artifacts/progress-comparison-new.json
```

这两条修复命令会使用本机 API 配置并产生费用。每次使用新的 batch，不覆盖旧结果。
一次配对仅能验证功能接入与案例变化，不能证明统计显著改善。
