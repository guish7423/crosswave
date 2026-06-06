# Polsia Fork API Client - Feature Complete

## 成果
- **hq/polsia_client.py** — PolsiaClient 类，httpx-based，X-API-Key 认证，覆盖9个 Polsia Fork API v1 端点
- **hq/tests/test_polsia_client.py** — 14 个测试（含集成测试），所有 mock-based，无外部依赖
- **hq/domains/data.py** — 集成 polsia_sync_via_api()，API 优先 + SQLite 回退双路径同步
- **hq/tests/conftest.py** — mock_polsia_client fixture 用于测试 mock

## 验证结果
- 全部 133 个测试通过（2个预期 skip）
- Ruff 零错误
- Mypy 无类型问题
