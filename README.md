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
- 完整工具输出在证据记忆采集链路中按哈希留存；有界首尾预览模块已测试，模型当前工具预览仍沿用旧格式。
- [版本化离线重评](docs/REVERIFY.md)：对已有补丁应用新版验证，核对源码来源并记录哈希，保留原始成绩和提交状态，不调用模型 API。
- 明确登记 Requests 和 Click 两种源码布局，按包内既有 Python 文件重建候选；布局配置及实现快照参与对照检查。
- [逐步源码进展观测](docs/PROGRESS.md)：记录动作前后变化、相对初始版本的净变化和采集异常；可选发送复查提示，不将未改动认定为停滞或将改动认定为修复。
- [有版本的证据记忆](docs/EVIDENCE_MEMORY.md)：保存有限源码位置、片段和失败记录，按当前源码指纹标记有效、过期或未知；历史删减时可补回卡片，仍遵守原上下文上限。
- [结构化证据](docs/STRUCTURED_EVIDENCE.md)：静态提取片段所在函数的完整签名、参数与所属类，并可附原任务约束原文；不执行源码，过期签名不补回。
- [公开检查来源与版本](docs/PUBLIC_CHECKS.md)：将固定公开复现脚本放入新容器，对允许导出的源码版本执行检查；记录脚本和源码哈希，区分公开检查、自写测试与独立验收，可选反馈当前结果和收尾建议。
- [结构化 Python 测试工具](docs/PYTHON_CHECK_TOOL.md)：接收 Agent 编写的 Python 断言，由监督进程返回真实退出状态、超时和执行前后源码版本；截断输出时保留合法 JSON 与状态字段，测试不会自动提交。
- [阶段调度](docs/STAGE_GUIDANCE.md)：按源码变化、版本匹配的检查和剩余调用数提出下一步；可选在检查节点指定 Python 工具，记录实际约束，不代替模型修改或提交。
- [离线失败归类](docs/FAILURE_TAXONOMY.md)：分开记录独立验收、提交、源码修改与检查覆盖差异；缺失证据保留未知，输出来源哈希，不执行历史轨迹或推断失败原因。
- [固定条件模型对照](docs/MODEL_COMPARISON.md)：版本化选择模型及报价，保留返回模型名，严格检查不同模型使用相同任务、工具、预算及实现快照，独立统计成本与修复结果。

## 实验现状

3 个自建开发任务首次配对实验：基线验证通过 2/3，恢复组 3/3；正常提交分别 1/3、2/3，调用分别 21、22 次。任务少、未重复且已用于开发，不能推断通用提升。见 [完整报告](reports/dev-paired-003.md) 和 [复现说明](docs/REPRODUCE.md)。

已新增 [三文件任务队列修复](docs/MULTIFILE.md)：基线未通过，恢复组通过全部 8 组独立测试，但仍因步数耗尽未正常提交。见 [多文件对照报告](reports/multifile-paired-001.md)。此任务也是自建开发题，不是真实企业 issue 或独立保留集。98 项本地离线测试覆盖诊断、预算、证据留存、任务验证器、结束状态、有界历史、原生工具协议、输出额度对照、多仓库源码导出、进展观测、证据记忆失效、静态函数作用域、公开检查来源与版本、结构化测试执行、阶段调度、离线结果归类及模型配置对照。

`recovery-budget` 增加逐轮剩余调用提醒，并明确区分补丁验证与正常提交；历史设计见[轨迹审计](reports/completion-audit-001.md)。现已在真实仓库试跑，尚无稳定效果结论。

使用[原生工具调用](docs/NATIVE_TOOLS.md)后，同一个 Requests 真实历史 issue 的两次干净运行均通过 5 组独立回归并正常提交，分别调用 21/22 次，格式拒绝均为 0；两次各有 7 次请求实际使用有界历史选择。见 [成功复测及限制](reports/native-study-001.md)。这是单题重复、自定义回归，不是跨任务成功率或 SWE-bench 分数。

已扩展至 **3 个不同的 Requests 历史问题**。新增重定向题通过冻结的 6 组测试但未提交，事后审计还发现新参数冲突；Cookie 题首次运行因多次输出截断退出，未修复。该轮两题均只跑一次，完整保留负结果，见[新增任务报告](reports/new-requests-study-001.md)和[复现步骤](docs/NEW_REQUESTS_TASKS.md)。

[输出额度重复对照](reports/output-budget-study-001.md)在同一 Cookie 题各跑两次，512/1024 组累计截断为 9/1，冻结测试通过且提交为 0/2、2/2；**额外审计发现两份 1024 补丁仍有缺陷**，不能宣称修复质量提升。现支持可配置输出上限和严格对照检查；见[复现设计](docs/OUTPUT_BUDGET.md)和[第四课讲解](docs/LESSON_04.md)。

[Cookie v2 与提交协议修正](reports/cookie-v2-study-001.md)将独立回归扩展至 10 组，并修正收尾提示与底座提交协议不一致的问题。两次新运行一次通过并提交、一次失败；保留全部结果。新增[离线重评工具](docs/REVERIFY.md)，历史成绩保持不变。v2 仍是同一开发题，不是新增独立问题或策略因果对照。

