import os
import time
import random
import logging

from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("llm_setting")


class LLMUnavailableError(Exception):
    """所有模型（主力+降级）均不可用。上层节点捕获后走降级话术（FT-001 §4 L2/L3）。"""


# 可重试异常：超时/连接/限流。参数错误、鉴权错误重试无意义，直接降级。
def _retryable(exc: Exception) -> bool:
    name = type(exc).__name__
    return name in {
        "APITimeoutError", "APIConnectionError", "RateLimitError",
        "InternalServerError", "TimeoutError", "ConnectionError", "ServiceUnavailableError",
    }


class ResilientChatModel:
    """弹性模型客户端：超时预算 + 指数退避重试 + 降级模型路由。

    - 与 init_chat_model 产物保持 .invoke(prompt) 兼容，调用点零改动；
    - 重试语义：仅对可重试异常（超时/连接/限流）退避重试，
      不可重试异常立即切换降级模型，避免放大故障（FT-001 §2）；
    - 降级链：primary -> fallback（未配置则跳过）-> LLMUnavailableError；
    - 每次调用结果带 degraded 标记写入返回消息的 response_metadata，
      供上层在 UI 显示"AI 繁忙"横幅与 Langfuse 统计（FT-001 §4）。
    """

    def __init__(self, primary, fallback=None, *,
                 timeout_s: float = 15.0,
                 max_retries: int = 2,
                 base_backoff_s: float = 0.5):
        self.primary = primary
        self.fallback = fallback
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s

    def _invoke_chain(self, prompt, **kwargs):
        models = [("primary", self.primary)]
        if self.fallback is not None:
            models.append(("fallback", self.fallback))

        last_exc = None
        for tier, model in models:
            for attempt in range(self.max_retries + 1):
                try:
                    result = model.invoke(prompt, **kwargs)
                    try:
                        result.response_metadata["sagt_degraded"] = (tier == "fallback")
                    except Exception:
                        pass
                    if tier == "fallback":
                        logger.warning("LLM 降级：使用 fallback 模型完成请求")
                    return result
                except Exception as exc:  # noqa: BLE001 —— 按异常类型分流，不吞栈
                    last_exc = exc
                    if not _retryable(exc):
                        logger.error(f"LLM 不可重试异常({type(exc).__name__})，切换下一档：{exc}")
                        break  # 换 tier，不再浪费退避
                    if attempt < self.max_retries:
                        backoff = self.base_backoff_s * (2 ** attempt) + random.uniform(0, 0.2)
                        logger.warning(f"LLM 第{attempt + 1}次失败({type(exc).__name__})，{backoff:.2f}s 后重试")
                        time.sleep(backoff)
        raise LLMUnavailableError(f"全部模型不可用: {last_exc}") from last_exc

    def invoke(self, prompt, **kwargs):
        return self._invoke_chain(prompt, **kwargs)

    # 兼容部分 langchain 内部路径
    def bind(self, *args, **kwargs):
        return self


def _build_model(model_name: str):
    if not model_name:
        return None
    return init_chat_model(
        model_provider=os.getenv("MODEL_PROVIDER", "openai"),
        model=model_name,
        base_url=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY"),
        timeout=float(os.getenv("LLM_TIMEOUT_S", "15")),
        max_retries=0,  # 重试由 ResilientChatModel 统一管理，禁止 SDK 层重复叠加
        extra_body={
            "thinking": {
                "type": "disabled"
            }
        }
    )


chat_model = ResilientChatModel(
    primary=_build_model(os.getenv("MODEL_NAME")),
    fallback=_build_model(os.getenv("FALLBACK_MODEL_NAME")),
    timeout_s=float(os.getenv("LLM_TIMEOUT_S", "15")),
    max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
)
