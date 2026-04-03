import pandas as pd
import pytest
import requests
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import src.brapi_client as brapi_module
from src.brapi_client import BrAPIClient


@pytest.fixture(autouse=True)
def isolated_price_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(brapi_module, "CACHE_FILE", tmp_path / "price_cache.json")
    BrAPIClient._quota_exceeded = False


def test_get_prices_falls_back_to_yfinance_after_brapi_429():
    client = BrAPIClient(api_key="test-token")

    response = MagicMock()
    response.ok = False
    response.status_code = 429
    response.json.return_value = {"error": "Monthly quota exceeded"}
    response.text = '{"error":"Monthly quota exceeded"}'
    response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")

    now = datetime.now(timezone.utc)
    yf_data = pd.DataFrame(
        {"Close": [10.10, 10.35, 10.55]},
        index=pd.date_range(end=now, periods=3, freq="min", tz="UTC"),
    )

    with patch("src.brapi_client.requests.get", return_value=response), patch(
        "src.brapi_client.yf.download", return_value=yf_data
    ):
        prices = client.get_prices(["PETR4"])

    assert client.is_quota_exceeded() is True
    assert prices["PETR4"] == pytest.approx(10.55)

    snapshot = client.get_price_snapshot("PETR4")
    assert snapshot is not None
    assert snapshot["source"] == "yfinance"


def test_cache_rejects_stale_quote_during_market_hours():
    client = BrAPIClient()
    now = datetime.now(timezone.utc)
    client._cache["PETR4"] = {
        "price": 25.0,
        "ts": now.timestamp(),
        "updated": now.isoformat(),
        "quote_ts": (now - timedelta(minutes=30)).isoformat(),
        "source": "yfinance",
    }

    with patch.object(client, "is_market_hours", return_value=True):
        assert client.get_price_snapshot("PETR4") is None
