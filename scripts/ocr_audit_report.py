"""OCR 감사 로그 분석 및 HTML 리포트 생성 스크립트.

사용법:
    py scripts/ocr_audit_report.py           # 가장 최근 감사 실행 분석
    py scripts/ocr_audit_report.py <run_id>  # 특정 run_id 분석
"""
from __future__ import annotations

import collections
import html
import json
import os
import sys
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_ROOT = os.path.join(BASE_DIR, "logs", "ocr_audit")


def find_target_run_dir(run_id: str | None = None) -> str | None:
    if not os.path.isdir(AUDIT_ROOT):
        return None
    if run_id:
        target = os.path.join(AUDIT_ROOT, run_id)
        return target if os.path.isdir(target) else None

    runs = [
        d for d in os.listdir(AUDIT_ROOT)
        if os.path.isdir(os.path.join(AUDIT_ROOT, d)) and d != "smoke_test"
    ]
    if not runs:
        return None
    runs.sort(reverse=True)
    return os.path.join(AUDIT_ROOT, runs[0])


def load_records(log_path: str) -> list[dict[str, Any]]:
    records = []
    if not os.path.exists(log_path):
        return records
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def generate_html_report(run_dir: str, records: list[dict[str, Any]]) -> str:
    run_id = os.path.basename(run_dir)
    total_count = len(records)
    captures = set(r.get("capture") for r in records if r.get("capture"))
    status_counts = collections.Counter(r.get("status", "UNKNOWN") for r in records)

    # 필드별 집계
    field_stats: dict[str, dict[str, Any]] = collections.defaultdict(lambda: {
        "total": 0, "ok": 0, "fail": 0, "candidates": collections.Counter(), "region": ""
    })
    for r in records:
        f = r.get("field", "unknown")
        field_stats[f]["total"] += 1
        field_stats[f]["region"] = r.get("region", "")
        if r.get("status") == "OK":
            field_stats[f]["ok"] += 1
        else:
            field_stats[f]["fail"] += 1
        for c in r.get("candidates", []):
            field_stats[f]["candidates"][c] += 1

    # 테이블 행
    field_rows = []
    for field_name, stats in sorted(field_stats.items()):
        total = stats["total"]
        ok = stats["ok"]
        rate = (ok / total * 100) if total > 0 else 0
        top_candidates = ", ".join(f"{repr(k)} ({v})" for k, v in stats["candidates"].most_common(3))
        rate_color = "#22c55e" if rate >= 90 else ("#eab308" if rate >= 70 else "#ef4444")
        field_rows.append(f"""
        <tr>
            <td style="font-weight: 600;">{html.escape(field_name)}</td>
            <td><code>{html.escape(stats['region'])}</code></td>
            <td>{total}</td>
            <td>{ok}</td>
            <td>{stats['fail']}</td>
            <td style="color: {rate_color}; font-weight: 700;">{rate:.1f}%</td>
            <td style="font-size: 0.85em; color: #64748b;">{html.escape(top_candidates)}</td>
        </tr>
        """)

    # 실패/주의 항목 그리드
    issue_cards = []
    for r in records:
        if r.get("status") != "OK":
            crop_path = r.get("crop_path")
            crop_html = ""
            if crop_path and os.path.exists(crop_path):
                rel_crop = os.path.relpath(crop_path, run_dir).replace("\\", "/")
                crop_html = f'<img src="{html.escape(rel_crop)}" style="max-height: 48px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff;" />'
            else:
                crop_html = '<span style="color: #94a3b8; font-size: 0.8em;">(크롭 없음)</span>'

            cands = ", ".join(repr(c) for c in r.get("candidates", [])) or "후보 없음"
            issue_cards.append(f"""
            <div style="background: #fff; border: 1px solid #fecaca; border-radius: 6px; padding: 10px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div>
                        <span style="background: #fee2e2; color: #dc2626; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: 700;">{html.escape(r.get('status', 'FAIL'))}</span>
                        <strong style="margin-left: 8px;">{html.escape(r.get('field', ''))}</strong>
                        <span style="color: #64748b; font-size: 0.85em; margin-left: 6px;">({html.escape(r.get('capture', ''))})</span>
                    </div>
                    {crop_html}
                </div>
                <div style="font-size: 0.85em; color: #475569;">
                    <strong>OCR 후보:</strong> <code>{html.escape(cands)}</code>
                    {f'<br><strong>참고:</strong> {html.escape(r.get("note", ""))}' if r.get("note") else ''}
                </div>
            </div>
            """)

    report_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>OCR 감사 리포트 - {html.escape(run_id)}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 24px; }}
    .container {{ max-width: 1080px; margin: 0 auto; }}
    .header {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    .stats-bar {{ display: flex; gap: 16px; margin-top: 14px; }}
    .stat-box {{ background: #f1f5f9; border-radius: 6px; padding: 10px 16px; flex: 1; }}
    .stat-val {{ font-size: 1.5em; font-weight: 700; color: #0284c7; }}
    .stat-lbl {{ font-size: 0.8em; color: #64748b; margin-top: 2px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 24px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f8fafc; font-size: 0.85em; color: #475569; text-transform: uppercase; }}
    h2 {{ font-size: 1.25em; margin: 24px 0 12px; color: #1e293b; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1 style="margin: 0; font-size: 1.6em; color: #0f172a;">📊 OCR 전수 감사 리포트</h1>
        <div style="color: #64748b; font-size: 0.9em; margin-top: 4px;">Run ID: <code>{html.escape(run_id)}</code></div>
        <div class="stats-bar">
            <div class="stat-box">
                <div class="stat-val">{total_count}</div>
                <div class="stat-lbl">총 판독 시도</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{len(captures)}</div>
                <div class="stat-lbl">대상 학생 캡처 수</div>
            </div>
            <div class="stat-box">
                <div class="stat-val" style="color: #22c55e;">{status_counts.get('OK', 0)}</div>
                <div class="stat-lbl">성공 (OK)</div>
            </div>
            <div class="stat-box">
                <div class="stat-val" style="color: #ef4444;">{status_counts.get('PARSE_FAIL', 0)}</div>
                <div class="stat-lbl">파싱 실패</div>
            </div>
        </div>
    </div>

    <h2>필드별 판독 성적표</h2>
    <table>
        <thead>
            <tr>
                <th>필드</th>
                <th>좌표 영역</th>
                <th>시도</th>
                <th>성공</th>
                <th>실패</th>
                <th>성공률</th>
                <th>주요 OCR 원문</th>
            </tr>
        </thead>
        <tbody>
            {''.join(field_rows)}
        </tbody>
    </table>

    <h2>미판독 / 실패 항목 ({len(issue_cards)}건)</h2>
    {''.join(issue_cards) if issue_cards else '<div style="color: #22c55e; padding: 16px; background: #fff; border-radius: 6px;">실패 항목 없음 (100% 성공)</div>'}
</div>
</body>
</html>
"""
    return report_html


def main() -> int:
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    run_dir = find_target_run_dir(run_id)
    if not run_dir:
        print("[리포트] 분석할 감사 로그 디렉터리를 찾을 수 없습니다.")
        return 1

    log_path = os.path.join(run_dir, "audit.jsonl")
    records = load_records(log_path)
    if not records:
        print(f"[리포트] {log_path} 에 기록된 감사 데이터가 없습니다.")
        return 1

    report_html = generate_html_report(run_dir, records)
    out_html_path = os.path.join(run_dir, "report.html")
    with open(out_html_path, "w", encoding="utf-8") as f:
        f.write(report_html)

    print(f"[OK] OCR 감사 리포트 생성 완료: {out_html_path}")
    print(f"     총 판독 {len(records)}건 분석됨.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
