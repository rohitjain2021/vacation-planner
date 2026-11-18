"""Exercise the real UI without invoking Bedrock, Serper, or CrewAI."""

from datetime import datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "vacation_planner" / "streamlitui.py"


class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        self.planner = Mock()
        self.kickoff = self.planner.return_value.crew.return_value.kickoff
        self.kickoff.return_value = types.SimpleNamespace(
            raw="## Tokyo itinerary\nExplore local attractions and regional food."
        )
        fake_crew = types.ModuleType("vacation_planner.crew")
        fake_crew.VacationPlanner = self.planner
        self.monitor = Mock()
        self.monitor.record.return_value = {"logs": True, "email": True}
        fake_monitoring = types.ModuleType("vacation_planner.monitoring")
        fake_monitoring.get_monitor = Mock(return_value=self.monitor)
        self.module_patch = patch.dict(sys.modules, {
            "vacation_planner.crew": fake_crew,
            "vacation_planner.monitoring": fake_monitoring,
        })
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.app = AppTest.from_file(str(APP)).run(timeout=15)

    def submit(self, destination):
        self.app.text_input(key="destination_input").set_value(destination)
        next(button for button in self.app.button if button.label == "Plan my trip").click()
        self.app.run(timeout=15)
        self.assertEqual(len(self.app.exception), 0)

    def test_page_load_does_not_initialize_paid_services(self):
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.text_input), 1)
        self.assertEqual(len(self.app.button), 1)
        self.assertIsNone(self.app.session_state["plan"])
        self.planner.assert_not_called()
        self.monitor.record.assert_not_called()

    def test_blank_destination_is_rejected_without_a_model_call(self):
        self.submit("   ")
        self.assertEqual(len(self.app.warning), 1)
        self.planner.assert_not_called()
        self.monitor.record.assert_not_called()

    def test_generation_receives_trimmed_destination_and_current_year(self):
        self.submit("  Tokyo  ")
        self.kickoff.assert_called_once_with(
            inputs={"topic": "Tokyo", "current_year": str(datetime.now().year)}
        )
        self.assertEqual(self.app.session_state["plan"]["destination"], "Tokyo")
        self.assertTrue(any("## Tokyo itinerary" in item.value for item in self.app.markdown))
        self.assertEqual(len(self.app.get("download_button")), 1)
        self.assertEqual([call.args[0] for call in self.monitor.record.call_args_list], ["submitted", "succeeded"])
        self.assertEqual(self.monitor.record.call_args_list[0].args[1], self.monitor.record.call_args_list[1].args[1])

    def test_reruns_retain_plan_without_calling_services_again(self):
        self.submit("Tokyo")
        self.app.run(timeout=15)
        self.kickoff.assert_called_once()
        self.assertEqual(self.app.session_state["plan"]["destination"], "Tokyo")
        self.assertEqual(self.monitor.record.call_count, 2)
        self.assertEqual(len(self.app.get("download_button")), 1)

    def test_provider_failure_does_not_expose_details_or_erase_last_plan(self):
        self.submit("Tokyo")
        self.kickoff.side_effect = RuntimeError("private-provider-detail-do-not-display")
        self.submit("Paris")
        self.assertEqual(len(self.app.error), 1)
        displayed = " ".join(item.value for item in self.app.markdown)
        displayed += " ".join(item.value for item in self.app.error)
        self.assertNotIn("private-provider-detail", displayed)
        self.assertEqual(self.app.session_state["plan"]["destination"], "Tokyo")
        self.assertEqual(self.monitor.record.call_args.args[0], "failed")

    def test_empty_generated_report_is_not_saved(self):
        self.kickoff.return_value = types.SimpleNamespace(raw="   ")
        self.submit("Paris")
        self.assertEqual(len(self.app.error), 1)
        self.assertIsNone(self.app.session_state["plan"])


if __name__ == "__main__":
    unittest.main()
