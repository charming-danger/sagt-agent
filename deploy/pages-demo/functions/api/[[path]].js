/// Sagt Sidebar — Cloudflare Pages Functions (mock Agent API)
///
/// 用途：无后端环境下的产品演示（PRD-001 的 S1/S2/S3 页面流程可完整走通）。
/// 契约来源：sagt_sidebar_app.py（FastAPI 版）与 sagt_web/app.js 的消费格式：
///   - SSE 行格式 `data: {"event": "...", "data": {...}}\n\n`
///   - event=values 时 data 含 task_result / node_result（LangGraph values 流投影）
///   - 401 → 前端跳登录页
/// ⚠️ 这是 demo mock，不是生产实现：无鉴权语义（token 仅回显）、无真实 LLM 调用。
/// 生产链路 = FastAPI 网关 + LangGraph server（见 ADR-001/002）。

const DEMO_USER = "demo";
const DEMO_PASS = "sagt2026";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Authorization",
};

const sseHeaders = {
  "Content-Type": "text/plain;charset=utf-8",
  "Cache-Control": "no-cache",
  ...CORS,
};

const jsonHeaders = { "Content-Type": "application/json;charset=utf-8", ...CORS };

const enc = new TextEncoder();
const sse = (event, data) => enc.encode(`data: ${JSON.stringify({ event, data })}\n\n`);

// ---- demo 记忆（worker 实例级，跨请求足够演示中断流） ----
const demoState = {
  interruptPending: false,
  profileVersion: 0,
};

function nodeMsg(node, code, msg) {
  return {
    execute_node_name: node,
    execute_result_code: code,
    execute_result_msg: msg,
    execute_exceptions: [],
  };
}

function taskResult(text, explain, code = 0) {
  return { task_result: text, task_result_explain: explain, task_result_code: code };
}

const PROFILE = {
  profile_items: [
    { item_name: "基础属性", item_value: "程先生 · 42岁 · 制造业企业主（信息不足项已按演示数据补全）" },
    { item_name: "需求与关注点", item_value: "近3次会话聚焦员工福利采购方案与交付周期" },
    { item_name: "购买力与阶段", item_value: "历史订单 ¥86万 · 高价值 · 复购评估期" },
    { item_name: "沟通偏好", item_value: "偏好微信文字沟通，回复集中在工作日晚间" },
    { item_name: "风险提示", item_value: "对价格敏感，近期对比竞品报价；避免口头承诺折扣" },
  ],
};

const TAGS = {
  tag_ids_add: [
    { tag_id: "t_high_value", tag_name: "高价值客户", tag_reason: "历史订单累计86万且处于复购评估期" },
    { tag_id: "t_price_sensitive", tag_name: "价格敏感", tag_reason: "近3次会话两次提及竞品报价" },
    { tag_id: "t_welfare", tag_name: "福利采购", tag_reason: "明确表达员工福利采购需求" },
  ],
  tag_ids_remove: [],
};

const CHAT_SUGGEST = JSON.stringify(
  {
    suggestions: [
      { style: "专业型", text: "程总，您关注的交付周期我们已排到最优档，本周五前确认方案可锁定3月产能。" },
      { style: "关系型", text: "程哥，上次聊到团队扩编，福利方案要不要我按新人数再出一版？" },
      { style: "促单型", text: "程总，这季度政策比上月好，老带新还有额外服务包，我给您算笔账？" },
    ],
  },
  null,
  2
);

