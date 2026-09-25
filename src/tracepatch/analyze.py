"""Read structured actions; never execute commands embedded in a trace."""

from collections import defaultdict
from typing import Any


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("trajectory_format") != "mini-swe-agent-1.1":
        raise ValueError("Expected mini-swe-agent-1.1 trajectory format")
    messages = data.get("messages")
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    positions: dict[str, list[int]] = defaultdict(list)
    assistant_count = 0
    action_count = 0
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"Message {index} must be an object")
        if message.get("role") != "assistant":
            continue
        assistant_count += 1
        extra = message.get("extra", {})
        if not isinstance(extra, dict) or not isinstance(extra.get("actions", []), list):
            raise ValueError(f"Invalid actions metadata at message {index}")
        for action in extra.get("actions", []):
            if not isinstance(action, dict) or not isinstance(action.get("command"), str):
                raise ValueError(f"Invalid command at message {index}")
            # Preserve shell syntax and quoted whitespace: only exact repeats count.
            command = action["command"]
            if command.strip():
                positions[command].append(index)
                action_count += 1
    info = data.get("info", {})
    if not isinstance(info, dict) or not isinstance(info.get("model_stats", {}), dict):
        raise ValueError("Invalid info/model_stats metadata")
    stats = info.get("model_stats", {})
    repeats = [
        {"command": command, "count": len(indices), "message_indices": indices}
        for command, indices in positions.items() if len(indices) > 1
    ]
    return {
        "schema_version": "tracepatch-report-0.1",
        "source_format": data["trajectory_format"],
        "synthetic": data.get("tracepatch_fixture") == "synthetic",
        "message_count": len(messages),
        "assistant_message_count": assistant_count,
        "action_count": action_count,
        "reported_api_calls": stats.get("api_calls"),
        "reported_cost": stats.get("instance_cost"),
        "reported_exit_status": info.get("exit_status"),
        "task_success": None,
        "repeated_commands": repeats,
        "limitations": [
            "Repeated commands are review candidates, not proof of a stalled agent.",
            "Task success requires an independent verifier; exit status is insufficient.",
            "Missing cost is unknown, not zero; reported cost is not an audited bill.",
            "Reports contain raw commands; inspect for secrets before sharing.",
        ],
    }
