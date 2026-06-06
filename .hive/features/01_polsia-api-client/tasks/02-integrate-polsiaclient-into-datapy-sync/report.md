# Task Report: 02-integrate-polsiaclient-into-datapy-sync

**Feature:** polsia-api-client
**Completed:** 2026-06-05T15:40:35.966Z
**Status:** success
**Commit:** 4bebe66116cfea6d002267e8fba009864f786024

---

## Summary

集成 PolsiaClient 到 hq/domains/data.py: (1) 添加 `polsia_sync_via_api()` — 通过 REST API 填充 CACHE (PolsiaClient 9个端点，按 endpoint 独立 try/except 优雅降级); (2) 修改 `polsia_sync()` — API 优先，失败后回退到原有的 SQLite 同步; (3) 提取 `_try_nocobase_sync()` 辅助函数; (4) 修复 E741 (l→lead)。验证: 130 PASS/2 SKIP, ruff 零错误。

---

## Changes

- **Files changed:** 1
- **Insertions:** +176
- **Deletions:** -1

### Files Modified

- `hq/domains/data.py`
