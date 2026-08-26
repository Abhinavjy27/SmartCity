"""
LLM Client Wrapper for the Planner Agent.
Interfaces with Groq Cloud API to execute structured JSON completions for models like Qwen 2.5 and Llama 3.3.
"""

from __future__ import annotations

import os
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
load_dotenv()

DEFAULT_MODEL = os.getenv("PLANNER_LLM_MODEL", "qwen/qwen3.8-27b")


class LLMClient:
    """Wrapper class for LLM completion requests."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Please add GROQ_API_KEY to your .env file."
            )
        self.model = model or os.getenv("PLANNER_LLM_MODEL", DEFAULT_MODEL)
        self._client = None

    def _get_client(self):
        """Lazy initialization of Groq client."""
        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except ImportError as exc:
                raise RuntimeError(
                    "The 'groq' package is required. Install it with 'pip install groq'."
                ) from exc
        return self._client

    def generate_json_plan(
        self,
        system_prompt: str,
        user_query: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send system prompt and user query to the LLM and return raw JSON string response.
        """
        client = self._get_client()

        try:
            chat_completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )

            raw_text = chat_completion.choices[0].message.content
            if not raw_text or not raw_text.strip():
                raise RuntimeError("LLM returned an empty response.")

            return raw_text.strip()
        except Exception as exc:
            # Fallback models available on current Groq instance
            fallback_models = ["qwen/qwen3.6-27b", "groq/compound", "openai/gpt-oss-120b"]
            for fallback in fallback_models:
                if fallback != self.model:
                    try:
                        fallback_completion = client.chat.completions.create(
                            model=fallback,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_query},
                            ],
                            response_format={"type": "json_object"},
                            temperature=temperature,
                            max_tokens=max_tokens,
                        )
                        raw_text = fallback_completion.choices[0].message.content
                        if raw_text and raw_text.strip():
                            return raw_text.strip()
                    except Exception:
                        continue

            raise RuntimeError(f"LLM generation failed: {str(exc)}") from exc


# Default global instance
default_llm_client = LLMClient
