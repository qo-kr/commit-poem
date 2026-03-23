from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

import pytest

from commitpoem.scheduler import _parse_duration, run_once, run_scheduler


# ---------------------------------------------------------------------------
# TestParseDuration
# ---------------------------------------------------------------------------


class TestParseDuration:
    """Unit tests for the private _parse_duration helper."""

    @pytest.mark.parametrize(
        "expr, expected",
        [
            ("30s", 30.0),
            ("5m", 300.0),
            ("1h", 3600.0),
            ("2h30m", 9000.0),
            ("1h5m30s", 3930.0),
            ("90s", 90.0),
            ("1m30s", 90.0),
            ("2h0m0s", 7200.0),
        ],
    )
    def test_happy_path(self, expr: str, expected: float) -> None:
        assert _parse_duration(expr) == expected

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("   ")

    def test_zero_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _parse_duration("0s")

    def test_all_zero_components_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _parse_duration("0h0m0s")

    def test_unrecognised_format_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("every tuesday")

    def test_uppercase_unit_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("5M")

    def test_uppercase_hour_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("1H")

    def test_bare_number_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_duration("60")

    def test_returns_float(self) -> None:
        result = _parse_duration("1m")
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# TestRunOnce
# ---------------------------------------------------------------------------


class TestRunOnce:
    """Tests for run_once."""

    def test_pipeline_called_exactly_once(self) -> None:
        calls: list[int] = []
        run_once(lambda: calls.append(1))
        assert calls == [1]

    def test_return_value_is_none(self) -> None:
        result = run_once(lambda: 42)
        assert result is None

    def test_exception_caught_and_not_reraised(self) -> None:
        def bad_pipeline() -> None:
            raise RuntimeError("boom")

        # Should not raise
        run_once(bad_pipeline)

    def test_exception_logged_at_error(self, caplog: pytest.LogCaptureFixture) -> None:
        def bad_pipeline() -> None:
            raise ValueError("test-error-message")

        with caplog.at_level(logging.ERROR, logger="commitpoem.scheduler"):
            run_once(bad_pipeline)

        assert any("test-error-message" in r.message or "test-error-message" in str(r.exc_info)
                   for r in caplog.records), f"Expected error in caplog, got: {caplog.records}"
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1

    def test_exception_log_includes_exc_info(self, caplog: pytest.LogCaptureFixture) -> None:
        def bad_pipeline() -> None:
            raise RuntimeError("exc-info-check")

        with caplog.at_level(logging.ERROR, logger="commitpoem.scheduler"):
            run_once(bad_pipeline)

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert error_records[0].exc_info is not None

    def test_keyboard_interrupt_propagates(self) -> None:
        def bad_pipeline() -> None:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            run_once(bad_pipeline)

    def test_system_exit_propagates(self) -> None:
        def bad_pipeline() -> None:
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            run_once(bad_pipeline)


# ---------------------------------------------------------------------------
# TestRunScheduler
# ---------------------------------------------------------------------------


class TestRunScheduler:
    """Tests for run_scheduler."""

    def test_stop_event_pre_set_pipeline_never_called(self) -> None:
        calls: list[int] = []
        stop = threading.Event()
        stop.set()
        run_scheduler("60s", lambda: calls.append(1), stop_event=stop)
        assert calls == []

    def test_single_iteration_stop_inside_pipeline(self) -> None:
        calls: list[int] = []
        stop = threading.Event()

        def pipeline() -> None:
            calls.append(1)
            stop.set()

        run_scheduler("60s", pipeline, stop_event=stop)
        assert calls == [1]

    def test_multiple_iterations(self) -> None:
        """Pipeline runs N times before stop_event is set."""
        counter: list[int] = []
        stop = threading.Event()
        max_calls = 3

        def pipeline() -> None:
            counter.append(1)
            if len(counter) >= max_calls:
                stop.set()

        run_scheduler("1s", pipeline, stop_event=stop)
        assert len(counter) == max_calls

    def test_exception_per_run_logged_loop_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exception in pipeline is logged and the loop continues."""
        call_count = 0
        stop = threading.Event()

        def bad_pipeline() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                stop.set()
            raise RuntimeError(f"error-{call_count}")

        with caplog.at_level(logging.ERROR, logger="commitpoem.scheduler"):
            run_scheduler("1s", bad_pipeline, stop_event=stop)

        assert call_count == 3
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        # All 3 calls raised, so all 3 should be logged (stop set after 3rd raise)
        assert len(error_records) >= 1

    def test_exception_does_not_abort_loop(self) -> None:
        """Exception in pipeline is caught; loop returns cleanly via stop_event rather than aborting."""
        results: list[int] = []
        stop = threading.Event()

        def raises_then_stops() -> None:
            results.append(1)
            stop.set()  # set stop so we return after the exception is caught
            raise ValueError("always fails")

        # Must not raise; must call pipeline exactly once before stop is honoured
        run_scheduler("60s", raises_then_stops, stop_event=stop)
        assert len(results) == 1

    def test_keyboard_interrupt_propagates(self) -> None:
        stop = threading.Event()

        def bad_pipeline() -> None:
            stop.set()
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            run_scheduler("60s", bad_pipeline, stop_event=stop)

    def test_system_exit_propagates(self) -> None:
        stop = threading.Event()

        def bad_pipeline() -> None:
            stop.set()
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            run_scheduler("60s", bad_pipeline, stop_event=stop)

    def test_invalid_expr_raises_value_error(self) -> None:
        stop = threading.Event()
        with pytest.raises(ValueError):
            run_scheduler("", lambda: None, stop_event=stop)

    def test_none_pipeline_raises_type_error(self) -> None:
        stop = threading.Event()
        stop.set()
        with pytest.raises(TypeError):
            run_scheduler("5m", None, stop_event=stop)  # type: ignore[arg-type]

    def test_async_pipeline_raises_type_error(self) -> None:
        async def async_fn() -> None:
            pass

        stop = threading.Event()
        stop.set()
        with pytest.raises(TypeError):
            run_scheduler("5m", async_fn, stop_event=stop)

    def test_returns_none(self) -> None:
        stop = threading.Event()
        stop.set()
        result = run_scheduler("1m", lambda: None, stop_event=stop)
        assert result is None

    def test_no_stop_event_single_pipeline_call_then_base_exception(self) -> None:
        """Without stop_event, BaseException from pipeline propagates on first call."""
        count = 0

        def pipeline_raises_immediately() -> None:
            nonlocal count
            count += 1
            raise SystemExit(0)

        with pytest.raises(SystemExit):
            run_scheduler("60s", pipeline_raises_immediately)

        assert count == 1

    def test_exception_log_has_exc_info(self, caplog: pytest.LogCaptureFixture) -> None:
        stop = threading.Event()

        def bad_pipeline() -> None:
            stop.set()
            raise RuntimeError("traceback-check")

        with caplog.at_level(logging.ERROR, logger="commitpoem.scheduler"):
            run_scheduler("60s", bad_pipeline, stop_event=stop)

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert error_records[0].exc_info is not None
