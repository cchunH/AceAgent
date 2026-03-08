import tempfile
import unittest
from unittest.mock import patch

from guiagent_v2.retrieval import InMemoryVectorIndex
from guiagent_v2.runtime.orchestrator_v2 import (
    _split_instruction_into_steps,
    run_single_task_with_runtime,
)
from guiagent_v2.runtime.v2_executor import V2ProbeResult


class _DummyPerceptor:
    @staticmethod
    def to_dict():
        return {}


class _DummyModels:
    DEFAULT = "ut-model"
    perceptor = _DummyPerceptor()


class _DummyPaths:
    ADB_PATH = "adb"
    SCREENSHOT_DIR = "screenshot"
    TEMP_DIR = "temp"


class _DummyConfig:
    models = _DummyModels()
    paths = _DummyPaths()


class _DummyLivePerceptor:
    def get_perception_infos(self, screenshot_file, temp_file=None):  # noqa: ANN001
        del screenshot_file, temp_file
        return [{"text": "live-pre", "coordinates": [11, 22]}], 720, 1280


def _vector_plugin_factory():
    def _embed(text: str, dim: int):
        vec = [0.0 for _ in range(max(1, int(dim)))]
        token = str(text).lower()
        if "settings" in token:
            vec[0] = 1.0
        else:
            vec[-1] = 1.0
        return vec

    return {
        "vector_index": InMemoryVectorIndex(),
        "embedding_fn": _embed,
        "source": "vector_plugin_ut",
    }