[第二个仓库 Click](reports/click-study-001.md)已完成从源码导入、Agent 执行到独立验证与离线重评的完整流程。首次两次修复均失败，分别暴露实现错误和长期检查后未形成有效修改的问题。该阶段共 **2 个仓库、4 个不同历史问题**，尚无可靠跨仓库修复结论；[Click 复现步骤](docs/CLICK_TASK.md)完整公开。

[源码进展提示配对实验](reports/progress-study-001.md)对“只记录”和“发送提示”各运行一次。首次修改发生在动作 22 / 19，但两份补丁均有未定义变量错误，均未通过独立验证。逐步证据和三次提示发送可查；不将修改提前解释为修复质量提升。

[版本化证据记忆实验](reports/memory-study-001.md)在 Click、Requests 各完成一组对照，34 次请求实际补回卡片，并区分匹配、过期和未知版本。四次修复均未全部通过独立回归；已提交的 Requests 补丁仍有兼容性缺陷。功能及审计链路已验证，尚无修复成功率提升结论。

[完整签名与任务约束对照](reports/symbols-study-001.md)中，结构化组通过十组独立回归，普通片段组因不存在的方法失败；两组都未提交。结构化组还暴露了 Agent 自写测试的错误路径断言，已用参考版和候选版离线核实。每组仅一次，不表述为稳定性能提升。

[公开检查来源与版本反馈](reports/public-checks-study-001.md)新增脚本冻结、源码版本绑定及新容器检查。24 次反馈与当前源码版本全部匹配，但两组公开复现通过后，独立验收均为 9/10，均未提交。本轮验证了证据链路，未观察到最终结果改善。

[结构化测试工具与新 Click 转发任务](reports/forward-tool-study-001.md)完成工具集成和一组新题对照。普通组通过冻结十组回归并提交，但事后发现两项兼容性缺陷；新工具组未调用新工具、补丁为空。该阶段共 **2 个仓库、5 个历史问题**，不将工具实现、模型采用和完整修复混为一谈。

[阶段调度两仓库对照](reports/stages-study-001.md)完成四次固定运行及 91 次决策复核，六次指定检查均执行，并识别出一次测试工具内部修改源码的情况。Click 两组均未通过验收，Requests 只记录组通过 10/10 并提交、引导组为 8/10 且未提交。本轮未观察到最终结果改善；Click v2 补充两个契约，不增加独立问题数量。

[符号值补全新任务](reports/completion-study-001.md)加入十二组冻结验收和四类回归注入检查。Agent 实现不变，两组均未修复，暴露未定义变量、未接入主流程的辅助函数和测试工具内修改源码等问题。现为 **2 个仓库、6 个不同历史问题**；不是盲测或官方基准。新增[十六次运行归类报告](reports/failure-inventory-001.md)，不将不同条件合并成效果分数。

最新：[固定条件两模型对照](reports/model-study-001.md)比较 qwen3.8-flash 与 qwen3-coder-plus，两题各一次新运行。Flash 两题通过冻结验收、仅一题提交，Coder 两题均未通过；Flash 的 Click 补丁事后又发现两项上下文兼容性缺陷。公开 95 次正式调用的审计及独立计价，不据单次结果排名模型或宣称 harness 提升。项目 **98 项离线测试**通过，默认模型保持不变。

此前五次未成功的开发尝试和条件变化完整保留在[历史报告](reports/requests-study-001.md)。不将失败隐藏，也不把协议改动前后不同条件的结果当作严格因果对照。

## 本地运行（Python 3.12+，无需 API）

```powershell
$env:PYTHONPATH = 'src'
python -m tracepatch examples/synthetic.traj.json --output artifacts/demo-report.json
python -m unittest discover -s tests -v
python scripts/demo-memory.py --output-dir artifacts/memory-demo-new
```

最后一条是无需 Docker 或 API 的合成演示：展示记忆从有效变为过期、重新读取后更新，
以及在固定字节预算内补回卡片。输出目录必须是新目录，演示结果不属于模型修复成绩。

正式接入模型后，使用相同命令分析真实轨迹。完整日志与报告默认仅保存在本地；分享前检查敏感内容。

## 路线与贡献边界

见 [项目路线](docs/ROADMAP.md)、[第一课](docs/LESSON_01.md)、[实验协议](docs/EVALUATION.md) 和 [进度记录](docs/STATUS.md)。

第二阶段实操见 [真实修复与独立验证](docs/LESSON_02.md)。模型修复结果保存在本机 runs/smoke-003；前两轮失败也保留。scripts/run-smoke.py 为固定单次实验脚本，拒绝覆盖已有目录；再次付费运行前应先完善多实验账本。

第三阶段已新增带预算账本的 `scripts/run-dev.py`。阅读 [第三课](docs/LESSON_03.md) 和 [首批开发集报告](reports/dev-baseline-002.md)：3 个补丁通过，2 个正常提交，发现 4 个动作格式问题。该开发集很小且已参与调试，不能当作泛化成绩。未来付费实验统一从带账本的入口运行，不直接重跑旧教学脚本。

本项目实现诊断与恢复策略。Agent 底座来自 [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)。已支持清单内多个 Python 源文件、真实仓库源码导出与独立验证，并提供源码变化观测及复查提示；Harbor 集成尚未实现。见 [上游归属](THIRD_PARTY_NOTICES.md)、[贡献指南](CONTRIBUTING.md) 与 [MIT License](LICENSE)。
