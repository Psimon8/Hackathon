"""
Unified OpenAI client with retry and backoff.
Used by Fanout, EEAT Enhancer, and Semantic Score refinement.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
import httpx

from core.credentials import get_credentials

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Centralized OpenAI GPT client."""

    def __init__(self, model: str = "gpt-4o-mini", max_retries: int = 2):
        creds = get_credentials()
        self.api_key = creds.openai_api_key
        self.model = model
        self.max_retries = max_retries
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            http_client = httpx.Client(timeout=60.0)
            self._client = OpenAI(api_key=self.api_key, http_client=http_client)
        return self._client

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 3000,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Send a chat completion request with retry."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"OpenAI API error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        return None

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ) -> Optional[Dict]:
        """Chat and parse JSON response."""
        raw = self.chat(system_prompt, user_prompt, temperature, max_tokens, json_mode=True)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw.replace("```json", "").replace("```", "").strip()
            elif raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                return None
