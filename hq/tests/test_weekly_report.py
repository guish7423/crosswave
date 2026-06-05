"""Tests for hq.weekly_report — weekly report generator."""

import json
import os
import sqlite3
import sys
import tempfile
from unittest.mock import patch

import pytest

from hq.weekly_report import generate_report, get_db, main as report_main


@pytest.fixture
def polsia_db():
    """Create a temp Polsia Fork SQLite DB with realistic data."""
    Pf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Pf.name
    Pf.close()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create tables
    cur.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, agent_type TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, name TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE external_orders (id INTEGER PRIMARY KEY, title TEXT, platform TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY, action TEXT, level TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE agent_runs (id INTEGER PRIMARY KEY, agent_type TEXT, started_at TEXT)")
    cur.execute("CREATE TABLE revenue_snapshots (id INTEGER PRIMARY KEY, mrr_cents INTEGER, arr_cents INTEGER, active_subscribers INTEGER, snapshot_date TEXT)")

    # Seed data
    cur.execute("INSERT INTO tasks VALUES (1, 'Build auth', 'orchestrator', 'completed', '2026-06-01')")
    cur.execute("INSERT INTO tasks VALUES (2, 'Fix bug', 'code_generation', 'failed', '2026-06-02')")
    cur.execute("INSERT INTO tasks VALUES (3, 'Deploy', 'deployment', 'pending', '2026-06-02')")
    cur.execute("INSERT INTO leads VALUES (1, 'Alice', 'new', '2026-06-01')")
    cur.execute("INSERT INTO leads VALUES (2, 'Bob', 'won', '2026-06-02')")
    cur.execute("INSERT INTO leads VALUES (3, 'Carol', 'new', '2026-06-03')")
    cur.execute("INSERT INTO external_orders VALUES (1, 'Build site', 'upwork', 'accepted', '2026-06-01')")
    cur.execute("INSERT INTO external_orders VALUES (2, 'Write content', 'fiverr', 'scanned', '2026-06-02')")
    cur.execute("INSERT INTO activity_log VALUES (1, 'Task created', 'info', '2026-06-01')")
    cur.execute("INSERT INTO agent_runs VALUES (1, 'orchestrator', '2026-06-01')")
    cur.execute("INSERT INTO revenue_snapshots VALUES (1, 17400, 208800, 4, '2026-06-05')")

    conn.commit()
    conn.close()
    return db_path


def test_get_db_returns_none_for_missing():
    """get_db returns None when DB_PATH doesn't exist."""
    import hq.weekly_report as wr

    original = wr.POLSIA_DB
    wr.POLSIA_DB = "/nonexistent/db.sqlite"
    try:
        assert get_db() is None
    finally:
        wr.POLSIA_DB = original


def test_generate_report_basic(polsia_db):
    """generate_report returns dict with expected structure."""
    import hq.weekly_report as wr

    wr.POLSIA_DB = polsia_db
    db = get_db()
    assert db is not None

    report = generate_report(db)
    db.close()

    assert report is not None
    assert "mrr" in report
    assert "tasks" in report
    assert "leads" in report
    assert "external_orders" in report
    assert "activity" in report
    assert report["activity"]["agent_runs_this_week"] == 1

    # Validate data
    assert report["mrr"]["current"] == 174.0
    assert report["tasks"]["total"] == 3
    assert report["tasks"]["done"] == 1  # 'completed'
    assert report["tasks"]["failed"] == 1
    assert report["tasks"]["pending"] == 1
    assert report["leads"]["total"] == 3
    assert report["leads"]["new"] == 2   # two new leads
    assert report["external_orders"]["total"] == 2
    assert report["external_orders"]["accepted"] == 1


def test_generate_report_with_trend(polsia_db):
    """generate_report includes revenue trend data."""
    import hq.weekly_report as wr

    wr.POLSIA_DB = polsia_db
    db = get_db()
    report = generate_report(db)
    db.close()

    assert "revenue_trend_30d" in report
    # Should have at least one data point
    assert len(report["revenue_trend_30d"]) > 0


def test_generate_report_empty_db():
    """generate_report handles empty DB gracefully."""
    Pf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Pf.name
    Pf.close()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, agent_type TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, name TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE external_orders (id INTEGER PRIMARY KEY, title TEXT, platform TEXT, status TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE activity_log (id INTEGER PRIMARY KEY, action TEXT, level TEXT, created_at TEXT)")
    cur.execute("CREATE TABLE agent_runs (id INTEGER PRIMARY KEY, agent_type TEXT, started_at TEXT)")
    cur.execute("CREATE TABLE revenue_snapshots (id INTEGER PRIMARY KEY, mrr_cents INTEGER, arr_cents INTEGER, active_subscribers INTEGER, snapshot_date TEXT)")
    conn.commit()
    conn.close()

    import hq.weekly_report as wr

    wr.POLSIA_DB = db_path
    db = get_db()
    report = generate_report(db)
    db.close()
    os.unlink(db_path)

    assert report is not None
    assert report["tasks"]["total"] == 0
    assert report["mrr"]["current"] == 0


def test_main_stdout(polsia_db):
    """main() prints report to stdout."""
    import hq.weekly_report as wr

    wr.POLSIA_DB = polsia_db
    test_args = ["weekly_report.py"]
    with patch.object(sys, "argv", test_args):
        with patch("builtins.print") as mock_print:
            report_main()
            assert mock_print.called


def test_main_json(polsia_db):
    """main() with --json outputs JSON."""
    import hq.weekly_report as wr

    wr.POLSIA_DB = polsia_db
    test_args = ["weekly_report.py", "--json"]
    with patch.object(sys, "argv", test_args):
        with patch("builtins.print") as mock_print:
            report_main()
            # Should have printed JSON
            calls = [c[0][0] for c in mock_print.call_args_list if c[0]]
            json_outputs = [c for c in calls if isinstance(c, str) and c.startswith("{")]
            assert len(json_outputs) > 0
            parsed = json.loads(json_outputs[0])
            assert "mrr" in parsed



