import json
import os
from pathlib import Path


def load_latest_summary() -> dict | None:
    candidates = sorted(
        Path("output").glob("run_summary_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def build_summary_markdown(summary: dict) -> str:
    notification_text = "yes" if summary.get("notification_sent") else "no"
    lines = [
        "## Workflow Summary",
        "",
        f"- Final dataset: {summary.get('final_count', 0)}",
        f"- Written to Feishu: {summary.get('written_count', 0)}",
        f"- Completion notification sent: {notification_text}",
        f"- Duration: {summary.get('elapsed_seconds', 0)}s",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    summary = load_latest_summary()
    if not summary:
        print("No run summary JSON found.")
        return 0

    markdown = build_summary_markdown(summary)
    print(markdown, end="")

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
