# 固定执行条件的模型对照

本轮比较 DMXAPI 上的 qwen3.8-flash 与 qwen3-coder-plus。
比较对象是服务商提供的两个模型配置，不独立认证其后端权重身份，也不预设谁更强。

## 配置与计价

`--model-profile` 从 configs/model-profiles.json 选择模型和报价。
它只能覆盖这两项，不能覆盖服务商地址或累计预算；默认 default 保留原 configs/model.json 行为。
模型不存在、报价无来源、单位错误或数值无效时拒绝运行。
请求记录保留服务商返回的 model 字段供核对，返回名称相同也不能证明后端身份。

2026-09-27 从[服务商公开价格页](https://rmb.dmxapi.cn/)及其数据接口核对：

| 模型 | 输入，元/百万 token | 输出，元/百万 token |
| --- | ---: | ---: |
| qwen3.8-flash | 0.8 | 2.7 |
| qwen3-coder-plus | 4.75 | 19 |

数据与公式记录于 [报价快照](../reports/model-pricing-001.json)。
本轮两组使用同一公开报价口径，忽略缓存折扣和账号折扣，均非账单。
历史 Flash 实验仍保留用户此前提供的 0.76 / 2.565 报价，不追改历史费用。
两次[微量协议探测](../reports/model-probe-001.json)使用模拟工具结果，确认代码检查调用及后续 bash 调用格式；未执行生成的命令，不属于修复成绩。

## 实验约束

选择两个已知开发题：Click 2040 补全、Requests 2527 v2 Cookie 复制。
每题两模型各一次新运行。Click 先 Flash 后 Coder，Requests 顺序反过来；没有随机化。
不拿新模型与条件不同的历史运行直接比较。

原生工具、阶段 observe、有界历史、结构化记忆、公开检查反馈、Python 工具及提交提示一致。
每次最多 24 次调用、1024 输出 token、24000 字节输入、300 秒 Agent 时间预算，容器及验收相同。
observe 只记录阶段，不发引导或指定工具。各组使用新的容器和对话，运行间不共享修复记忆。
首次正式调用前冻结任务、代码和配置，运行中不调参、不自动重试，不按成功筛选。

相同 token 上限不代表相同算力或相同可见文字量；不同 tokenizer 和模型默认采样参数仍可能不同。
没有显式设置 temperature 或随机种子。此对照回答固定客户端规则下的运行表现，不隔离纯模型能力。
模型、报价允许变化；比较器要求其余已登记控制项、任务哈希和实现快照相同。
只有明确选择 `--intervention model` 才允许模型不同，普通策略对照仍拒绝这种差异。

## 复现与审计

```powershell
python scripts/run-repo.py --batch repo-model-new --task click-2040 --model-profile qwen3-coder-plus --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile structured --check-mode feedback --test-tool python --stage-mode observe
python scripts/compare-runs.py runs/<flash-batch> runs/<coder-batch> --intervention model --output artifacts/model-compare-new.json
python scripts/summarize-model-study.py --plan reports/model-plan-001.json --output artifacts/model-audit-new.json
```

最后一个命令需要本地原始运行和冻结文件，核对源码、工具记录、计价、阶段决策及最终候选，不执行历史命令。
输出文件必须不存在。若后续源码已更新，应使用对应版本和本地记录审计，不跳过哈希失败。
公开计划和摘要提供追溯信息，私有运行目录不在仓库中；只有公开仓库不能还原全部原始轨迹。

每题每模型仅一次，题目已用于开发；无标准基准、统计显著性、通用模型排名或 harness 效果结论。
模型改善若出现，也不能写成上下文或恢复策略带来的提升。
