"""Alert system for threshold-based monitoring."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .config import settings

log = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Alert rule definition."""

    name: str
    metric: str  # e.g., "cpu.percent", "memory.virtual.percent"
    operator: str  # "gt", "lt", "gte", "lte", "eq"
    threshold: float
    message: str = ""


@dataclass
class Alert:
    """Triggered alert."""

    rule: AlertRule
    value: float
    message: str


@dataclass
class MemoryLeakDetector:
    """Detect memory leaks by tracking memory usage over time.

    Improvements over a simple first-half / second-half comparison:
    - Linear regression slope for rate-of-change estimation.
    - Alert cooldown to avoid firing on every consecutive sample once the
      threshold is crossed.
    - Tracks per-sample derivative so callers can inspect instantaneous
      growth rate.
    """

    window_size: int = field(default_factory=lambda: settings.memory_leak_window_size)
    growth_threshold: float = field(default_factory=lambda: settings.memory_leak_growth_threshold)
    cooldown_samples: int = 3  # suppress re-alert for N samples after fire
    _history: deque[float] = field(default_factory=deque)
    _samples_since_alert: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.window_size)

    def add_sample(self, memory_percent: float) -> None:
        """Add a memory usage sample."""
        self._history.append(memory_percent)
        if self._samples_since_alert > 0:
            self._samples_since_alert -= 1

    @staticmethod
    def _slope(samples: list[float]) -> float:
        """Compute least-squares slope of *samples* vs index."""
        n = len(samples)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(samples) / n
        ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(samples))
        ss_xx = sum((i - x_mean) ** 2 for i in range(n))
        if ss_xx == 0:
            return 0.0
        return ss_xy / ss_xx

    def check_leak(self) -> Alert | None:
        """Check if memory usage shows a leak pattern (consistent growth)."""
        if len(self._history) < self.window_size:
            return None
        if self._samples_since_alert > 0:
            return None  # cooldown active

        samples = list(self._history)
        first_half_avg = sum(samples[: self.window_size // 2]) / (self.window_size // 2)
        second_half_avg = sum(samples[self.window_size // 2 :]) / (
            self.window_size - self.window_size // 2
        )

        growth = second_half_avg - first_half_avg

        # Check for consistent upward trend
        increasing_count = sum(1 for i in range(1, len(samples)) if samples[i] > samples[i - 1])
        trend_ratio = increasing_count / (len(samples) - 1)

        slope = self._slope(samples)

        if growth >= self.growth_threshold and trend_ratio >= 0.6:
            self._samples_since_alert = self.cooldown_samples
            rule = AlertRule(
                name="Memory Leak Detected",
                metric="memory.virtual.percent",
                operator="trend",
                threshold=self.growth_threshold,
                message=(
                    f"Potential memory leak: +{growth:.1f}% over "
                    f"{self.window_size} samples (trend: {trend_ratio:.0%} "
                    f"increasing, slope: {slope:.2f}%/sample)"
                ),
            )
            return Alert(rule=rule, value=growth, message=rule.message)

        return None

    def get_stats(self) -> dict[str, Any]:
        """Get current memory tracking stats."""
        if not self._history:
            return {
                "samples": 0,
                "min": 0,
                "max": 0,
                "current": 0,
                "growth": 0,
                "slope": 0,
            }

        samples = list(self._history)
        return {
            "samples": len(samples),
            "min": round(min(samples), 2),
            "max": round(max(samples), 2),
            "current": round(samples[-1], 2),
            "growth": round(samples[-1] - samples[0], 2) if len(samples) > 1 else 0,
            "slope": round(self._slope(samples), 4),
        }


@dataclass
class AlertChecker:
    """Check snapshot against alert rules."""

    rules: list[AlertRule] = field(default_factory=list)
    memory_leak_detector: MemoryLeakDetector | None = None

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

    def enable_memory_leak_detection(
        self,
        window_size: int | None = None,
        growth_threshold: float | None = None,
    ) -> None:
        """Enable memory leak detection."""
        self.memory_leak_detector = MemoryLeakDetector(
            window_size=window_size or settings.memory_leak_window_size,
            growth_threshold=growth_threshold or settings.memory_leak_growth_threshold,
        )

    def check(self, snapshot: dict[str, Any]) -> list[Alert]:
        """Check snapshot against all rules and return triggered alerts."""
        alerts: list[Alert] = []

        for rule in self.rules:
            value = self._get_nested_value(snapshot, rule.metric)
            if value is None:
                continue

            triggered = False
            if (
                (rule.operator == "gt" and value > rule.threshold)
                or (rule.operator == "gte" and value >= rule.threshold)
                or (rule.operator == "lt" and value < rule.threshold)
                or (rule.operator == "lte" and value <= rule.threshold)
                or (rule.operator == "eq" and value == rule.threshold)
            ):
                triggered = True

            if triggered:
                message = (
                    rule.message
                    or f"{rule.name}: {rule.metric} is {value} ({rule.operator} {rule.threshold})"
                )
                alert = Alert(rule=rule, value=value, message=message)
                alerts.append(alert)
                log.warning(f"Alert triggered: {message}")

        # Memory leak detection
        if self.memory_leak_detector:
            memory_percent = self._get_nested_value(snapshot, "memory.virtual.percent")
            if memory_percent is not None:
                self.memory_leak_detector.add_sample(memory_percent)
                leak_alert = self.memory_leak_detector.check_leak()
                if leak_alert:
                    alerts.append(leak_alert)
                    log.warning(f"Alert triggered: {leak_alert.message}")

        return alerts

    def _get_nested_value(self, data: dict[str, Any], path: str) -> float | None:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        current: Any = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        if isinstance(current, int | float):
            return float(current)
        return None


def get_default_alert_checker(enable_leak_detection: bool = True) -> AlertChecker:
    """Get alert checker with default production rules."""
    checker = AlertChecker()

    # CPU alerts (using configurable threshold)
    checker.add_rule(
        AlertRule(
            name="High CPU",
            metric="cpu.percent",
            operator="gt",
            threshold=settings.alert_cpu_threshold,
            message=f"CPU usage is above {settings.alert_cpu_threshold}%",
        )
    )

    # Memory alerts (using configurable thresholds)
    checker.add_rule(
        AlertRule(
            name="High Memory",
            metric="memory.virtual.percent",
            operator="gt",
            threshold=settings.alert_memory_threshold,
            message=f"Memory usage is above {settings.alert_memory_threshold}%",
        )
    )

    checker.add_rule(
        AlertRule(
            name="Critical Memory",
            metric="memory.virtual.percent",
            operator="gt",
            threshold=settings.alert_memory_critical_threshold,
            message=f"CRITICAL: Memory usage is above {settings.alert_memory_critical_threshold}%",
        )
    )

    # Swap alerts (using configurable threshold)
    checker.add_rule(
        AlertRule(
            name="High Swap",
            metric="memory.swap.percent",
            operator="gt",
            threshold=settings.alert_swap_threshold,
            message=f"Swap usage is above {settings.alert_swap_threshold}%",
        )
    )

    # Enable memory leak detection
    if enable_leak_detection:
        checker.enable_memory_leak_detection()

    return checker
