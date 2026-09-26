# 按证据推进检查、修改与收尾

上一轮 Click 新工具组 24 个动作没有源码变化，也未调用 Python 检查。
[只读轨迹审计](../reports/stage-trigger-audit-001.json)记录了这一现象；未变化不等于没有思考，也不能证明插入提醒一定有效。

新增 `--stage-mode off|observe|guide`，默认关闭。启用必须同时开启 Python 检查、源码观测和公开检查。
observe 计算并记录建议；guide 在同一状态判断上发送提示，并在指定检查节点选择下一次必须调用的工具。
两组拥有完全相同的工具、系统说明和任务，区别为阶段反馈与工具选择约束。

## 固定规则

1. 初始保留最多六次模型调用用于查看和形成假设；拒绝回复也计入调用预算，不等同于六次有效阅读。
2. 达到六次调用，或已有净源码变化，但没有匹配源码版本的结构化检查时，要求下一次调用 `python_check`。代码由模型生成，不自动执行参考测试或参考补丁。
3. 已检查但没有净变化时，提示聚焦已核实的位置进行修改，或进行一次有区分力的诊断。不能靠无意义修改重置提示。
4. 修改后检查失败，提示核对失败预期与原任务，再修正代码或错误自测。超时、未知保留诊断状态。
5. 自写检查退出零且公开复现通过时，提示复查全部原要求后再决定提交；这不等于独立验收通过。
6. 最后两次调用不再强制安排检查，提示处理关键问题并在可行时预留提交。已知失败不因此变成成功，也不自动提交。

该模块读取允许导出的源码指纹、公开检查状态、自写检查元数据及调用计数，不读取独立验收器、金标准修复或自写测试输出中的指令。
源码丢失/采集失败时不沿用通过状态；测试自己改动源码时不能给最终版本提供匹配检查。
相同源码指纹可复用之前的自写检查记录用于建议，这不能证明容器内其它文件、环境或测试覆盖一致。
检查失败或过期时不根据日志里的“成功”转为提交建议。

强制检查通过 API 的 tool_choice 实现，适配器同时拒绝返回错误工具的回复，拒绝也占预算。
所以检查采用属于调度器干预，不能写成模型自发更会使用工具。修改内容和提交仍由模型决定。
guide 同时包含多个阶段提示与工具路由，不是对某一句提示词的单因素归因。

## 验证与复现

无模型 API 的集成检查，用合成回复穿过真实适配器及 Docker：

```powershell
python scripts/check-stages.py --run-dir artifacts/stages-new --output artifacts/stages-new.json
```

它验证错误工具在执行前被拒绝、检查失败后进入修改建议、源码变化后重新检查，以及只有显式提交动作结束任务。

实际运行示例（新批次名）：

```powershell
python scripts/run-repo.py --batch repo-stages-new --task click-1840-v2 --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile structured --check-mode feedback --test-tool python --stage-mode guide
```

用 `--stage-mode observe` 构成同实现对照，比较器选择 `--intervention stage-guidance`。
每次决策、提示和实际 tool_choice 保存于请求记录，并计入原输入额度。

Click v2 在原十组测试之外加入上一轮已公开的两个事后契约，同时明确业务关键字兼容与不继承未传参数的要求。
原 Click 任务、成绩及事后报告保留不变；v2 不增加独立问题数量。
新实验采用两仓库各一组固定对照，仍是已知开发题，不能推断通用成功率。
