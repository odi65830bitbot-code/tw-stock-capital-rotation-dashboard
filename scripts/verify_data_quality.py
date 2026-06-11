#!/usr/bin/env python3
"""
台股資金網站 — 全面數據品質驗證腳本
每 2 小時由 cron 執行，檢查所有 JSON 檔案的 null 率和數據正確性。
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PUBLIC_DATA = Path(__file__).parent.parent / "public" / "data"
LOG_DIR = Path(__file__).parent.parent / ".tmp"
LOG_DIR.mkdir(exist_ok=True)

CRITICAL_FILES = {
    "market_latest.json": {
        "fields": ["change_pct"],
        "top_level_checks": [],
    },
    "sector_rotation_latest.json": {
        "fields": [],
        "warning_fields": ["foreign_net_yi", "trust_net_yi", "dealer_net_yi", "concentration"],
        "top_level_checks": ["market_chg_1d"],
    },
    "sector_constituents_latest.json": {
        "fields": ["close", "change_pct", "foreign_net_shares", "trustee_net_shares", "dealer_net_shares"],
        "top_level_checks": [],
    },
    "recommendations_latest.json": {
        "fields": ["model_win_rate", "model_max_drawdown", "foreign_net_shares"],
        "top_level_checks": [],
    },
    "cp_ranking_latest.json": {
        "fields": [],
        "warning_fields": ["foreign_net_yi", "trust_net_yi", "dealer_net_yi", "concentration"],
        "top_level_checks": [],
    },
    "bottom_fishing_latest.json": {
        "fields": [],
        "warning_fields": ["foreign_net_yi", "trust_net_yi", "dealer_net_yi", "concentration"],
        "top_level_checks": [],
    },
    "chip_analysis_latest.json": {
        "fields": ["foreign_net_shares", "trustee_net_shares", "dealer_net_shares"],
        "top_level_checks": [],
    },
    "watchlist_latest.json": {
        "fields": ["close", "change_pct"],
        "top_level_checks": [],
    },
}

def verify_all() -> list[str]:
    """驗證所有 JSON 檔案，回傳問題清單"""
    issues = []
    warnings = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"  台股資金網站 — 數據品質驗證")
    print(f"  驗證時間: {timestamp}")
    print(f"{'='*60}\n")

    for fname, config in CRITICAL_FILES.items():
        path = PUBLIC_DATA / fname
        if not path.exists():
            msg = f"❌ {fname}: 檔案不存在!"
            print(msg)
            issues.append(msg)
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            msg = f"❌ {fname}: JSON 解析失敗: {e}"
            print(msg)
            issues.append(msg)
            continue

        records = data.get("records", [])
        if not records:
            msg = f"❌ {fname}: 無記錄!"
            print(msg)
            issues.append(msg)
            continue

        total = len(records)
        field_issues = []
        field_warnings = []

        for field in config["fields"]:
            null_count = sum(1 for r in records if r.get(field) is None)
            pct = null_count / total * 100
            if null_count > 0:
                field_issues.append(f"{field}: {null_count}/{total} ({pct:.0f}%)")

        for field in config.get("warning_fields", []):
            null_count = sum(1 for r in records if r.get(field) is None)
            pct = null_count / total * 100
            if null_count > 0:
                field_warnings.append(f"{field}: {null_count}/{total} ({pct:.0f}%)")

        # 頂層欄位檢查
        for tl in config.get("top_level_checks", []):
            val = data.get(tl)
            if val is None:
                field_issues.append(f"[頂層] {tl}: null")

        if field_issues:
            msg = f"❌ {fname}: {total} recs | " + " | ".join(field_issues)
            print(msg)
            issues.append(msg)
        elif field_warnings:
            msg = f"⚠️  {fname}: {total} recs | " + " | ".join(field_warnings)
            print(msg)
            warnings.append(msg)
        else:
            print(f"✅ {fname}: {total} recs | 所有關鍵欄位完整")

    # 特殊檢查：大盤漲跌方向
    print(f"\n{'─'*40}")
    sr_path = PUBLIC_DATA / "sector_rotation_latest.json"
    if sr_path.exists():
        sr = json.loads(sr_path.read_text(encoding="utf-8"))
        mkt = sr.get("market_chg_1d")
        is_down = sr.get("is_market_down")
        date = sr.get("as_of_date", "?")

        # 從 market_latest 驗證一致性
        mk_path = PUBLIC_DATA / "market_latest.json"
        if mk_path.exists():
            mk = json.loads(mk_path.read_text(encoding="utf-8"))
            for r in mk.get("records", []):
                if r.get("index_name") == "TAIEX":
                    actual_change = r.get("change")
                    actual_close = r.get("close")
                    if actual_change and actual_close:
                        prev = actual_close - actual_change
                        expected_pct = round(actual_change / prev * 100, 2) if prev else None
                        print(f"  TAIEX close={actual_close}, change={actual_change}")
                        print(f"  預期 change_pct: {expected_pct}%")
                        print(f"  顯示 market_chg_1d: {mkt}%")
                        if expected_pct and mkt:
                            if abs(expected_pct - mkt) > 0.5:
                                msg = f"❌ 大盤漲跌偏差過大！預期 {expected_pct}% vs 顯示 {mkt}%"
                                print(f"  {msg}")
                                issues.append(msg)
                            else:
                                print(f"  ✅ 大盤漲跌一致")
                            # 檢查方向
                            if expected_pct < 0 and not is_down:
                                msg = "❌ is_market_down 應為 True 但為 False!"
                                print(f"  {msg}")
                                issues.append(msg)

    # 5日/20日/60日 是否相同
    if sr_path.exists():
        sr = json.loads(sr_path.read_text(encoding="utf-8"))
        recs = sr.get("records", [])
        if recs:
            same_count = sum(1 for r in recs if r.get("net_5d_yi") == r.get("net_20d_yi") == r.get("net_60d_yi"))
            if same_count == len(recs):
                msg = "⚠️  5日/20日/60日 買賣超全部相同（歷史窗口不足）"
                print(f"  {msg}")
                issues.append(msg)

    print(f"\n{'='*60}")
    if issues:
        print(f"  共 {len(issues)} 個問題待修復")
    elif warnings:
        print(f"  ✅ Critical checks 通過，另有 {len(warnings)} 個資料缺口 warning（保留 null，不補假 0）")
    else:
        print(f"  ✅ 所有檢查通過！")
    print(f"{'='*60}\n")

    return issues


def main():
    issues = verify_all()

    # 寫入驗證日誌
    log_path = LOG_DIR / "data_quality_log.jsonl"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "total_issues": len(issues),
        "issues": issues,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
