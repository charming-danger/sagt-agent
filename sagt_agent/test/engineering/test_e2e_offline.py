# -*- coding: utf-8 -*-
"""端到端离线测试：不依赖 LangGraph server、不依赖真实模型。

手法：monkeypatch 数据加载函数与 LLM 客户端，验证
1) 并行 fan-out/fan-in 拓扑可完整执行
2) NODE_RESULT reducer 在并行分支下正确合并（不丢、不覆盖）
3) 意图路由（menu 直达 / 未明确意图→sub_talk）行为正确
"""
import pytest
from langchain_core.messages import AIMessage


@pytest.fixture()
def patched(monkeypatch):
    """替换所有外部依赖（store/LLM），返回可断言的桩数据。"""
    import graphs.sagt_graph.sagt_node_load_data as load_mod
    import graphs.sagt_graph.sagt_node as node_mod
    from models.sagt_models import (EmployeeInfo, CustomerInfo, CustomerProfile,
                                    CustomerTags, TagSetting, ChatHistory,
                                    KFChatHistory, OrderHistory)

    def fake_employee(user_id=None, **kw):
        return EmployeeInfo(user_id=user_id or "xiaocheng", name="小明")

    def fake_customer(external_id=None, follow_user_id=None, **kw):
        return CustomerInfo(external_id=external_id, union_id="union_123",
                            follow_user_id=follow_user_id, nick_name="程哥")

    def fake_profile(external_id=None, follow_user_id=None, **kw):
        return CustomerProfile()

    def fake_tags(external_id=None, follow_user_id=None, **kw):
        return CustomerTags()

    def fake_tag_setting(**kw):
        return TagSetting()

    def fake_chat(external_id=None, follow_user_id=None, **kw):
        return ChatHistory()

    def fake_kf(external_id=None, **kw):
        return KFChatHistory()

    def fake_order(union_id=None, **kw):
        return OrderHistory()

    for name, fn in {
        "get_employee_info": fake_employee, "get_customer_info": fake_customer,
        "get_customer_profile": fake_profile, "get_customer_tags": fake_tags,
        "get_tag_setting": fake_tag_setting, "get_chat_history": fake_chat,
        "get_kf_history": fake_kf, "get_order_history": fake_order,
    }.items():
        monkeypatch.setattr(load_mod, name, fn)

    # 假 LLM：just_talk 路径返回合法 JSON
    import llm.llm_just_talk as talk_mod
    class FakeLLM:
        def invoke(self, prompt):
            return AIMessage(content='{"just_talk_output": "你好，我是Sagt测试回复"}')
    monkeypatch.setattr(talk_mod, "llm", FakeLLM())
    return load_mod


def _run(graph, task_input):
    return graph.invoke(
        {"task_input": task_input},
        {"configurable": {"user_id": "xiaocheng",
                          "external_id": "wmE8gRKQAArnVDJ84bNuOK3KVjy_7-Wg"}},
    )


def test_e2e_no_clear_intention(patched):
    from graphs.sagt_graph.sagt_graph import graph
    out = _run(graph, "随便聊聊")
    assert out["task_result"].task_result_code == 0
    assert "Sagt测试回复" in out["task_result"].task_result
    node_names = {r.execute_node_name for r in out["node_result"]}
    # 5 个并行加载节点的结果都必须被 reducer 合并进来，一个不能少
    for n in ["load_employee_info_node", "load_tag_setting_node",
              "load_customer_info_node", "load_chat_history_node",
              "load_kf_chat_history_node"]:
        assert n in node_names, f"reducer 丢失并行分支结果: {n}"
    assert "load_order_history_node" in node_names  # fan-in 前依赖 customer 完成


def test_e2e_cleanup_resets_node_result(patched):
    """第二次运行不得残留第一次的 node_result（cleanup 节点 + reducer 空列表语义）"""
    from graphs.sagt_graph.sagt_graph import graph
    out1 = _run(graph, "随便聊聊")
    out2 = _run(graph, "随便聊聊")
    assert len(out2["node_result"]) == len(out1["node_result"])


def test_talk_empty_output_no_secondary_crash(monkeypatch):
    """回归 K3：模型空输出分支曾因 f-string 引用未定义的 e 抛 NameError 二次崩溃"""
    import graphs.sagt_graph.sagt_sub_graph_talk.sub_talk_graph as st
    import llm.llm_just_talk as talk
    from langchain_core.messages import AIMessage

    class EmptyLLM:
        def invoke(self, prompt):
            return AIMessage(content="")

    monkeypatch.setattr(talk, "llm", EmptyLLM())
    out = st.just_talk_node({"task_input": "hi"}, {})
    assert out["task_result"].task_result_code == 1
    assert out["node_result"][0].execute_exceptions == ["模型返回内容为空"]


def _fake_store_msgs():
    return [{"from_id": "u1", "content": "真实消息", "msg_time": 1767240000}]


def test_demo_mode_off_no_injected_messages(monkeypatch):
    """回归 K2：默认（生产）路径不得注入演示假消息"""
    import tools.store_tool as tool_mod
    monkeypatch.setenv("SAGT_DEMO_MODE", "false")
    monkeypatch.setattr(tool_mod.store_client, "list_last_wxqy_msg",
                        lambda *a, **k: _fake_store_msgs())
    hist = tool_mod.get_chat_history("ext1", "u1")
    assert [m.content for m in hist.chat_msgs] == ["真实消息"]


def test_demo_mode_on_injects_messages(monkeypatch):
    """演示模式显式开启时才注入（课程日程场景依赖这两条）"""
    import tools.store_tool as tool_mod
    monkeypatch.setenv("SAGT_DEMO_MODE", "true")
    monkeypatch.setattr(tool_mod.store_client, "list_last_wxqy_msg",
                        lambda *a, **k: _fake_store_msgs())
    hist = tool_mod.get_chat_history("ext1", "u1")
    assert len(hist.chat_msgs) == 3
    assert "酒席" in hist.chat_msgs[-1].content


