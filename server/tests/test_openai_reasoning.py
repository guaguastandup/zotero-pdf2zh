import unittest

from utils.openai_reasoning import supports_none, validate_openai_none


class OpenAIReasoningTests(unittest.TestCase):
    def test_verified_families_accept_none(self):
        for model in (
            "gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.4-mini",
            "gpt-5.5", "gpt-5.6", "gpt-5.6-terra", "gpt-6-sol",
            "gpt-6-luna", "gpt-6.1-terra", "gpt-5.4-2026-03-05",
        ):
            with self.subTest(model=model):
                self.assertTrue(supports_none(model))

    def test_unverified_models_reject_none(self):
        for model in (
            "gpt-5", "gpt-5-mini", "gpt-6-astra", "gpt-6.1-sol",
            "o3", "gpt-4o", "gpt-7", "", "gpt-5.5-pro",
        ):
            with self.subTest(model=model):
                self.assertFalse(supports_none(model))
                with self.assertRaisesRegex(ValueError, "发送前停止"):
                    validate_openai_none({
                        "model": model,
                        "extraData": {
                            "openai_reasoning_effort": "none",
                            "openai_send_reasoning_effort": "true",
                        },
                    }, {})

    def test_only_explicit_send_is_checked(self):
        for flag in ("false", False, "", None):
            validate_openai_none({
                "model": "gpt-6-astra",
                "extraData": {
                    "openai_reasoning_effort": "none",
                    "openai_send_reasoning_effort": flag,
                },
            }, {})

    def test_real_upstream_2_9_0_settings_accept_none_without_network(self):
        try:
            from pdf2zh_next.config.translate_engine_model import OpenAISettings
        except ImportError as exc:
            self.skipTest(f"upstream test wheel missing: {exc}")

        options = OpenAISettings(
            openai_model="gpt-5.4",
            openai_api_key="unit-test-no-network",
            openai_reasoning_effort="none",
            openai_send_reasoning_effort=True,
        )
        options.validate_settings()
        self.assertEqual(options.openai_reasoning_effort, "none")
        self.assertTrue(options.openai_send_reasoning_effort)

    def test_saved_model_and_other_efforts(self):
        validate_openai_none({
            "extraData": {
                "openai_reasoning_effort": "none",
                "openai_send_reasoning_effort": True,
            },
        }, {"openai_detail": {"openai_model": "gpt-5.4"}})
        validate_openai_none({"model": "gpt-5", "extraData": {}}, {})
        validate_openai_none({"model": "gpt-5", "extraData": {
            "openai_reasoning_effort": "medium",
            "openai_send_reasoning_effort": True,
        }}, {})


if __name__ == "__main__":
    unittest.main()
