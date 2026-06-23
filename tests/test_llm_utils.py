from llm_utils import apply_temperature_strategy, supports_temperature


def test_standard_models_support_temperature():
    for model in ("gpt-4o", "gpt-4", "gpt-5", "claude-sonnet-4-6"):
        assert supports_temperature(model) is True, model


def test_reasoning_models_do_not_support_temperature():
    # The o1 / o3 / o4 reasoning families (and their -mini / -preview variants)
    # reject the temperature parameter — passing it errors at the API.
    for model in ("o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o4-mini"):
        assert supports_temperature(model) is False, model


def test_gpt_5_mini_still_unsupported():
    assert supports_temperature("gpt-5-mini") is False


def test_vendor_prefix_is_stripped_before_checking_family():
    assert supports_temperature("openai/o1-mini") is False
    assert supports_temperature("OpenAI/GPT-4o") is True


def test_lookalike_names_are_not_misclassified():
    # A name that merely starts with the letters "o1" but isn't the o1 family
    # (no boundary) must still be treated as supporting temperature.
    assert supports_temperature("o1ama") is True


def test_apply_strategy_passes_temperature_through_for_supported_model():
    prompt, temperature = apply_temperature_strategy("gpt-4o", "You are helpful.", 0.7)
    assert prompt == "You are helpful."
    assert temperature == 0.7


def test_apply_strategy_emulates_temperature_for_reasoning_model():
    prompt, temperature = apply_temperature_strategy("o1-mini", "You are helpful.", 0.7)
    # No temperature is sent; the intent is folded into the prompt instead.
    assert temperature is None
    assert "You are helpful." in prompt
    assert "Variability Directive" in prompt
