from __future__ import annotations

from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.moneydj_client import (
    _parse_bcd_history,
    _parse_market_fund_flow,
    _parse_sector_catalog,
)


def test_parse_moneydj_market_fund_flow_extracts_twse_tpex_rates():
    html = """
    <table>
      <tr><td class="t10" colspan="8">上市資金流向表<div>最後更新時間：06/05</div></td></tr>
      <tr><td>類股名稱</td><td>流向率</td><td>類股名稱</td><td>流向率</td></tr>
      <tr><td>電腦及週邊設備</td><td>10.10%</td><td>電子零組件</td><td>15.57%</td></tr>
      <tr><td class="t10" colspan="8">上櫃資金流向表<div>最後更新時間：06/05</div></td></tr>
      <tr><td>類股名稱</td><td>流向率</td><td>類股名稱</td><td>流向率</td></tr>
      <tr><td>半導體</td><td>43.82%</td><td>電子零組件</td><td>20.44%</td></tr>
    </table>
    """

    trade_date, rows = _parse_market_fund_flow(html, date(2026, 6, 7))

    assert trade_date == date(2026, 6, 5)
    twse_component = next(row for row in rows if row["market"] == "TWSE" and row["industry"] == "電子零組件")
    assert twse_component["trade_date"] == "2026-06-05"
    assert twse_component["moneydj_flow_rate_pct"] == 15.57
    assert twse_component["source"] == "moneydj"
    assert any(row["market"] == "TPEX" and row["industry"] == "半導體" for row in rows)


def test_parse_moneydj_sector_catalog_extracts_market_sector_id():
    html = """
    <script>
    sTSE[0] = new SecEnt('EB033000', '電腦及週邊設備');
    sOTC[0] = new SecEnt('EB166000', '電子零組件');
    </script>
    """

    rows = _parse_sector_catalog(html)

    assert rows == [
        {"market": "TWSE", "moneydj_sector_id": "EB033000", "industry": "電腦及週邊設備"},
        {"market": "TPEX", "moneydj_sector_id": "EB166000", "industry": "電子零組件"},
    ]


def test_parse_moneydj_bcd_history_extracts_best_indicator_inputs():
    raw = "601,602,605 100,101,103 50,51,55 1.20,1.40,2.10"

    rows = _parse_bcd_history(
        raw,
        target_date=date(2026, 6, 7),
        market="TWSE",
        industry="電腦及週邊設備",
        sector_id="EB033000",
    )

    assert len(rows) == 3
    assert rows[-1]["trade_date"] == "2026-06-05"
    assert rows[-1]["moneydj_market_index"] == 103
    assert rows[-1]["moneydj_sector_index"] == 55
    assert rows[-1]["moneydj_flow_rate_pct"] == 2.10
