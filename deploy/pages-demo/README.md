# Sagt Sidebar · Cloudflare Pages 部署工程

产品演示环境：静态前端（sagt_web 原样复用）+ Pages Functions mock Agent API。

## 结构
```
public/            # 前端静态资源（源自 sagt-202610/sagt_sidebar/sagt_web + demo.html 落地页）
functions/api/     # Pages Functions：/api/* 全量 mock（契约与生产 FastAPI 一致）
wrangler.toml      # pages 项目配置
```

## Mock 契约（与 sagt_sidebar_app.py / app.js 对齐）
- `POST /api/login` → `{success, token, message}`；演示账号 `demo / sagt2026`
- `POST /api/send_message` → SSE `data: {"event":"values","data":{node_result|task_result}}`
- `GET  /api/get_interrupt` → `{has_interrupt, interrupt_info}`（标签场景触发）
- `POST /api/confirm_interrupt` → ok/discard/recreate 三态闭环
- `GET  /api/health` → `{status:"healthy", mode:"cloudflare-pages-demo"}`
- 无 Authorization → 401（前端跳登录页的语义保留）

## 本地运行
```bash
npm i -g wrangler
wrangler pages dev --port 8799     # http://127.0.0.1:8799/demo
```

## 部署（需 Cloudflare 账号）
```bash
wrangler login                     # 或 CLOUDFLARE_API_TOKEN 环境变量
wrangler pages deploy public --project-name sagt-sidebar-demo
```

## 边界声明（防面试误解）
- Functions 为 worker 实例级内存态：中断状态不跨实例、不持久（演示可接受，生产用 Redis/PG，见 FT-001 §5）
- 无真实 LLM/客户数据；话术与画像为固定演示内容
- Pages 免费档即可承载；SSE 经 Functions 流式透传，与 FastAPI StreamingResponse 行为一致
