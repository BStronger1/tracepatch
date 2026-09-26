# 新任务：Click 多层命令参数转发

来源：[Click PR #1840](https://github.com/pallets/click/pull/1840)，
对应历史 issue #1568。多层命令转发时，中间命令收到的值未完整保留到其上下文，后续转发会丢失参数。

基线 `6c7624491911f0b18f869e5d0a989506e7b416f8`，参考修复 `043511294a9eec59d08e64c351621e790ae74b76`。
沿用项目固定 Python 3.9 镜像、Click 的 `src/click/` 导出规则和无网络执行条件。

任务说明依据公开行为编写，10 项独立回归覆盖多层转发、直接调用命令时的上下文参数、默认值、
显式空值覆盖、父上下文隔离、命令与父上下文身份、普通回调行为、隐藏参数、错误路径和 CLI 返回值。
公开最小复现只检查两层转发，不能代替这些回归。

这是本项目首次运行的新题，独立问题数量从四个增至五个。其公开参考修复改动较小，
不能宣称它代表企业大型多文件任务。任务作者已查看参考修复来定义并核验行为，
不是盲测保留集，也无法排除历史修复进入模型训练数据。
实验前冻结说明与验收，运行后不追改测试去改善成绩。

预检查不调用 API：

```powershell
python scripts/run-repo.py --batch repo-forward-preflight-new --task click-1840 --visible-reproducer --verify-only
python scripts/check-forward-task.py --preflight runs/repo-forward-preflight-new --run-dir artifacts/forward-mutants-new --output artifacts/forward-mutants-new.json
```

第二条在参考修复上分别注入父上下文污染、过滤未声明参数、错误覆盖显式值三种回归，
确认独立验收会识别这些错误。目录与输出文件须使用新名字，保留历史证据。
