#!/usr/bin/env python3
"""CrossWave HQ — 自动周报生成器

Usage:
  python hq/weekly_report.py                    # Print to stdout
  python hq/weekly_report.py --save              # Save to hq/reports/
  python hq/weekly_report.py --json              # JSON output
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

POLSIA_DB = os.environ.get(
    "POLSIA_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "polsia-fork", "polsia.db")
)

def get_db():
    if not os.path.exists(POLSIA_DB):
        print(f"[report] Polsia DB not found at {POLSIA_DB}", file=sys.stderr)
        return None
    return sqlite3.connect(POLSIA_DB)

def generate_report(db):
    cur = db.cursor()
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).isoformat()

    # MRR: latest snapshot
    rev = cur.execute("SELECT mrr_cents, arr_cents, active_subscribers, snapshot_date FROM revenue_snapshots ORDER BY snapshot_date DESC LIMIT 1").fetchone()
    # MRR a week ago
    rev_ago = cur.execute("SELECT mrr_cents FROM revenue_snapshots WHERE snapshot_date <= date('now', '-7 days') ORDER BY snapshot_date DESC LIMIT 1").fetchone()
    # Tasks
    total_tasks = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] or 0
    done_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('done','completed')").fetchone()[0] or 0
    failed_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0] or 0
    pending_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0] or 0
    # Recent tasks (7 days)
    recent_tasks = cur.execute("SELECT COUNT(*) FROM tasks WHERE created_at >= ?", (week_ago,)).fetchone()[0] or 0
    # Leads
    total_leads = cur.execute("SELECT COUNT(*) FROM leads").fetchone()[0] or 0
    new_leads = cur.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0] or 0
    won_leads = cur.execute("SELECT COUNT(*) FROM leads WHERE status='won'").fetchone()[0] or 0
    recent_leads = cur.execute("SELECT COUNT(*) FROM leads WHERE created_at >= ?", (week_ago,)).fetchone()[0] or 0
    # External orders
    total_ext = cur.execute("SELECT COUNT(*) FROM external_orders").fetchone()[0] or 0
    pending_ext = cur.execute("SELECT COUNT(*) FROM external_orders WHERE status IN ('scanned','pending')").fetchone()[0] or 0
    accepted_ext = cur.execute("SELECT COUNT(*) FROM external_orders WHERE status='accepted'").fetchone()[0] or 0
    # Activity
    recent_activity = cur.execute("SELECT COUNT(*) FROM activity_log WHERE created_at >= ?", (week_ago,)).fetchone()[0] or 0
    # Agent runs
    agent_runs = cur.execute("SELECT COUNT(*) FROM agent_runs WHERE started_at >= ?", (week_ago,)).fetchone()[0] or 0
    # Revenue history for trend
    rev_history = cur.execute(
        "SELECT snapshot_date, mrr_cents FROM revenue_snapshots WHERE snapshot_date >= date('now', '-30 days') ORDER BY snapshot_date"
    ).fetchall()

    return {
        "generated_at": now.isoformat(),
        "period": f"{(now - timedelta(days=7)).date()} ~ {now.date()}",
        "mrr": {
            "current": (rev[0] or 0) / 100.0 if rev else 0,
            "arr": (rev[1] or 0) / 100.0 if rev else 0,
            "subscribers": rev[2] or 0 if rev else 0,
            "last_week": (rev_ago[0] or 0) / 100.0 if rev_ago else 0,
            "growth": ((rev[0] or 0) - (rev_ago[0] or 0)) / 100.0 if (rev and rev_ago) else 0,
        },
        "tasks": {
            "total": total_tasks,
            "done": done_tasks,
            "failed": failed_tasks,
            "pending": pending_tasks,
            "completion_rate": round(done_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
            "this_week": recent_tasks,
        },
        "leads": {
            "total": total_leads,
            "new": new_leads,
            "won": won_leads,
            "this_week": recent_leads,
            "conversion_rate": round(won_leads / total_leads * 100, 1) if total_leads > 0 else 0,
        },
        "external_orders": {
            "total": total_ext,
            "pending": pending_ext,
            "accepted": accepted_ext,
        },
        "activity": {
            "this_week": recent_activity,
            "agent_runs_this_week": agent_runs,
        },
        "revenue_trend_30d": [
            {"date": r[0], "mrr": r[1] / 100.0} for r in rev_history
        ] if rev_history else [],
    }

def format_markdown(report):
    lines = []
    lines.append("# 📊 CrossWave 周报\n")
    lines.append(f"**周期**: {report['period']}  |  **生成时间**: {report['generated_at'][:19]}\n")
    lines.append("---\n")

    # MRR
    m = report["mrr"]
    growth_emoji = "📈" if m["growth"] >= 0 else "📉"
    lines.append("## 💰 收入\n")
    lines.append(f"- **当前 MRR**: ${m['current']:.2f}")
    lines.append(f"- **ARR**: ${m['arr']:.2f}")
    lines.append(f"- **活跃订阅**: {m['subscribers']}")
    lines.append(f"- **上周 MRR**: ${m['last_week']:.2f}")
    lines.append(f"- **周增长**: {growth_emoji} ${m['growth']:.2f}\n")

    # Tasks
    t = report["tasks"]
    lines.append("## ✅ 任务\n")
    lines.append(f"- **总计**: {t['total']} | ✅ {t['done']} | ❌ {t['failed']} | ⏳ {t['pending']}")
    lines.append(f"- **完成率**: {t['completion_rate']}%")
    lines.append(f"- **本周新增**: {t['this_week']}\n")

    # Leads
    lead_info = report["leads"]
    lines.append("## 👥 线索\n")
    lines.append(f"- **总计**: {lead_info['total']} | 🆕 {lead_info['new']} | 🏆 {lead_info['won']}")
    lines.append(f"- **本周新增**: {lead_info['this_week']}")
    lines.append(f"- **转化率**: {lead_info['conversion_rate']}%\n")

    # Orders
    o = report["external_orders"]
    lines.append("## 📦 外部订单\n")
    lines.append(f"- **总计**: {o['total']} | ⏳ {o['pending']} | ✅ {o['accepted']}\n")

    # Activity
    a = report["activity"]
    lines.append("## 🔄 活动\n")
    lines.append(f"- **本周活动记录**: {a['this_week']}")
    lines.append(f"- **Agent 执行次数**: {a['agent_runs_this_week']}\n")

    # Revenue trend
    if report["revenue_trend_30d"]:
        first = report["revenue_trend_30d"][0]["mrr"]
        last = report["revenue_trend_30d"][-1]["mrr"]
        total_growth = ((last - first) / first * 100) if first > 0 else 0
        lines.append("## 📈 30天收入趋势\n")
        trend_days = len(report["revenue_trend_30d"])
        lines.append(f"- **{trend_days} 天数据**: ${first:.2f} → ${last:.2f}")
        lines.append(f"- **累计增长率**: +{total_growth:.1f}%\n")

    lines.append("---\n")
    lines.append("*由 CrossWave HQ 自动生成*\n")
    return "\n".join(lines)

def main():
    """CLI entry point: parse args, generate report, output."""
    parser = argparse.ArgumentParser(description="CrossWave HQ 自动周报")
    parser.add_argument("--save", action="store_true", help="保存到 hq/reports/ 目录")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    db = get_db()
    if not db:
        sys.exit(1)
    report = generate_report(db)
    db.close()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.save:
        reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"weekly-{datetime.now().strftime('%Y-%m-%d')}.md"
        filepath = os.path.join(reports_dir, filename)
        with open(filepath, "w") as f:
            f.write(format_markdown(report))
        print(f"[report] ✅ 周报已保存到 {filepath}")
    else:
        print(format_markdown(report))


if __name__ == "__main__":
    main()
