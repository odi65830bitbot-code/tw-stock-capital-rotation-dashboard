from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_update_pipeline_uses_non_ai_sentiment_step() -> None:
    script = (ROOT / "scripts" / "run_daily_update.sh").read_text(encoding="utf-8")
    server = (ROOT / "web" / "server.js").read_text(encoding="utf-8")

    assert "scripts/update_txf_after_hours.py" in script
    assert "scripts/update_txf_after_hours.py" in server
    assert "scripts/fetch_sentiment_and_macro.py" in script
    assert "scripts/fetch_sentiment_and_macro.py" in server
    assert "advanced_sentiment_analyzer.py" not in script
    assert "advanced_sentiment_analyzer.py" not in server
