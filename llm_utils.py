#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility helpers for LLM calls (temperature compatibility, etc.).
"""
from __future__ import annotations

from typing import Optional, Tuple

TEMPERATURE_UNSUPPORTED_MODELS = {"gpt-5-mini"}


def _normalize_model_name(model: Optional[str]) -> str:
    return (model or "").strip().lower()


def supports_temperature(model: Optional[str]) -> bool:
    """Return True if the model accepts the temperature parameter."""
    return _normalize_model_name(model) not in TEMPERATURE_UNSUPPORTED_MODELS


def _temperature_guideline(desired_temperature: float) -> str:
    """Provide textual guidance to emulate a temperature when it cannot be set."""
    if desired_temperature <= 0.25:
        return (
            "Respond deterministically with minimal stylistic variance. Keep sentences concise, "
            "avoid speculative language, and stay strictly grounded in provided facts."
        )
    if desired_temperature >= 0.85:
        return (
            "Adopt a creative tone, explore multiple alternatives, and surface non-obvious insights. "
            "Offer at least two contrasting options whenever relevant."
        )
    return (
        "Balance precision and creativity. Provide structured answers while adding one or two "
        "supplementary ideas to show moderate exploration without losing clarity."
    )


def apply_temperature_strategy(
    model: Optional[str],
    system_prompt: str,
    desired_temperature: float,
) -> Tuple[str, Optional[float]]:
    """
    Adjust prompts/parameters to match temperature intent.

    Returns the (possibly augmented) system prompt and an optional temperature value.
    """
    if supports_temperature(model):
        return system_prompt, desired_temperature

    directive = (
        "## Variability Directive\n"
        f"The current model ({model}) ignores the temperature parameter. "
        f"Simulate temperature={desired_temperature:.2f} using this guidance:\n"
        f"{_temperature_guideline(desired_temperature)}"
    )
    combined_prompt = (
        f"{system_prompt.rstrip()}\n\n{directive}" if system_prompt.strip() else directive
    )
    return combined_prompt, None


