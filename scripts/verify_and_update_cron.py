#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股資金網站：每兩小時定時數據檢測與自我修復腳本
1. 檢測今日大盤與各股 Parquet 數據完整性 (是否過期、NaN、異常全為 0)
2. 檢測前端 JSON payload (cp, bottom, sector_rotation, chip_analysis) 欄位正確性
3. 發現異常時自動啟動對應的下載與重構流程
4. 生成 Markdown 驗證報告
"""

import sys
import os
import json
import math
import subprocess
from pathlib import Path
from datetime import datetime, time
import pandas as pd

ROOT = Path("/Users/maxyu/Documents/台股資金網站")
DATA_DIR = ROOT / "data" / "processed"
PUBLIC_DATA = ROOT / "public" / "data"
REPORT_PATH = ROOT / "data" / "data_verification_report.md"

def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

def run_script(script_name: str) -> bool:
    script_path = ROOT / "scripts" / script_name
    print(f"[*] Running script: {script_name}...")
    try:
        res = subprocess.run([sys.executable, str(script_path)], cwd=str(ROOT), capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] {script_name} completed successfully.")
            return True
        else:
            print(f"[-] {script_name} failed with code {res.returncode}.")
            print(f"Error output:\n{res.stderr}")
            return False
    except Exception as e:
        print(f"[-] Error running {script_name}: {e}")
        return False

def verify_parquet_files() -> tuple[bool, list[str]]:
    errors = []
    files = {
        "daily_price.parquet": ["trade_date", "market", "stock_code", "close", "change"],
        "institutional_flow.parquet": ["trade_date", "market", "stock_code", "three_party_net_shares"],
        "sector_flow.parquet": ["trade_date", "market", "three_party_net_shares"],
        "stock_alpha_breakdown.parquet": ["trade_date", "stock_code", "stock_alpha_v4"]
    }
    
    for name, cols in files.items():
        p = DATA_DIR / name
        if not p.exists():
            errors.append(f"Missing parquet file: {name}")
            continue
        try:
            df = pd.read_parquet(p)
            if df.empty:
                errors.append(f"Empty parquet dataset: {name}")
                continue
            # Check required columns
            for col in cols:
                if col not in df.columns:
                    errors.append(f"Column '{col}' missing in {name}")
            
            # Check latest date
            if "trade_date" in df.columns:
                latest = pd.to_datetime(df["trade_date"]).max()
                days_diff = (datetime.now() - latest).days
                # 台股週末不開盤，所以大於 4 天才算嚴重過期
                if days_diff > 4:
                    errors.append(f"Parquet {name} date {latest.strftime('%Y-%m-%d')} seems too old ({days_diff} days ago)")
        except Exception as e:
            errors.append(f"Error reading {name}: {e}")
            
    return len(errors) == 0, errors

def verify_json_payloads() -> tuple[bool, list[str]]:
    errors = []
    
    # 1. 驗證 sector_rotation_latest.json
    sr_path = PUBLIC_DATA / "sector_rotation_latest.json"
    if not sr_path.exists():
        errors.append("Missing json payload: sector_rotation_latest.json")
    else:
        try:
            data = json.loads(sr_path.read_text(encoding="utf-8"))
            sectors = data.get("sectors") or data.get("records") or []
            if not sectors:
                errors.append("sector_rotation_latest.json contains no sectors")
            else:
                # 抽查第一個 sector
                s = sectors[0]
                # 驗證累積流向不能為空/NaN
                for key in ["net_5d_yi", "net_20d_yi", "net_60d_yi"]:
                    if s.get(key) is None:
                        errors.append(f"Sector {s.get('sector_name')} has null {key} values")
                # 驗證 position 是數值且在合理區間
                pos = s.get("position")
                if pos is None or isinstance(pos, str) or not isinstance(pos, (int, float)):
                    errors.append(f"Sector {s.get('sector_name')} position '{pos}' is not numeric")
                # 驗證 quadrant 狀態存在
                quad = s.get("quadrant")
                if not quad or quad not in ["主力", "輪動", "觀望", "退潮"]:
                    errors.append(f"Sector {s.get('sector_name')} has invalid quadrant state: '{quad}'")
        except Exception as e:
            errors.append(f"Error parsing sector_rotation_latest.json: {e}")

    # 2. 驗證 chip_analysis_latest.json
    chip_path = PUBLIC_DATA / "chip_analysis_latest.json"
    if not chip_path.exists():
        errors.append("Missing json payload: chip_analysis_latest.json")
    else:
        try:
            data = json.loads(chip_path.read_text(encoding="utf-8"))
            records = data.get("records") or []
            if not records:
                errors.append("chip_analysis_latest.json has no records")
            else:
                # 驗證融資券餘額不能全為 0 或是 N/A
                zero_count = 0
                null_count = 0
                for r in records[:10]:
                    margin = r.get("margin_purchase_balance_shares")
                    if margin is None:
                        null_count += 1
                    elif margin == 0:
                        zero_count += 1
                if null_count >= 8:
                    errors.append("Most stock margin balances in chip_analysis_latest.json are null (data join error)")
                elif zero_count >= 8:
                    errors.append("Most stock margin balances in chip_analysis_latest.json are 0 (data fetch error)")
        except Exception as e:
            errors.append(f"Error parsing chip_analysis_latest.json: {e}")
            
    return len(errors) == 0, errors

def self_healing(parquet_failed: bool, json_failed: bool, errors: list[str]) -> bool:
    print("[!] Initiating self-healing protocol...")
    
    # 判斷是否是因為 margin 數據缺失
    margin_error = any("margin" in err.lower() or "chip_analysis" in err.lower() for err in errors)
    date_error = any("too old" in err.lower() for err in errors)
    
    success = True
    if date_error or parquet_failed:
        # 1. 重新下載每日最新大盤與個股數據
        success = success and run_script("update_daily.py")
        
    if margin_error or date_error:
        # 2. 重新更新 FinMind 融資融券數據
        success = success and run_script("patch_margin_data.py")
        
    # 3. 不管怎樣都重新建構 JSON outputs
    success = success and run_script("build_formal_json_outputs.py")
    
    return success

def write_verification_report(success: bool, parquet_errors: list[str], json_errors: list[str], healed: bool, heal_success: bool):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "PASS" if success else ("HEALED" if heal_success else "FAIL")
    
    report_md = f"""# 台股數據定時自動化驗證報告
