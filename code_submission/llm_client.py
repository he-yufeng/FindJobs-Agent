#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from llm_utils import apply_temperature_strategy

try:
    # reuse key manager if available
    from tag_rate import APIKeyManager, load_api_keys
except Exception:
    APIKeyManager = None  # type: ignore
    load_api_keys = None  # type: ignore

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = ROOT_DIR / "llm_config.json"
DEFAULT_API_KEY_FILE = ROOT_DIR / "API_key-openai.md"

DEFAULTS = {
    "provider": "openai",  # or "deepseek"
    "model": "gpt-5-mini",
    "api_url_openai": "https://api.openai.com/v1/chat/completions",
    "api_url_deepseek": "https://api.deepseek.com/v1/chat/completions",
    "timeout": 120,
    "max_retry": 3,
    "temperature": 0.7,
}


def load_llm_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if DEFAULT_CONFIG_FILE.exists():
        try:
            cfg = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning(f"无法解析 llm_config.json，使用默认配置: {e}")
    # env overrides
    provider = os.getenv("LLM_PROVIDER", cfg.get("provider", DEFAULTS["provider"]))
    model = os.getenv("LLM_MODEL", cfg.get("model", DEFAULTS["model"]))
    api_url = os.getenv("LLM_API_URL")  # optional
    timeout = int(os.getenv("LLM_TIMEOUT_S", str(cfg.get("timeout", DEFAULTS["timeout"]))))
    max_retry = int(os.getenv("LLM_MAX_RETRY", str(cfg.get("max_retry", DEFAULTS["max_retry"]))))
    temperature = float(os.getenv("LLM_TEMPERATURE", str(cfg.get("temperature", DEFAULTS["temperature"]))))
    return {
        "provider": provider,
        "model": model,
        "api_url": api_url,
        "timeout": timeout,
        "max_retry": max_retry,
        "temperature": temperature,
    }


class LLMClient:
    """
    Unified LLM client supporting multiple providers (OpenAI, DeepSeek).
    - Rotates API keys using tag_rate.APIKeyManager if available
    - Supports response_format={"type": "json_object"}
    """
    def __init__(
        self,
        api_key_manager: Optional["APIKeyManager"] = None,
        override: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.cfg = load_llm_config()
        if override:
            self.cfg.update({k: v for k, v in override.items() if v is not None})

        self.provider: str = self.cfg["provider"]
        self.model: str = self.cfg["model"]
        self.timeout: int = self.cfg["timeout"]
        self.max_retry: int = self.cfg["max_retry"]
        self.temperature: float = self.cfg["temperature"]
        self.api_key_manager = api_key_manager or self._maybe_build_key_manager()

        # Resolve API URL
        if self.cfg.get("api_url"):
            self.api_url = self.cfg["api_url"]
        else:
            if self.provider.lower() == "deepseek":
                self.api_url = DEFAULTS["api_url_deepseek"]
            else:
                self.api_url = DEFAULTS["api_url_openai"]

    def _maybe_build_key_manager(self) -> Optional["APIKeyManager"]:
        if APIKeyManager is None or load_api_keys is None:
            return None
        # Default to API_key-openai.md in project root
        key_file = DEFAULT_API_KEY_FILE
        try:
            api_keys = load_api_keys(key_file)
            return APIKeyManager(api_keys)
        except Exception as e:
            logging.warning(f"无法从 {key_file} 加载API Key: {e}")
            return None

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> str:
        target_temperature = self.temperature if temperature is None else temperature
        adjusted_system_prompt, temp_param = apply_temperature_strategy(
            self.model, system_prompt, target_temperature
        )
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": adjusted_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if temp_param is not None:
            body["temperature"] = temp_param
        if response_format:
            body["response_format"] = response_format

        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retry + 1):
            api_key = None
            if self.api_key_manager:
                api_key = self.api_key_manager.get_key()
            else:
                # fallback to env
                api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY", "")
            try:
                resp = requests.post(
                    self.api_url,
                    headers=self._headers(api_key),
                    json=body,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if content:
                    return content
                raise ValueError("LLM 响应为空或缺少 content。")
            except Exception as e:
                last_err = e
                logging.warning(f"LLM调用失败（{self.provider}, 第{attempt}/{self.max_retry}次）: {e}")
                if attempt < self.max_retry:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 多次重试后仍失败: {last_err}")


