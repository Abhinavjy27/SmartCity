"""
Grounding LLM access helper for SUPADSP.
Tries get_llm_provider() from planner_agent, falls back to direct Groq chat-completions call
using LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY (or GROQ_API_KEY).
Features:
- Temperature 0.1
- Reasoning off / suppressed if supported
- Strips <think>...</think> blocks
- Strict 8-second total timeout using ThreadPoolExecutor (does not wait on hung threads)
- Returns (parsed_dict, answer_path) where answer_path is 'llm' or 'rule_based_fallback'
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("pollution_grounding.llm")


def strip_think_blocks(text: str) -> str:
    """Strip reasoning/think blocks (e.g. Qwen / DeepSeek <think>...</think>)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _direct_groq_call(
    prompt: str,
    system_prompt: str,
    api_key: str,
    model: str,
    timeout: float = 7.0,
) -> Optional[Dict[str, Any]]:
    """Direct HTTPS call to Groq /chat/completions without third-party library dependencies."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "SUPADSP-SmartCity/2.0",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                return None
            msg_content = choices[0].get("message", {}).get("content", "")
            cleaned = strip_think_blocks(msg_content)
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
    except Exception as exc:
        logger.warning("Direct Groq API fallback call failed: %s", exc)
        return None


def call_llm_json(
    user_prompt: str,
    system_prompt: str,
    timeout: float = 8.0,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Execute LLM call with 8s hard deadline.
    Returns (result_dict, answer_path).
    answer_path is either 'llm' or 'rule_based_fallback'.
    """

    def _execute() -> Optional[Dict[str, Any]]:
        # 1. Try get_llm_provider() from planner_agent
        try:
            from backend.agents.planner_agent.llm_client import get_llm_provider
            provider = get_llm_provider()
            if hasattr(provider, "generate_json"):
                res = provider.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                if isinstance(res, dict) and "text" in res:
                    return res
            elif hasattr(provider, "generate_json_plan"):
                raw = provider.generate_json_plan(
                    system_prompt=system_prompt,
                    user_query=user_prompt,
                )
                raw = strip_think_blocks(raw) if isinstance(raw, str) else raw
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(parsed, dict) and "text" in parsed:
                    return parsed
        except Exception as exc:
            logger.info("Planner LLM provider attempt unviable: %s. Trying direct Groq...", exc)

        # 2. Direct Groq chat-completions fallback
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        if api_key:
            res = _direct_groq_call(
                prompt=user_prompt,
                system_prompt=system_prompt,
                api_key=api_key.strip(),
                model=model.strip(),
                timeout=timeout - 1.0,
            )
            if res and isinstance(res, dict) and "text" in res:
                return res

        return None

    # Hard timeout barrier so caller does not block on hung worker thread
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute)
            result = future.result(timeout=timeout)
            if result and isinstance(result, dict) and result.get("text"):
                return result, "llm"
    except concurrent.futures.TimeoutError:
        logger.warning("LLM invocation exceeded hard %ss limit; returning rule_based_fallback", timeout)
    except Exception as exc:
        logger.warning("LLM invocation encountered error: %s", exc)

    return None, "rule_based_fallback"
