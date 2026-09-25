# 原生工具调用适配

服务端依据：[DMXAPI 函数调用说明](https://doc.dmxapi.cn/function-call.html)。
文档说明接口可返回 tool_calls，但不能证明特定模型支持；本项目额外完成当前 qwen3.8-flash 的两轮实测。

## 协议

请求显式提供 bash 函数 schema，唯一必填参数为 command 字符串，要求使用该工具并关闭并行调用。
回复必须含恰好一个 function 工具调用、非空 id、bash 名称及完整 JSON 参数。
拒绝重复 JSON 键、未知参数、错误工具、多个调用、空命令、NUL 字符和输出截断。
原生模式不将正文中的 XML 或代码块作为备用可执行命令。

执行后的结果以 role=tool 和匹配的 tool_call_id 回传；下一次请求保留 assistant.tool_calls。
上下文删减保留完整调用—结果组，并把 schema 字节计入 24 KB 上限，避免孤立的工具结果。
失败回复保留在本地记录中，但不会把无效工具调用放入下一轮协议历史。

当前服务商的探测回复包含合法 tool_calls，却使用 finish_reason=stop。适配器接受 stop/tool_calls，
仍校验完整参数；length 一律拒绝。该兼容性仅对本次测试服务与模型有证据，不宣称所有兼容端点都可用。

## 探测与实验的区别

scripts/probe-tools.py 发送两次固定命令参数测试，并向模型明确声明工具结果为模拟数据。
探测不执行系统命令，只确认结构化回复及回传格式；它不是 Agent 修复结果。
真实任务随后在隔离 Docker 中执行，并使用原始独立测试判断补丁。

使用：

```powershell
python scripts/probe-tools.py --name native-probe-local
python scripts/run-repo.py --batch repo-native-local --policy recovery-budget --context-policy recent-turns --visible-reproducer --max-calls 24 --action-protocol native
```

文本模式仍通过 --action-protocol text 保留。两种协议需要不同接口提示，
历史试跑只能作描述性比较；原有比较脚本会拒绝把不同协议/提示直接认定为同配置对照。
复现脚本、输出上限、任务条件和每次使用的实现均保存快照。
