# Sagt · Sales Champion Agent

> 企业销冠智能体 —— 基于 LangGraph 的销售场景多智能体系统，本仓库为**工程化加固版**。
>
> Upstream: 项目骨架来自课程仓库 `cnb.cool/llm.course/202610/sagt-202610`（教学示例）。
> 本仓库的价值在于 `feat/v2-engineering-hardening` 系列提交：以生产标准对教学代码做的
> 缺陷修复、性能重构、弹性策略与测试/CI 建设。

## Architecture

```
sagt_agent    Python · LangGraph server 模式（langgraph.json）
  ├─ 主图: cleanup → welcome → [并行数据加载 fan-out/fan-in] → intent → 子图 → confirm
  ├─ 子图: chat_suggestion / kf_chat / tag / profile / schedule / talk
  └─ 人工在环: interrupt() → ok / discard / recreate（tag、profile 写路径）
sagt_client   API 客户端 + 长期记忆(Store)初始化脚本
sagt_admin    管理后台（员工/客户/会话/标签字典）
sagt_sidebar  企微侧边栏前端（流式对话 + 中断确认卡）
```

## Engineering Hardening Highlights

| Commit | 类型 | 问题 → 方案 |
|---|---|---|
| `a4ed2ad` | fix | StoreClient 在模块导入期调用 `get_store()`，脱离 LangGraph 运行时上下文即 `RuntimeError` → 属性懒解析，构造零副作用；刻意不做实例缓存（多上下文串用风险） |
| `ff1aa25` | perf | 7 个数据加载节点串行链（耗时=Σ）→ 写集不重叠分析后改并行 fan-out/fan-in（耗时=max），保留 `customer→order` 真依赖边；reducer 合并正确性由端到端测试断言"5 分支结果一个不丢" |
| `cade160` | fix | 模型空输出分支的 f-string 引用未定义变量 `e` → 触发即二次 NameError 崩溃；修复并补回归测试 |
| `4892fc5` | fix | 演示假聊天记录硬编码在生产路径（污染 Prompt 输入）→ `SAGT_DEMO_MODE` 环境开关，默认关闭，双向回归测试 |
| `7f85ce8` | feat | 裸模型客户端 → `ResilientChatModel`：可重试异常分类（超时/连接/限流）+ 指数退避抖动 + primary→fallback 降级链 + `sagt_degraded` 元数据标记；SDK 层重试置 0 防叠加 |
| `7528e63` | ci | GitHub Actions：`uv sync --frozen` + 全离线测试门禁 |

## Testing

全部离线（mock Store + fake LLM），无网络/无模型 key 依赖：

```bash
cd sagt_agent
uv sync --dev
PYTHONPATH=src uv run pytest test/engineering/ -q
# 15 passed
```

覆盖：图编译/接线、懒加载语义、端到端 invoke、并行分支 reducer、cleanup 重置、
空输出回归、demo 开关回归、弹性策略 6 例（重试成功/耗尽降级/不可重试直降级/全挂异常/无降级档）。

## Run (LangGraph server mode)

```bash
cd sagt_agent
cp .env.example .env        # 填 MODEL_NAME / API_KEY / BASE_URL；可配 FALLBACK_MODEL_NAME
uv run langgraph dev        # http://127.0.0.1:2024
# 调试（另一终端）：
cd ../sagt_client/store_client && uv run python sagt_demo_init.py
cd ../agent_client && uv run python sagt_agent_test.py chat
```

## Roadmap (v2)

- [ ] MCP 工具层（Java 业务系统 → Agent tools，契约先行 + 幂等键）
- [ ] Langfuse 全链路 trace（run 级 user/session metadata）
- [ ] LLM 意图路由恢复（当前 menu 直达 + 兜底）
- [ ] 上下文 compaction 与 Token 预算
- [ ] 故障演练：LLM 全挂降级 / 工具熔断 / checkpoint 断点续跑

## License

Educational portfolio project. Upstream course code belongs to its author.
