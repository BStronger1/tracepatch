# 新任务：符号值与命令行补全

来源：[Click issue 2040](https://github.com/pallets/click/issues/2040)。
部分符号开头的选项值被误识别成选项名，导致补全失效。
固定错误版 `d251cb0abc9b0dbda2402d4d831c18718cfb51bf` 与
参考版 `f2e579ab187ca8fdfbe6ce86de08f0e9f62fe4ae`。

任务说明将行为边界写清：按当前命令注册的前缀区分选项名与符号值；
真实前缀仍优先补全选项名，计数和布尔选项不占值槽位，并保留多值、重复、等号、路径、
双横杠位置参数和嵌套上下文行为。Agent 不接触参考修复或独立验收器。

12 组自定义验收使用 Python 标准 unittest，无额外服务或容器内联网依赖。
公开最小复现只检查一类 '+' 值，独立验收覆盖其余契约。
参考版十二组全过，错误版失败；恢复旧标点规则、硬编码前缀、让计数选项占值、
缩短多值扫描范围这四种注入回归均被捕获。
证据见 [预检查报告](../reports/completion-preflight-001.json)。

```powershell
python scripts/run-repo.py --batch repo-completion-preflight-new --task click-2040 --visible-reproducer --verify-only
python scripts/check-completion-task.py --preflight runs/repo-completion-preflight-new --run-dir artifacts/completion-mutants-new --output artifacts/completion-mutants-new.json
```

本项目首次运行此历史问题，问题数增加至六个、仓库数仍为两个。
任务作者查看了公开参考修复以核验行为；这是新加入的开发评估题，不是盲测保留集。
历史代码可能存在于模型训练数据，且该修复范围有限，不能称为企业大型任务。
验收覆盖不是完整上游测试，更不是所有真实 shell 的交互验证。

本轮保持已发布的 Agent 执行模块、模型、调用预算和提示不变，仅在同一新任务上比较
observe / guide 阶段模式；任务、测试、模块与配置哈希在调用 API 前冻结。
先 guide 后 observe，各一次，不改动后重跑或按成功筛选，不能估计稳定收益。
