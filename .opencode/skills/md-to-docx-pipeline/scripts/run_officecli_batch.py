from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import ensure_officecli_available, officecli_batch, read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy OfficeCLI batch từ một JSON array mutation duy nhất.")
    parser.add_argument("--target-file", required=True)
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--report-json", required=False)
    args = parser.parse_args()

    target_file = Path(args.target_file)
    input_json = Path(args.input_json)
    report_json = Path(args.report_json) if args.report_json else input_json.with_name("batch_report.json")

    commands = read_json(input_json)
    if not isinstance(commands, list):
        raise ValueError("Batch input phải là JSON array các command OfficeCLI.")

    version = ensure_officecli_available()
    payload = officecli_batch(target_file, input_json)
    report = {
        "officecli_version": version,
        "target_file": str(target_file),
        "input_json": str(input_json),
        "command_count": len(commands),
        "result": payload.get("data"),
    }
    write_json(report_json, report)


if __name__ == "__main__":
    main()