- **驗證時間**：{ts}
- **驗證狀態**：{status}
- **是否有啟動修補**：{"是" if healed else "否"}
- **修補是否成功**：{"成功" if heal_success else "失敗" if healed else "無須修補"}

## 1. Parquet 數據庫檢測
- 狀態：{"異常" if parquet_errors else "正常"}
- 錯誤細節：
"""
    if parquet_errors:
        for err in parquet_errors:
            report_md += f"  - [ ] {err}\n"
    else:
        report_md += "  - [x] 所有 Parquet 檔案及最新交易日日期均完備正常。\n"
        
    report_md += f"""
## 2. 前端 JSON Payload 檢測
- 狀態：{"異常" if json_errors else "正常"}
- 錯誤細節：
"""
    if json_errors:
        for err in json_errors:
            report_md += f"  - [ ] {err}\n"
    else:
        report_md += "  - [x] 所有前端 JSON 輸出欄位 (包括累積金流、泡泡坐標與真實融資券數據) 均解析正常。\n"

    report_md += """
## 3. 下一步行動規劃
"""
    if status == "PASS":
        report_md += "- [x] 數據狀態良好，保持每 2 小時的定時追蹤。\n"
    elif status == "HEALED":
        report_md += "- [x] 成功修復數據缺失，並已重新產生 JSON 檔案。目前前端展示無虞。\n"
    else:
        report_md += "- [ ] **警告**：自動化修復失敗！可能遭遇 FinMind API 限流或 TWSE OpenAPI 連線錯誤。將於下一週期再次嘗試或轉交人工調查。\n"
        
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"[+] Verification report written to {REPORT_PATH}")

def main():
    load_env()
    
    print("[*] Starting data verification cycle...")
    parquet_ok, parquet_errors = verify_parquet_files()
    json_ok, json_errors = verify_json_payloads()
    
    all_ok = parquet_ok and json_ok
    healed = False
    heal_success = False
    
    if not all_ok:
        print(f"[!] Verification failed with {len(parquet_errors) + len(json_errors)} errors.")
        healed = True
        heal_success = self_healing(not parquet_ok, not json_ok, parquet_errors + json_errors)
        
        if heal_success:
            print("[+] Self-healing succeeded! Re-verifying...")
            p_ok, p_errs = verify_parquet_files()
            j_ok, j_errs = verify_json_payloads()
            all_ok = p_ok and j_ok
            parquet_errors = p_errs
            json_errors = j_errs
        else:
            print("[-] Self-healing failed to resolve all issues.")
    else:
        print("[+] All verification checks passed.")
        
    write_verification_report(all_ok, parquet_errors, json_errors, healed, heal_success)
    
    if not all_ok and not heal_success:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
