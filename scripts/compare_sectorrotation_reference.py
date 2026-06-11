from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "public" / "data"
REPORTS = ROOT / "reports"

FIELDS = ("net_1d_yi", "net_5d_yi", "net_20d_yi", "chg_1d", "chg_5d", "position", "stock_count")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}"}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _diff_value(local: Any, reference: Any) -> dict[str, Any]:
    local_num = _num(local)
    ref_num = _num(reference)
    if local_num is not None and ref_num is not None:
        return {
            "local": local_num,
            "reference": ref_num,
            "diff": round(local_num - ref_num, 4),
            "match": abs(local_num - ref_num) <= 0.05,
        }
    return {
        "local": local,
        "reference": reference,
        "diff": None,
        "match": local == reference,
    }


def _reference_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("sectors") or payload.get("records") or []
    return records if isinstance(records, list) else []


def compare() -> dict[str, Any]:
    local = _read_json(PUBLIC_DATA / "sector_rotation_latest.json")
    reference = _read_json(PUBLIC_DATA / "sectorrotation_latest.json")
    local_records = local.get("records") or []
    reference_records = _reference_records(reference)

    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "ok",
        "local_file": "public/data/sector_rotation_latest.json",
        "reference_file": "public/data/sectorrotation_latest.json",
        "local_as_of_date": local.get("as_of_date") or local.get("data_timestamp"),
        "reference_as_of_date": reference.get("as_of_date") or reference.get("source_updated_at"),
        "local_status": local.get("status"),
        "reference_status": reference.get("status"),
        "local_count": len(local_records) if isinstance(local_records, list) else 0,
        "reference_count": len(reference_records),
        "matches": [],
        "missing_in_local": [],
        "missing_in_reference": [],
        "mismatch_count": 0,
    }

    if reference.get("status") == "unavailable" or not reference_records:
        report["status"] = "reference_unavailable"
        report["reason"] = reference.get("reason") or "reference has no sector records"
        return report

    local_by_name = {
        str(row.get("sector_name") or row.get("name") or "").strip(): row
        for row in local_records
        if isinstance(row, dict)
    }
    ref_by_name = {
        str(row.get("sector_name") or row.get("name") or "").strip(): row
        for row in reference_records
        if isinstance(row, dict)
    }

    for name in sorted(set(local_by_name) | set(ref_by_name)):
        if not name:
            continue
        if name not in local_by_name:
            report["missing_in_local"].append(name)
            continue
        if name not in ref_by_name:
            report["missing_in_reference"].append(name)
            continue
        local_row = local_by_name[name]
        ref_row = ref_by_name[name]
        field_diffs = {field: _diff_value(local_row.get(field), ref_row.get(field)) for field in FIELDS}
        row_match = all(item["match"] for item in field_diffs.values())
        if not row_match:
            report["mismatch_count"] += 1
        report["matches"].append({"sector_name": name, "match": row_match, "fields": field_diffs})

    if report["mismatch_count"] or report["missing_in_local"] or report["missing_in_reference"]:
        report["status"] = "mismatch"
    return report


def write_report(report: dict[str, Any]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sectorrotation_compare_latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    lines = [
        "# SectorRotation 逐欄比對報告",
        "",
        f"- 產生時間：{report.get('generated_at')}",
        f"- 狀態：{report.get('status')}",
        f"- 本機日期：{report.get('local_as_of_date')}",
        f"- 參考站日期：{report.get('reference_as_of_date')}",
        f"- 本機筆數：{report.get('local_count')}",
        f"- 參考站筆數：{report.get('reference_count')}",
    ]
    if report.get("reason"):
        lines.append(f"- 原因：{report.get('reason')}")
    if report.get("status") == "mismatch":
        lines.append(f"- 不一致產業數：{report.get('mismatch_count')}")
        lines.append(f"- 本機缺少：{', '.join(report.get('missing_in_local') or []) or '無'}")
        lines.append(f"- 參考站缺少：{', '.join(report.get('missing_in_reference') or []) or '無'}")
        lines.append("")
        lines.append("## 前 20 筆不一致")
        shown = 0
        for row in report.get("matches") or []:
            if row.get("match"):
                continue
            shown += 1
            lines.append(f"- {row.get('sector_name')}：{json.dumps(row.get('fields'), ensure_ascii=False)}")
            if shown >= 20:
                break
    (REPORTS / "sectorrotation_compare_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = compare()
    write_report(report)
    print(json.dumps({k: report.get(k) for k in ["status", "local_as_of_date", "reference_as_of_date", "local_count", "reference_count", "mismatch_count", "reason"]}, ensure_ascii=False))
    return 0 if report.get("status") in {"ok", "reference_unavailable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
