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


class ClaudeCliProviderTest(unittest.TestCase):
    def _fake_cli(self, body):
        import stat
        import tempfile

        d = tempfile.mkdtemp()
        path = os.path.join(d, "claude")
        with open(path, "w") as f:
            f.write("#!/usr/bin/env python3\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_config_and_command_are_locked_down(self):
        cfg = lp.load_config(secrets(LLM_PROVIDER="claude_cli", LLM_CLAUDE_BIN="/x/claude"))
        self.assertTrue(cfg.is_cli)
        cmd = lp.cli_command(cfg, "claude-haiku-4-5", stream=False)
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertIn("--no-session-persistence", cmd)
        self.assertFalse(lp.is_configured(secrets(LLM_PROVIDER="claude_cli", LLM_CLAUDE_BIN="/nope/claude")))

    def test_complete_uses_stdin_and_drops_api_key(self):
        from unittest import mock

        fake = self._fake_cli(
            "import os, sys\n"
            "print('KEY' if os.environ.get('ANTHROPIC_API_KEY') else 'NOKEY', sys.stdin.read().strip())\n")
        cfg = lp.load_config(secrets(LLM_PROVIDER="claude_cli", LLM_CLAUDE_BIN=fake))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            out = lp.complete([{"type": "text", "text": "hej"}], cfg=cfg)
        self.assertEqual(out, "NOKEY hej")

    def test_stream_parses_partial_messages(self):
        fake = self._fake_cli(
            "import json, sys\nsys.stdin.read()\n"
            "for t in ['Hej ', 'verden']:\n"
            "    print(json.dumps({'type': 'stream_event', 'event': {'type': 'content_block_delta',"
            " 'delta': {'type': 'text_delta', 'text': t}}}))\n"
            "print(json.dumps({'type': 'result', 'result': 'Hej verden'}))\n")
        cfg = lp.load_config(secrets(LLM_PROVIDER="claude_cli", LLM_CLAUDE_BIN=fake))
        seen = []
        self.assertEqual(lp.stream("x", cfg=cfg, on_text=seen.append), "Hej verden")
        self.assertEqual(seen, ["Hej ", "Hej verden"])


class HelpersEnabledTest(unittest.TestCase):
    def test_defaults_and_override(self):
        self.assertTrue(lp.helpers_enabled(secrets(LLM_PROVIDER="gemini", LLM_API_KEY="k")))
        self.assertFalse(lp.helpers_enabled(secrets(LLM_PROVIDER="claude_cli")))
        self.assertTrue(lp.helpers_enabled(secrets(LLM_PROVIDER="claude_cli", LLM_HELPERS="1")))
        self.assertFalse(lp.helpers_enabled(secrets(LLM_PROVIDER="gemini", LLM_API_KEY="k", LLM_HELPERS="0")))


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
