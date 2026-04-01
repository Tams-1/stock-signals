from pathlib import Path
from typing import Dict, List, Optional
import json
from urllib import error, parse, request

from .alert_generator import generate_trading_alerts


DEFAULT_BR_MARKET_CHAT_ID = "-1003717122770"
TELEGRAM_MESSAGE_LIMIT = 4000
ACTIONABLE_SIGNALS = {"STRONG_BUY", "BUY", "SELL", "STRONG_SELL"}


def build_actionable_alert(results: List[Dict], top_n: int = 5) -> Optional[str]:
    """Return the exact Telegram alert payload when there is something actionable."""
    actionable = [r for r in results if r.get("signal") in ACTIONABLE_SIGNALS]
    if not actionable:
        return None
    return generate_trading_alerts(results, top_n=top_n)


def write_alert_snapshot(alert_text: Optional[str], output_path: str) -> Path:
    """Persist the exact alert payload for audit/debugging."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(alert_text or "", encoding="utf-8")
    return path


def split_telegram_message(text: str, max_chars: int = TELEGRAM_MESSAGE_LIMIT) -> List[str]:
    """Split long alerts across multiple Telegram messages without changing content."""
    if not text:
        return []

    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0

    for line in text.splitlines():
        if len(line) > max_chars:
            if current_lines:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_len = 0

            for start in range(0, len(line), max_chars):
                chunks.append(line[start:start + max_chars])
            continue

        projected_len = current_len + len(line) + (1 if current_lines else 0)
        if current_lines and projected_len > max_chars:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len = projected_len if len(current_lines) > 1 else len(line)

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks


def send_telegram_text(token: str, chat_id: str, text: str, timeout: int = 30) -> Dict:
    """Send plain-text messages through the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Telegram delivery failed: {exc.reason}") from exc

    if not body.get("ok"):
        raise RuntimeError(f"Telegram delivery rejected: {body}")

    return body


def deliver_trading_alerts(
    results: List[Dict],
    token: str,
    chat_id: str = DEFAULT_BR_MARKET_CHAT_ID,
    output_path: Optional[str] = None,
    top_n: int = 5,
    dry_run: bool = False,
) -> Dict:
    """Persist and optionally send the exact formatted trading alert."""
    alert_text = build_actionable_alert(results, top_n=top_n)
    snapshot_path = None
    if output_path:
        snapshot_path = write_alert_snapshot(alert_text, output_path)

    if not alert_text:
        return {
            "alert": None,
            "sent": False,
            "chunks": 0,
            "snapshot_path": str(snapshot_path) if snapshot_path else None,
        }

    chunks = split_telegram_message(alert_text)

    if not dry_run:
        for chunk in chunks:
            send_telegram_text(token=token, chat_id=chat_id, text=chunk)

    return {
        "alert": alert_text,
        "sent": not dry_run,
        "chunks": len(chunks),
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
    }
