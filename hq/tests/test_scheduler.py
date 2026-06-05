"""Tests for hq.scheduler — standalone sync runner."""

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from hq.scheduler import run_sync, main as scheduler_main


@pytest.mark.asyncio
async def test_run_sync_success():
    """run_sync returns True when subprocess succeeds."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(
        return_value=(b"sync complete\n", b"")
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await run_sync()
        assert result is True


@pytest.mark.asyncio
async def test_run_sync_failure():
    """run_sync returns False when subprocess fails."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"error: DB not found")
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await run_sync()
        assert result is False


@pytest.mark.asyncio
async def test_run_sync_prints_stderr():
    """run_sync prints stderr when present."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(
        return_value=(b"sync ok", b"warning: slow query")
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("builtins.print") as mock_print:
            result = await run_sync()
            assert result is True
            # Should print both stdout and stderr
            assert mock_print.called


@pytest.mark.asyncio
async def test_main_one_shot():
    """main() runs sync once and exits."""
    with patch("hq.scheduler.run_sync", return_value=True):
        with patch.object(sys, "argv", ["scheduler.py"]):
            with pytest.raises(SystemExit) as exc:
                await scheduler_main()
            assert exc.value.code == 0


@pytest.mark.asyncio
async def test_main_with_interval_flag():
    """main() parses --interval flag."""
    with patch("hq.scheduler.run_sync", return_value=True):
        with patch.object(sys, "argv", ["scheduler.py", "--interval", "60"]):
            with pytest.raises(SystemExit) as exc:
                await scheduler_main()
            assert exc.value.code == 0
