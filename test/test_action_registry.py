import unittest

from guiagent_v2.runtime.action_registry import ActionRegistry


class TestActionRegistry(unittest.TestCase):
    def test_register_validate_dispatch(self):
        registry = ActionRegistry()

        def handler(payload, context):
            return {"ok": True, "payload": payload, "context": context}

        registry.register(
            "demo_action",
            schema={
                "required": ["name"],
                "field_types": {"name": "str"},
            },
            handler=handler,
        )

        valid, detail = registry.validate("demo_action", {"name": "abc"})
        self.assertTrue(valid)
        self.assertEqual(detail["reason"], "OK")

        result = registry.dispatch("demo_action", {"name": "abc"}, {"source": "ut"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["payload"]["name"], "abc")

    def test_validate_missing_field(self):
        registry = ActionRegistry()
        registry.register("x", schema={"required": ["a"]}, handler=lambda p, c: {"ok": True})

        valid, detail = registry.validate("x", {})
        self.assertFalse(valid)
        self.assertEqual(detail["reason"], "MISSING_FIELD")

    def test_dispatch_invalid_payload_raises(self):
        registry = ActionRegistry()
        registry.register("x", schema={"required": ["a"]}, handler=lambda p, c: {"ok": True})
        with self.assertRaises(ValueError):
            registry.dispatch("x", {})


if __name__ == "__main__":
    unittest.main()
