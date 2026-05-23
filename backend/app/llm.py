import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .models import LlmProviderConfig


class LlmConfigurationError(RuntimeError):
    pass


class LlmResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class LlmRuntimeConfig:
    provider: str
    model: str
    base_url: str
    api_key: str
    name: str = "Default"

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


def get_api_key(settings: Settings) -> str:
    api_key = os.getenv(settings.llm_api_key_env_name, "")
    if not api_key:
        raise LlmConfigurationError(f"Missing API key in environment variable {settings.llm_api_key_env_name}.")
    return api_key


def runtime_from_settings(settings: Settings) -> LlmRuntimeConfig:
    return LlmRuntimeConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=get_api_key(settings),
        name="Default .env",
    )


def runtime_from_db(config: LlmProviderConfig) -> LlmRuntimeConfig:
    if not config.api_key:
        raise LlmConfigurationError(f"Missing API key for model config {config.name}.")
    return LlmRuntimeConfig(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
        name=config.name,
    )


async def chat_completion(config: LlmRuntimeConfig, messages: list[dict[str, str]], *, max_tokens: int = 900) -> str:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    url = f"{config.normalized_base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmResponseError("LLM response did not include choices[0].message.") from exc

    content = str(message.get("content") or "").strip()
    if content:
        return content

    finish_reason = choice.get("finish_reason")
    reasoning_content = str(message.get("reasoning_content") or "").strip()
    if reasoning_content and finish_reason == "length":
        raise LlmResponseError(
            "LLM returned reasoning_content but no final content because max_tokens was exhausted. "
            "Use a non-reasoning chat model or increase the model output token budget."
        )
    if reasoning_content:
        raise LlmResponseError("LLM returned reasoning_content but no final content.")
    raise LlmResponseError("LLM returned an empty message content.")


async def test_llm(config: LlmRuntimeConfig) -> str:
    return await chat_completion(
        config,
        [{"role": "user", "content": "Return exactly: TraCN connection OK"}],
        max_tokens=128,
    )


async def extract_profile_summary(config: LlmRuntimeConfig, text: str) -> str:
    prompt = (
        "你是计算神经科学研究生申请匹配助手。请从申请人的 CV 或个人陈述中提取："
        "研究兴趣、方法技能、神经科学主题、AI/建模技能、希望匹配的导师类型。"
        "请用简洁中文输出，不要编造文本中没有的信息。"
    )
    return await chat_completion(
        config,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:16000]},
        ],
    )


async def rank_teachers_with_llm(config: LlmRuntimeConfig, profile_summary: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = (
        "你需要根据申请人画像和导师资料做匹配排序。只返回 JSON 数组，"
        "每个元素包含 teacher_id、ai_score、reason。ai_score 为 0-5 分，reason 用中文一句话说明证据。"
        "不要返回 Markdown，不要返回额外说明。"
    )
    content = json.dumps(
        {"profile_summary": profile_summary, "teachers": candidates},
        ensure_ascii=False,
    )
    raw = await chat_completion(
        config,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content[:18000]},
        ],
        max_tokens=1800,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            raise
        parsed = json.loads(raw[start : end + 1])
    return parsed if isinstance(parsed, list) else []


async def classify_teacher_directions(
    config: LlmRuntimeConfig,
    teacher: dict[str, Any],
    directions: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = (
        "你是计算神经科学导师分类助手。请只根据给定导师资料判断其相关研究方向。"
        "可选择多个方向，但不要为了凑数而选择；必须给出一句可展示的中文证据句。"
        "方向分类规则：如果类脑智能明确解释生物智能机制，应视为更强相关；"
        "如果神经成像涉及机制或理论建模，应视为更强相关。"
        "只返回 JSON 对象，字段为 direction_keys 和 evidence_sentence。"
    )
    raw = await chat_completion(
        config,
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps({"teacher": teacher, "directions": directions}, ensure_ascii=False),
            },
        ],
        max_tokens=2000,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM classification response is not an object.")
    return parsed
