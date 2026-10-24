"""Regression tests for the documented immediate acquisition effect."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from agno.tools.operation.platform_operator import PlatformOperatorTools
from agno.tools.operation.timer import TimerTools


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "day": 0,
            "dau": 1000,
            "content_volume": 100,
            "content_quality": 0.5,
            "creator_activity": 0.5,
            "engagement_level": 0.0,
            "_platform_dynamics": {
                "noise_config": {"enabled": False, "seed": 1},
                "actions": {
                    "acquisition_boost": {
                        "base_new_users": 20,
                        "quality_bonus_rate": 1.1,
                    }
                },
            },
        }
        self.operator = PlatformOperatorTools(
            platform_dynamics=self.state["_platform_dynamics"]
        )

    def test_reported_users_are_added_immediately(self):
        before = deepcopy(self.state)
        receipt = json.loads(self.operator.acquisition_boost(self.state))

        self.assertEqual(receipt, {
            "status": "success",
            "action": "acquisition_boost",
            "new_users_acquired": 31,
        })
        self.assertEqual(self.state["dau"], 1031)
        self.assertEqual(self.state["action_history"], [{
            "day": 0, "action": "acquisition_boost", "new_users": 31,
        }])
        for key, value in before.items():
            if key != "dau":
                self.assertEqual(self.state[key], value)

    def test_uses_actual_noisy_integer_count(self):
        with patch.object(self.operator, "_apply_action_noise", return_value=17.9) as noise:
            receipt = json.loads(self.operator.acquisition_boost(self.state))

        noise.assert_called_once_with(31, "acquisition_campaign", self.state)
        self.assertEqual(receipt["new_users_acquired"], 17)
        self.assertEqual(self.state["dau"], 1017)
        self.assertEqual(self.state["action_history"][0]["new_users"], 17)

    def test_repeated_actions_add_each_receipt_once(self):
        receipts = [json.loads(self.operator.acquisition_boost(self.state)) for _ in range(2)]
        self.assertEqual(self.state["dau"], 1000 + sum(r["new_users_acquired"] for r in receipts))
        self.assertEqual(len(self.state["action_history"]), 2)

    def test_zero_acquisition_leaves_dau_unchanged(self):
        self.state["_platform_dynamics"]["actions"]["acquisition_boost"]["base_new_users"] = 0
        receipt = json.loads(self.operator.acquisition_boost(self.state))
        self.assertEqual(receipt["new_users_acquired"], 0)
        self.assertEqual(self.state["dau"], 1000)

    def test_missing_dau_uses_daily_simulators_default(self):
        del self.state["dau"]
        self.operator.acquisition_boost(self.state)
        self.assertEqual(self.state["dau"], 1031)

    def test_acquired_users_enter_normal_next_day_dynamics(self):
        untreated = deepcopy(self.state)
        expected = deepcopy(self.state)
        receipt = json.loads(self.operator.acquisition_boost(self.state))
        expected["dau"] += receipt["new_users_acquired"]

        # Reloading state must retain the effect without relying on tool-local memory.
        restored = json.loads(json.dumps(self.state))
        timer = TimerTools()
        for _ in range(2):
            actual_day = json.loads(timer.task_done(restored))
            expected_day = json.loads(timer.task_done(expected))
            untreated_day = json.loads(timer.task_done(untreated))
            self.assertEqual(actual_day, expected_day)
            self.assertGreater(actual_day["current_state"]["dau"],
                               untreated_day["current_state"]["dau"])


if __name__ == "__main__":
    unittest.main()
