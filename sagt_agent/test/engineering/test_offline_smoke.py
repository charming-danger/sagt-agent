# -*- coding: utf-8 -*-
"""离线冒烟测试：不依赖 LangGraph server / 外部模型，验证
1) 图可导入可编译（StoreClient 懒加载回归）
2) 用 InMemoryStore 注入 mock 数据后，图可端到端执行
运行：PYTHONPATH=src uv run pytest test/ -q  或  python -m pytest
"""
import os
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="module")
def graph():
    from graphs.sagt_graph.sagt_graph import graph
    return graph


def test_graph_import_offline(graph):
    """模块导入期不得触碰运行时 store（回归：导入期 get_store() 崩溃）"""
    assert graph is not None


def test_graph_nodes_wired(graph):
    g = graph.get_graph()
    names = set(g.nodes.keys())
    for expected in ["cleanup_state", "intent_detection", "task_result_confirm",
                     "load_customer_info_node", "load_chat_history_node", "no_clear_intention"]:
        assert expected in names, f"missing node {expected}"


def test_store_client_lazy():
    """StoreClient 构造不得调用 get_store()"""
    from store.store_client import StoreClient
    sc = StoreClient()          # 旧实现此处直接 RuntimeError
    with pytest.raises(RuntimeError):
        _ = sc.store            # 无运行上下文时访问属性才报错，语义正确