// ---- 场景编排：按 task_input 走一遍主图节点序列 ----
function buildScript(taskInput) {
  const menu = taskInput || "";
  if (menu === "profile_suggestion") {
    demoState.profileVersion += 1;
    return {
      nodes: [
        nodeMsg("sagt_welcome_message", 0, "您好，我是Sagt，很高兴为您服务"),
        nodeMsg("load_customer_info_node", 0, "完成客户信息加载"),
        nodeMsg("load_chat_history_node", 0, "完成聊天消息加载"),
        nodeMsg("intent_detection", 0, "识别意图：客户画像"),
        nodeMsg("profile_suggestion", 0, "正在生成客户画像…"),
      ],
      result: taskResult(
        JSON.stringify(PROFILE),
        `画像基于近30天会话与订单数据生成（演示数据 · v${demoState.profileVersion}）。确认后将写入客户档案。`,
      ),
    };
  }
  if (menu === "tag_suggestion") {
    demoState.interruptPending = true;
    return {
      nodes: [
        nodeMsg("sagt_welcome_message", 0, "您好，我是Sagt，很高兴为您服务"),
        nodeMsg("tag_suggestion", 0, "正在生成客户标签建议…"),
        nodeMsg("human_feedback", 0, "等待您的确认"),
      ],
      result: null, // 标签场景以中断收尾，无最终 task_result
    };
  }
  if (menu === "chat_suggestion" || menu === "kf_chat_suggestion") {
    return {
      nodes: [
        nodeMsg("sagt_welcome_message", 0, "您好，我是Sagt，很高兴为您服务"),
        nodeMsg("load_chat_history_node", 0, "完成聊天消息加载"),
        nodeMsg(menu, 0, "正在生成聊天建议…"),
      ],
      result: taskResult(CHAT_SUGGEST, "三条话术分别覆盖专业/关系/促单策略，点击复制即可发送（演示数据）。"),
    };
  }
  if (menu === "schedule_suggestion") {
    return {
      nodes: [
        nodeMsg("sagt_welcome_message", 0, "您好，我是Sagt，很高兴为您服务"),
        nodeMsg("schedule_suggestion", 0, "正在解析跟进承诺…"),
      ],
      result: taskResult(
        JSON.stringify({
          schedule: "明天 10:00",
          title: "与程总商量筹办酒席（客户承诺到访）",
          source: "聊天记录：「明天上午10点左右，我去你那里找你商量…」",
        }, null, 2),
        "已从会话中识别跟进承诺，确认后自动创建日历（演示数据）。",
      ),
    };
  }
  // 自由聊天 → no_clear_intention 子图
  return {
    nodes: [
      nodeMsg("sagt_welcome_message", 0, "您好，我是Sagt，很高兴为您服务"),
      nodeMsg("intent_detection", 0, "未识别到明确指令，进入咨询模式"),
      nodeMsg("talk_reply_node", 0, "正在生成回复…"),
    ],
    result: taskResult(
      `收到：“${(menu || "").slice(0, 40) || "（空消息）"}”。这是演示环境的固定回复——生产环境中，这里由 DeepAgents 的 talk 子图基于客户画像与会话上下文实时生成。`,
      "试试底部菜单：客户画像 / 聊天建议 / 标签建议（含人工确认）/ 日程建议。",
    ),
  };
}

function streamFrom(script) {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const n of script.nodes) {
          controller.enqueue(sse("values", { node_result: [n] }));
        }
        if (script.result) {
          controller.enqueue(sse("values", { task_result: script.result }));
        }
        controller.close();
      },
    }),
    { headers: sseHeaders },
  );
}

function unauthorized() {
  return new Response(JSON.stringify({ detail: "无效的访问令牌" }), { status: 401, headers: jsonHeaders });
}

export async function onRequest(context) {
  const { request, next } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

  const url = new URL(request.url);
  const path = url.pathname.replace(/^\/api/, "") || "/";

  if (path === "/login" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    if (body.username === DEMO_USER && body.password === DEMO_PASS) {
      return new Response(
        JSON.stringify({ success: true, token: `demo-${Date.now()}`, message: "登录成功（演示环境）" }),
        { headers: jsonHeaders },
      );
    }
    return new Response(JSON.stringify({ success: false, token: "", message: "用户名或密码错误（演示账号 demo / sagt2026）" }), { headers: jsonHeaders });
  }

  // 以下接口要求 Authorization 头存在（值不校验，演示用）
  const auth = request.headers.get("Authorization") || "";
  if (!auth.startsWith("Bearer ")) return unauthorized();

  if (path === "/logout") {
    return new Response(JSON.stringify({ success: true, message: "登出成功" }), { headers: jsonHeaders });
  }

  if (path === "/send_message" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    return streamFrom(buildScript(body.menu_id || body.message));
  }

  if (path === "/get_interrupt") {
    if (!demoState.interruptPending) {
      return new Response(JSON.stringify({ has_interrupt: false, interrupt_info: null }), { headers: jsonHeaders });
    }
    const info = {
      __interrupt__: [
        {
          value: {
            description: "这是帮您生成的客户标签建议，您可以确认、放弃、重新生成。",
            old_tags: { customer_tags: [{ tag_id: "t_old", tag_name: "老客户" }] },
            new_tags: TAGS,
          },
        },
      ],
    };
    return new Response(JSON.stringify({ has_interrupt: true, interrupt_info: info }), { headers: jsonHeaders });
  }

  if (path === "/confirm_interrupt" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    demoState.interruptPending = false;
    const decision = body.confirmed || "ok";
    if (decision === "ok") {
      return streamFrom({
        nodes: [nodeMsg("update_tag", 0, "标签已写入客户档案")],
        result: taskResult(
          JSON.stringify({ applied: TAGS.tag_ids_add.map((t) => t.tag_name) }),
          "3 个标签已确认写入（演示数据）。生产链路此处经 MCP 工具调用 Java 侧 CRM 服务，幂等键防重复写入。",
        ),
      });
    }
    if (decision === "recreate") {
      demoState.interruptPending = true;
      return streamFrom({
        nodes: [nodeMsg("generate_tag", 0, "重新生成中，稍后再次弹出确认")],
        result: null,
      });
    }
    return streamFrom({
      nodes: [nodeMsg("human_feedback", 0, "已放弃本次标签建议")],
      result: taskResult("已放弃，未做任何修改。", "放弃动作会写入审计日志（演示环境略）。"),
    });
  }

  if (path === "/health") {
    return new Response(JSON.stringify({ status: "healthy", mode: "cloudflare-pages-demo" }), { headers: jsonHeaders });
  }

  return next();
}
