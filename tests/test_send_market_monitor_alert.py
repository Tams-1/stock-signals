import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "send_market_monitor_alert.py"
SPEC = importlib.util.spec_from_file_location("send_market_monitor_alert", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_main_prints_only_alert_block(monkeypatch, capsys):
    output = "\n".join(
        [
            "Initializing...",
            "📱 TELEGRAM ALERTS",
            "",
            "🚨 TOP TRADING OPPORTUNITIES",
            "Generated: 15:20:00",
            "",
            "1️⃣  PRIO3 - BUY 🟢",
            "======================================================================",
        ]
    )

    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    exit_code = MODULE.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "\n".join(
        [
            "🚨 TOP TRADING OPPORTUNITIES",
            "Generated: 15:20:00",
            "",
            "1️⃣  PRIO3 - BUY 🟢",
            "======================================================================",
        ]
    )


def test_main_prints_no_actionable_signals_when_alert_missing(monkeypatch, capsys):
    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="⚠️  MONITORING: 0 BUY signals out of 214 tickers. (0 SELL)\n",
            stderr="",
        ),
    )

    exit_code = MODULE.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "No actionable signals"
