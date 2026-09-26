# 函数作用域与任务约束提示

上一轮记忆只保留数字范围前 16 行、最多 700 字符。
[事后覆盖审计](../reports/memory-coverage-audit-001.json)检查实际注入且版本匹配的 16 张不同源码卡片：
10 张缺少包围其起点的函数完整签名，4 张包含签名，2 张起点不在函数内。
核查只使用指纹匹配的基础或最终源码，未补造中间版本；这是覆盖检查，不是失败因果分析。

## 两种表达方式

- `--memory-profile excerpts`：默认原有摘录表达，保持旧的召回行为。
- `--memory-profile structured`：同一来源、同一采集器，优先补回结构化函数信息和原任务约束提示。

两组都采集 AST 信息；只有召回消息的组织方式不同。该干预同时包含函数信息与约束提示，
不能将效果单独归因于其中一项。仍需 `--memory-mode recall` 才向模型补回，
仍仅在历史需要删减时触发，总额 24000 字节、卡片消息 4200 字节不变。

## 函数信息

对已读取且指纹核对通过的源码使用 Python AST，不导入项目、不执行函数、默认值或装饰器。
优先选择包含片段起点的最内层函数，再选范围内相邻函数，最多两项。
返回限定名称、源码起止行、标准化完整签名、参数名、所属类及其基类表达式。
这是静态声明，不推断运行时装饰器行为、继承的方法解析或变量实际取值。

签名超过 1200 字符时整条省略并标记，不截出看似完整的半条签名。
语法解析失败明确记录错误；没有函数信息时沿用普通源码片段。
代码变化或版本未知后，旧签名与旧片段一样不再补回。
整个函数体、任意 grep 查询及动态生成代码不在本阶段完整覆盖范围。

## 原任务约束

原任务在历史删减时一直保留，本功能是再次突出原文，不是找回丢失任务。
按确定性关键词规则选取最多六句原文，每句最多 380 字符，附原任务哈希及字符起止位置。
例如原文已说明“子类可能需要构造参数”，卡片只重复这句，不推断正确实现。
不读取独立验证器，不从参考补丁提取约束；规则也不能保证找齐所有要求。
任务提示占用同一有限预算，可能挤占其它卡片，需根据实际注入记录核查。

## 运行

准备沿用 [证据记忆说明](EVIDENCE_MEMORY.md)。无需模型的检查：

```powershell
python scripts/check-symbols.py --run-dir runs/symbols-check-new --output artifacts/symbols-check-new.json
```

下面的固定任务对照会调用本机 API，使用新的 batch 名称：

```powershell
python scripts/run-repo.py --task requests-2527-v2 --batch repo-symbols-excerpts-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile excerpts
python scripts/run-repo.py --task requests-2527-v2 --batch repo-symbols-structured-new --policy recovery-submit --action-protocol native --context-policy recent-turns --visible-reproducer --max-calls 24 --max-output-tokens 1024 --progress-mode observe --memory-mode recall --memory-profile structured
python scripts/compare-runs.py runs/repo-symbols-excerpts-new runs/repo-symbols-structured-new --intervention structured-evidence --output artifacts/symbols-comparison-new.json
```

每种条件只跑一次只能作为开发案例，不能证明通用提升。