class TestOrchestratorV2Loop(unittest.TestCase):
    def test_split_instruction_into_steps(self):
        steps = _split_instruction_into_steps(
            "先打开设置，然后返回主页；接着等待一下。最后回到桌面",
            max_steps=6,
        )
        self.assertGreaterEqual(len(steps), 3)
        self.assertEqual(steps[0], "先打开设置")

    def test_v2_skip_legacy_runs_multi_steps_with_cap(self):
        calls = []

        def _fake_probe(**kwargs):
            calls.append(dict(kwargs))
            return V2ProbeResult(
                status="SUCCESS",
                intent_key=f"global:STEP:{kwargs['step_id']}",
                channel="mobile_native",
                route_reason="ut",
            )

        with tempfile.TemporaryDirectory() as td:
            with (
                patch("guiagent_v2.runtime.orchestrator_v2._load_runtime_config", return_value=_DummyConfig()),
                patch("guiagent_v2.runtime.orchestrator_v2.run_probe_step", side_effect=_fake_probe),
                patch(
                    "guiagent_v2.runtime.orchestrator_v2._emit_events_from_legacy_steps",
                    side_effect=AssertionError("legacy should not be called when v2_skip_legacy=true"),
                ),
            ):
                out = run_single_task_with_runtime(
                    instruction="先打开设置，然后返回，再等待，最后回到桌面",
                    run_name="ut-loop",
                    task_id="t-cap",
                    log_root=td,
                    runtime_mode="guiagent_v2",
                    v2_skip_legacy=True,
                    v2_max_steps=2,
                    mobile_execution_mode="shadow",
                )

        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(len(calls), 2)
        self.assertEqual([item["step_id"] for item in calls], [1, 2])
        self.assertTrue(all(item.get("perception_provider") is None for item in calls))

    def test_v2_skip_legacy_stops_on_handover(self):
        calls = []

        def _fake_probe(**kwargs):
            calls.append(dict(kwargs))
            status = "HANDOVER" if int(kwargs["step_id"]) == 2 else "SUCCESS"
            return V2ProbeResult(
                status=status,
                intent_key=f"global:STEP:{kwargs['step_id']}",
                channel="mobile_native",
                route_reason="ut",
            )

        with tempfile.TemporaryDirectory() as td:
            with (
                patch("guiagent_v2.runtime.orchestrator_v2._load_runtime_config", return_value=_DummyConfig()),
                patch("guiagent_v2.runtime.orchestrator_v2.run_probe_step", side_effect=_fake_probe),
            ):
                out = run_single_task_with_runtime(
                    instruction="第一步，然后第二步，然后第三步",
                    run_name="ut-loop",
                    task_id="t-stop",
                    log_root=td,
                    runtime_mode="guiagent_v2",
                    v2_skip_legacy=True,
                    v2_max_steps=5,
                    mobile_execution_mode="shadow",
                )

        self.assertEqual(out["status"], "HANDOVER")
        self.assertEqual(len(calls), 2)
        self.assertEqual([item["step_id"] for item in calls], [1, 2])
        self.assertTrue(all(item.get("perception_provider") is None for item in calls))

    def test_v2_live_perception_provider_forwarded(self):
        calls = []

        def _fake_probe(**kwargs):
            calls.append(dict(kwargs))
            return V2ProbeResult(
                status="SUCCESS",
                intent_key=f"global:STEP:{kwargs['step_id']}",
                channel="mobile_native",
                route_reason="ut",
            )

        with tempfile.TemporaryDirectory() as td:
            with (
                patch("guiagent_v2.runtime.orchestrator_v2._load_runtime_config", return_value=_DummyConfig()),
                patch("guiagent_v2.runtime.orchestrator_v2.run_probe_step", side_effect=_fake_probe),
                patch(
                    "guiagent_v2.runtime.orchestrator_v2._emit_events_from_legacy_steps",
                    side_effect=AssertionError("legacy should not be called when v2_skip_legacy=true"),
                ),
            ):
                out = run_single_task_with_runtime(
                    instruction="打开设置",
                    run_name="ut-loop",
                    task_id="t-live-perception",
                    log_root=td,
                    runtime_mode="guiagent_v2",
                    v2_skip_legacy=True,
                    v2_max_steps=1,
                    mobile_execution_mode="shadow",
                    v2_use_live_perception=True,
                    perceptor=_DummyLivePerceptor(),
                )

        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)
        provider = calls[0].get("perception_provider")
        self.assertTrue(callable(provider))
        snapshot = provider()
        self.assertEqual(snapshot.get("screen_width"), 720)
        self.assertEqual(snapshot.get("screen_height"), 1280)
        self.assertEqual(snapshot.get("perception_infos", [])[0].get("text"), "live-pre")

    def test_v2_blueprint_embedding_dim_forwarded(self):
        calls = []

        def _fake_probe(**kwargs):
            calls.append(dict(kwargs))
            return V2ProbeResult(
                status="SUCCESS",
                intent_key=f"global:STEP:{kwargs['step_id']}",
                channel="mobile_native",
                route_reason="ut",
            )

        with tempfile.TemporaryDirectory() as td:
            with (
                patch("guiagent_v2.runtime.orchestrator_v2._load_runtime_config", return_value=_DummyConfig()),
                patch("guiagent_v2.runtime.orchestrator_v2.run_probe_step", side_effect=_fake_probe),
                patch(
                    "guiagent_v2.runtime.orchestrator_v2._emit_events_from_legacy_steps",
                    side_effect=AssertionError("legacy should not be called when v2_skip_legacy=true"),
                ),
            ):
                out = run_single_task_with_runtime(
                    instruction="打开设置",
                    run_name="ut-loop",
                    task_id="t-blueprint-dim",
                    log_root=td,
                    runtime_mode="guiagent_v2",
                    v2_skip_legacy=True,
                    v2_max_steps=1,
                    mobile_execution_mode="shadow",
                    blueprint_embedding_dim=8,
                )

        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)
        repo = calls[0].get("blueprint_repo")
        info = repo.get_vector_backend_info()
        self.assertEqual(info.get("embedding_dim"), 8)
        self.assertEqual(info.get("source"), "vector_mock")

    def test_v2_blueprint_custom_vector_plugin_loaded(self):
        calls = []

        def _fake_probe(**kwargs):
            calls.append(dict(kwargs))
            return V2ProbeResult(
                status="SUCCESS",
                intent_key=f"global:STEP:{kwargs['step_id']}",
                channel="mobile_native",
                route_reason="ut",
            )

        with tempfile.TemporaryDirectory() as td:
            with (
                patch("guiagent_v2.runtime.orchestrator_v2._load_runtime_config", return_value=_DummyConfig()),
                patch("guiagent_v2.runtime.orchestrator_v2.run_probe_step", side_effect=_fake_probe),
                patch(
                    "guiagent_v2.runtime.orchestrator_v2._emit_events_from_legacy_steps",
                    side_effect=AssertionError("legacy should not be called when v2_skip_legacy=true"),
                ),
            ):
                out = run_single_task_with_runtime(
                    instruction="打开设置",
                    run_name="ut-loop",
                    task_id="t-blueprint-plugin",
                    log_root=td,
                    runtime_mode="guiagent_v2",
                    v2_skip_legacy=True,
                    v2_max_steps=1,
                    mobile_execution_mode="shadow",
                    blueprint_vector_backend="custom",
                    blueprint_vector_plugin="test_orchestrator_v2_loop:_vector_plugin_factory",
                    blueprint_embedding_dim=6,
                )

        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)
        repo = calls[0].get("blueprint_repo")
        info = repo.get_vector_backend_info()
        self.assertEqual(info.get("embedding_dim"), 6)
        self.assertEqual(info.get("source"), "vector_plugin_ut")


if __name__ == "__main__":
    unittest.main()
