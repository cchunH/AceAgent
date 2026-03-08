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

    def test_match_by_skeleton(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "blueprints.json")
            repo = BlueprintRepository(path)
            repo.save_blueprint(
                {
                    "intent_key": "global:TAP:SEARCH_BAR",
                    "app_state": "global:DEFAULT",
                    "version": "v0.1.0",
                    "anchors": [],
                    "static_skeleton": {
                        "signature": "sig-a",
                        "nodes": [
                            {
                                "type": "TEXT",
                                "text": "Search",
                                "zone": "top",
                                "norm_bbox": {"x": 0.5, "y": 0.08, "w": 0.0, "h": 0.0},
                            }
                        ],
                    },
                }
            )
            matched = repo.match_by_skeleton(
                {
                    "signature": "sig-a",
                    "nodes": [
                        {
                            "type": "TEXT",
                            "text": "Search",
                            "zone": "top",
                            "norm_bbox": {"x": 0.49, "y": 0.09, "w": 0.0, "h": 0.0},
                        }
                    ],
                },
                app_state="global:DEFAULT",
                top_k=1,
            )
            self.assertTrue(matched)
            self.assertEqual(matched[0]["intent_key"], "global:TAP:SEARCH_BAR")

    def test_match_by_vector(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "blueprints.json")
            repo = BlueprintRepository(path)
            repo.save_blueprint(
                Blueprint(
                    intent_key="global:TAP:SEARCH_BAR",
                    app_state="global:DEFAULT",
                    anchors=[{"text": "Search", "x": 0.5, "y": 0.05}],
                    post_expectations=["Results"],
                )
            )
            repo.save_blueprint(
                Blueprint(
                    intent_key="global:TAP:SETTINGS",
                    app_state="global:DEFAULT",
                    anchors=[{"text": "Settings", "x": 0.2, "y": 0.2}],
                    post_expectations=["Settings"],
                )
            )
            repo.rebuild_vector_index(app_state="global:DEFAULT")
            matched = repo.match_by_vector("tap search input and open results", app_state="global:DEFAULT", top_k=1)
            self.assertTrue(matched)
            self.assertEqual(matched[0]["app_state"], "global:DEFAULT")
            self.assertIn("intent_key", matched[0])
            self.assertGreaterEqual(matched[0]["score"], 0.4)

    def test_vector_backend_can_be_configured(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "blueprints.json")

            def _embed(text: str, dim: int) -> list[float]:
                token = str(text).lower()
                vec = [0.0 for _ in range(max(1, int(dim)))]
                if "settings" in token:
                    vec[0] = 1.0
                elif "search" in token:
                    vec[1] = 1.0
                else:
                    vec[2] = 1.0
                return vec

            repo = BlueprintRepository(path)
            before = repo.get_vector_backend_info()
            self.assertEqual(before["source"], "vector_mock")
            self.assertEqual(before["embedding_dim"], 32)

            repo.configure_vector_backend(embedding_fn=_embed, embedding_dim=4, rebuild=False)
            after = repo.get_vector_backend_info()
            self.assertEqual(after["embedding_dim"], 4)
            self.assertFalse(after["ready"])

            repo.save_blueprint(
                Blueprint(
                    intent_key="global:TAP:SEARCH_BAR",
                    app_state="global:DEFAULT",
                    anchors=[{"text": "Search", "x": 0.5, "y": 0.05}],
                )
            )
            repo.save_blueprint(
                Blueprint(
                    intent_key="global:TAP:SETTINGS",
                    app_state="global:DEFAULT",
                    anchors=[{"text": "Settings", "x": 0.2, "y": 0.2}],
                )
            )
            repo.rebuild_vector_index(app_state="global:DEFAULT")
            matched = repo.match_by_vector("open settings", app_state="global:DEFAULT", top_k=1)
            self.assertTrue(matched)
            self.assertEqual(matched[0]["intent_key"], "global:TAP:SETTINGS")


if __name__ == "__main__":
    unittest.main()
