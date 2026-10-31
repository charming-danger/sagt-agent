# -*- coding: utf-8 -*-
"""ResilientChatModel 弹性策略单测：重试/降级/不可重试分流/全挂异常。"""
import pytest

from langchain_core.messages import AIMessage
from llm.llm_setting import ResilientChatModel, LLMUnavailableError


class FakeModel:
    """按脚本依次抛异常/返回消息。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def invoke(self, prompt, **kw):
        self.calls += 1
        item = self.script.pop(0) if self.script else AIMessage(content="default")
        if isinstance(item, Exception):
            raise item
        return AIMessage(content=item, response_metadata={})


class TimeoutErr(Exception):
    pass


TimeoutErr.__name__ = "APITimeoutError"  # 命中 _retryable 名单


class AuthErr(Exception):
    pass


AuthErr.__name__ = "AuthenticationError"  # 不可重试


def _model(**kw):
    kw.setdefault("base_backoff_s", 0.001)  # 测试不真睡觉
    return ResilientChatModel(**kw)


def test_success_first_try():
    m = _model(primary=FakeModel(["ok"]))
    r = m.invoke("p")
    assert r.content == "ok"
    assert r.response_metadata["sagt_degraded"] is False


def test_retry_then_success():
    m = _model(primary=FakeModel([TimeoutErr(), "ok2"]), max_retries=2)
    r = m.invoke("p")
    assert r.content == "ok2"


def test_retries_exhausted_falls_back():
    prim = FakeModel([TimeoutErr(), TimeoutErr(), TimeoutErr()])
    fb = FakeModel(["fb-ok"])
    m = _model(primary=prim, fallback=fb, max_retries=2)
    r = m.invoke("p")
    assert r.content == "fb-ok"
    assert r.response_metadata["sagt_degraded"] is True
    assert prim.calls == 3  # 1 + 2 retries


def test_non_retryable_skips_retries_and_degrades():
    prim = FakeModel([AuthErr()])
    fb = FakeModel(["fb2"])
    m = _model(primary=prim, fallback=fb, max_retries=2)
    r = m.invoke("p")
    assert r.content == "fb2"
    assert prim.calls == 1  # 不可重试 → 不叠加退避，立即降级


def test_all_tiers_down_raises_unavailable():
    prim = FakeModel([TimeoutErr(), TimeoutErr(), TimeoutErr()])
    fb = FakeModel([TimeoutErr(), TimeoutErr(), TimeoutErr()])
    m = _model(primary=prim, fallback=fb, max_retries=2)
    with pytest.raises(LLMUnavailableError):
        m.invoke("p")


def test_no_fallback_configured():
    prim = FakeModel(["only"])
    m = _model(primary=prim)
    assert m.invoke("p").content == "only"
