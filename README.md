# TracePatch

面向 Coding Agent 的执行轨迹诊断、动作失败恢复与上下文证据留存工具。早期实验项目：已有真实 API 开发集对照，无标准基准成绩或稳定性能提升结论。

Diagnose coding-agent failures, preserve evidence, and evaluate recovery with independently verified patches. An early experimental toolkit.

## 当前可运行能力

- 离线读取 mini-swe-agent `mini-swe-agent-1.1` 格式的结构化命令记录。
- 统计消息、动作、上游报告的调用数及成本，定位完全相同的重复命令。
- 不执行轨迹内的命令；不把重复命令认定为死循环，不把 Submitted 认定为任务成功。
- 样例明确为合成数据，不属于实验成果。
- 识别输出截断、不完整动作和缺失提交动作，生成定向恢复反馈；不执行残缺命令。
- 请求预算账本、Docker 独立验证、冻结实验快照和双组比较。
- 完整工具输出按哈希留存，并生成保留退出码的有界首尾预览；此独立模块已测试，尚未接入付费实验。

## 实验现状

3 个自建开发任务首次配对实验：基线验证通过 2/3，恢复组 3/3；正常提交分别 1/3、2/3，调用分别 21、22 次。任务少、未重复且已用于开发，不能推断通用提升。见 [完整报告](reports/dev-paired-003.md) 和 [复现说明](docs/REPRODUCE.md)。

已新增 [三文件任务队列修复](docs/MULTIFILE.md)：基线未通过，恢复组通过全部 8 组独立测试，但仍因步数耗尽未正常提交。见 [多文件对照报告](reports/multifile-paired-001.md)。此任务也是自建开发题，不是真实企业 issue 或独立保留集。29 项离线测试覆盖诊断、预算、证据留存、任务验证器、结束状态、有界历史及原生工具协议。

`recovery-budget` 增加逐轮剩余调用提醒，并明确区分补丁验证与正常提交；历史设计见[轨迹审计](reports/completion-audit-001.md)。现已在真实仓库试跑，尚无稳定效果结论。

最新：使用[原生工具调用](docs/NATIVE_TOOLS.md)后，同一个 Requests 真实历史 issue 的两次干净运行均通过 5 组独立回归并正常提交，分别调用 21/22 次，格式拒绝均为 0；两次各有 7 次请求实际使用有界历史选择。见 [成功复测及限制](reports/native-study-001.md)。这是单题重复、自定义回归，不是跨任务成功率或 SWE-bench 分数。

此前五次未成功的开发尝试和条件变化完整保留在[历史报告](reports/requests-study-001.md)。不将失败隐藏，也不把协议改动前后不同条件的结果当作严格因果对照。

## 本地运行（Python 3.12+，无需 API）

```powershell
$env:PYTHONPATH = 'src'
python -m tracepatch examples/synthetic.traj.json --output artifacts/demo-report.json
python -m unittest discover -s tests -v
```

正式接入模型后，使用相同命令分析真实轨迹。完整日志与报告默认仅保存在本地；分享前检查敏感内容。

## 路线与贡献边界

见 [项目路线](docs/ROADMAP.md)、[第一课](docs/LESSON_01.md)、[实验协议](docs/EVALUATION.md) 和 [进度记录](docs/STATUS.md)。

第二阶段实操见 [真实修复与独立验证](docs/LESSON_02.md)。模型修复结果保存在本机 runs/smoke-003；前两轮失败也保留。scripts/run-smoke.py 为固定单次实验脚本，拒绝覆盖已有目录；再次付费运行前应先完善多实验账本。

第三阶段已新增带预算账本的 `scripts/run-dev.py`。阅读 [第三课](docs/LESSON_03.md) 和 [首批开发集报告](reports/dev-baseline-002.md)：3 个补丁通过，2 个正常提交，发现 4 个动作格式问题。该开发集很小且已参与调试，不能当作泛化成绩。未来付费实验统一从带账本的入口运行，不直接重跑旧教学脚本。

本项目实现诊断与恢复策略。Agent 底座来自 [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)。已支持清单内多个 Python 源文件及 Requests 整仓实验中的源码导出与独立验证；Harbor 集成和停滞恢复尚未实现。见 [上游归属](THIRD_PARTY_NOTICES.md)、[贡献指南](CONTRIBUTING.md) 与 [MIT License](LICENSE)。
