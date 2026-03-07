import os
import tempfile
import unittest

from guiagent_v2.blueprint_hub import Blueprint, BlueprintPatch, BlueprintRepository


class TestBlueprintHub(unittest.TestCase):
    def test_save_get_apply_patch(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "blueprints.json")
            repo = BlueprintRepository(path)

            bp = Blueprint(
                intent_key="global:TAP:SEARCH_BAR",
                app_state="global:DEFAULT",
                version="v0.1.0",
                reference_screen={"width": 1080, "height": 2340},
            )
            repo.save_blueprint(bp)
            found = repo.get_blueprint("global:TAP:SEARCH_BAR", "global:DEFAULT")
            self.assertIsNotNone(found)
            self.assertEqual(found["version"], "v0.1.0")

            patch = BlueprintPatch(
                target_intent_key="global:TAP:SEARCH_BAR",
                target_state="global:DEFAULT",
                version="v0.1.1",
                delta={"post_expectations": ["KEYBOARD_VISIBLE"]},
            )
            result = repo.apply_patch(patch)
            self.assertEqual(result["status"], "SUCCESS")
            found2 = repo.get_blueprint("global:TAP:SEARCH_BAR", "global:DEFAULT")
            self.assertEqual(found2["version"], "v0.1.1")
            self.assertEqual(found2["post_expectations"], ["KEYBOARD_VISIBLE"])


if __name__ == "__main__":
    unittest.main()

