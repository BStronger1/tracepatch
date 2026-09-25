import argparse
import json
from pathlib import Path

from tracepatch.analyze import analyze


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a mini-swe-agent trajectory offline")
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.trajectory.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Trajectory must be a JSON object")
        result = json.dumps(analyze(data), ensure_ascii=False, indent=2)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.output:
        if args.output.resolve() == args.trajectory.resolve():
            parser.error("Output must not overwrite the source trajectory")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    else:
        print(result)
