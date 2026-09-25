# 首个真实仓库接入：Requests 方法名处理

来源：[Requests issue 2316](https://github.com/psf/requests/issues/2316) 与
[官方 PR 2317](https://github.com/psf/requests/pull/2317)。这是一条已公开多年的小补丁问题，
用于验证真实整仓运行流程，不代表复杂 issue 能力；模型训练中可能已见过，不能称作未见题。

## 冻结与隔离

- 修复前提交：091991be0da19de9108dbe5e3752917fea3d7fdc。
- 参考合并提交：de2494d36f53aaaf32f6b387c1112f2e37325533。
- 使用固定 Python 3.9 镜像 digest，以兼容历史依赖；无需额外 pip 安装。
- 从 Git 对象导出源码，不向 Agent 提供 .git 历史、官方修复或独立验证器。
- 主机 API 适配器访问模型；执行容器禁止网络、不挂载主机密钥。
- 只把修复前已存在的 requests/**/*.py 导出到干净源码副本，拒绝符号链接或缺失源码。
- 验证器由 harness 重新注入，模型写的测试文件不进入独立验证。

## 自定义测试范围

原 PR 测试使用 HTTP 服务。本项目使用内存 BaseAdapter 记录 PreparedRequest，避免外部 HTTP 服务、DNS 与网络噪声。
五组测试检查 bytes 方法名、大小写、原有字符串方法、请求体/参数/头/超时传递及便捷 get 接口。
预检查必须满足：原始版本在 issue 复现测试上失败，官方参考修复通过全部五组测试。

这不是原版 SWE-bench 测试环境，没有运行上游完整测试集，也不报告 SWE-bench resolved 分数。
观察结果只覆盖该自定义回归。Requests 源码不随 TracePatch 发布，单独克隆并遵守其 Apache 2.0 许可证。

## 有界上下文候选

首轮真实仓库运行在第 11 次请求前超过 24 KB 输入上限，留下 10 次已付费调用。完整记录保留。
新增 recent-turns 策略在超限时保留原始系统指令和任务描述，按完整 assistant/后续反馈组删除最早历史，加入显式省略提示。
最近一组也无法放入时仍停止，不截断任务或执行残缺动作。记录原始字节数、省略条数及内容哈希。
完整历史保存在本机轨迹；这是有界历史选择，不是语义记忆、摘要或检索。工具输出仍沿用每条 6000 字符的旧预览限制。

## 复现

先完成 [通用配置](REPRODUCE.md)。在 tracepatch 根目录执行：

```powershell
git clone --no-checkout https://github.com/psf/requests.git ../vendor/requests
git -C ../vendor/requests fetch origin de2494d36f53aaaf32f6b387c1112f2e37325533
docker pull python@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b
python scripts/run-repo.py --batch repo-check-local --verify-only
python scripts/run-repo.py --batch repo-control-local --policy recovery-budget --context-policy none
python scripts/run-repo.py --batch repo-window-local --policy recovery-budget --context-policy recent-turns
python scripts/compare-runs.py runs/repo-control-local runs/repo-window-local --output reports/repo-local.json
```

请使用已安装通用依赖的 Python 环境。每批次必须使用新的名称；付费组各最多 12 次调用，每次 512 输出 Token。
两组唯一指定差异为历史选择策略。初轮无步数提醒的失败试跑不作为这两组的正式对照臂。

## 可选公开问题复现辅助

`--visible-reproducer` 会额外把 reproduce_issue.py 放进 Agent 工作区，并提示修复前后运行。
该脚本从公开 issue 构造 Session→send 的失败路径，不含修复方案或参考源码。
预检查额外要求该脚本在原版失败、官方修复版通过；独立验证仍使用未提供给 Agent 的五组回归。
这是观察初次失败后加入的开发辅助条件，必须单独报告；不能与未提供复现脚本的组混算为同条件对照。

```powershell
python scripts/run-repo.py --batch repo-assisted-local --policy recovery-budget --context-policy recent-turns --visible-reproducer
```

`--max-calls 24` 可单独增加整仓任务的步数上限；默认仍为 12。
改变上限也是实验条件变化，不能与旧组直接归因为策略效果。全部当前结果见 [开发报告](../reports/requests-study-001.md)。

新增原生模式：添加 `--action-protocol native`，见 [接口配置](NATIVE_TOOLS.md)。
该模式在本题完成了两次通过独立验证且正常提交的重复运行，见 [最新结果](../reports/native-study-001.md)。
