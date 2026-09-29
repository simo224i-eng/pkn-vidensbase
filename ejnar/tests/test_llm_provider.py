import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_provider as lp


def secrets(**values):
    return lambda name: values.get(name, "")


class LLMProviderTest(unittest.TestCase):
    def test_default_is_anthropic(self):
        cfg = lp.load_config(secrets(ANTHROPIC_API_KEY="k"))
        self.assertTrue(cfg.is_anthropic)
        self.assertEqual(cfg.resolve_model("claude-haiku-4-5-20251001"), lp.ANTHROPIC_FAST)
        self.assertEqual(cfg.resolve_model("claude-sonnet-4-6"), lp.ANTHROPIC_MAIN)

    def test_preset_maps_fast_and_main(self):
        cfg = lp.load_config(secrets(LLM_PROVIDER="gemini", GEMINI_API_KEY="g"))
        self.assertEqual(cfg.api_key, "g")
        self.assertEqual(cfg.resolve_model("claude-haiku-4-5-20251001"), "gemini-2.5-flash-lite")
        self.assertEqual(cfg.resolve_model("claude-sonnet-4-6"), "gemini-2.5-flash")

    def test_openai_compatible_request_flattens_cache_blocks(self):
        cfg = lp.load_config(secrets(
            LLM_PROVIDER="openai_compatible", LLM_API_KEY="x",
            LLM_BASE_URL="http://localhost:11434/v1/", LLM_MODEL="qwen",
        ))
        prompt = [{"type": "text", "text": "A", "cache_control": {"type": "ephemeral"}},
                  {"type": "text", "text": "B"}]
        url, headers, body = lp.build_request(cfg, prompt, 100, "claude-haiku", stream=True)
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer x")
        self.assertEqual(body["model"], "qwen")
        self.assertEqual(body["messages"][0]["content"], "A\n\nB")
        self.assertTrue(body["stream"])

    def test_extract_text_and_delta(self):
        oa = lp.load_config(secrets(LLM_PROVIDER="deepseek", LLM_API_KEY="d"))
        self.assertEqual(lp.extract_text(oa, {"choices": [{"message": {"content": "hej"}}]}), "hej")
        self.assertEqual(lp.extract_delta(oa, {"choices": [{"delta": {"content": "h"}}]}), "h")
        an = lp.load_config(secrets(ANTHROPIC_API_KEY="k"))
        self.assertEqual(lp.extract_text(an, {"content": [{"type": "text", "text": "hej"}]}), "hej")
        self.assertEqual(lp.extract_delta(an, {"type": "content_block_delta", "delta": {"text": "h"}}), "h")

    def test_configuration_checks(self):
        self.assertFalse(lp.is_configured(secrets()))
        self.assertFalse(lp.is_configured(secrets(LLM_PROVIDER="nope", LLM_API_KEY="x")))
        self.assertFalse(lp.is_configured(secrets(LLM_PROVIDER="openai_compatible", LLM_API_KEY="x")))
        self.assertTrue(lp.is_configured(secrets(LLM_PROVIDER="deepseek", DEEPSEEK_API_KEY="d")))


class SharedHelperTest(unittest.TestCase):
    def test_helper_calls_get_empty_string_without_llm(self):
        # Fejlteksten til brugeren må aldrig ende i query-udvidelse/HyDE/rerank.
        from unittest import mock
        import shared

        with mock.patch.object(shared._llm_provider, "is_configured", return_value=False), \
             mock.patch.object(shared._llm_provider, "complete", side_effect=AssertionError("kaldt")):
            self.assertEqual(shared._llm_haiku("udvid"), "")
            self.assertIn("LLM", shared._llm("svar"))


if __name__ == "__main__":
    unittest.main()
