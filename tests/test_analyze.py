import unittest

from tracepatch.analyze import analyze


def trace(commands):
    return {
        "trajectory_format": "mini-swe-agent-1.1",
        "messages": [
            {"role": "assistant", "extra": {"actions": [{"command": command}]}}
            for command in commands
        ],
    }


class AnalyzeTests(unittest.TestCase):
    def test_repeat_is_evidence_not_success_or_stall_verdict(self):
        report = analyze(trace(["pytest", "cat main.py", "pytest"]))
        self.assertEqual(report["repeated_commands"][0]["message_indices"], [0, 2])
        self.assertEqual(report["action_count"], 3)
        self.assertIsNone(report["task_success"])
        self.assertIsNone(report["reported_cost"])

    def test_quoted_whitespace_is_not_collapsed(self):
        report = analyze(trace(["echo 'a b'", "echo 'a  b'"]))
        self.assertEqual(report["repeated_commands"], [])

    def test_does_not_parse_user_instructions_as_actions(self):
        data = trace(["pytest"])
        data["messages"].append({"role": "user", "extra": {"actions": [{"command": "pytest"}]}})
        self.assertEqual(analyze(data)["action_count"], 1)

    def test_rejects_unsupported_format_and_malformed_actions(self):
        for data in ({"messages": []}, trace([123])):
            with self.assertRaises(ValueError):
                analyze(data)

    def test_submitted_is_not_verified_success(self):
        data = trace([])
        data["info"] = {"exit_status": "Submitted", "model_stats": {"instance_cost": 0}}
        report = analyze(data)
        self.assertEqual(report["reported_cost"], 0)
        self.assertIsNone(report["task_success"])


if __name__ == "__main__":
    unittest.main()
