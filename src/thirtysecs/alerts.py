"""Alert system for threshold-based monitoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

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
class AlertChecker:
    """Check snapshot against alert rules."""

    rules: list[AlertRule] = field(default_factory=list)

    def add_rule(self, rule: AlertRule) -> None:
        self.rules.append(rule)

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

        if isinstance(current, (int, float)):
            return float(current)
        return None


def get_default_alert_checker() -> AlertChecker:
    """Get alert checker with default production rules."""
    checker = AlertChecker()

    # CPU alerts
    checker.add_rule(
        AlertRule(
            name="High CPU",
            metric="cpu.percent",
            operator="gt",
            threshold=90,
            message="CPU usage is above 90%",
        )
    )

    # Memory alerts
    checker.add_rule(
        AlertRule(
            name="High Memory",
            metric="memory.virtual.percent",
            operator="gt",
            threshold=90,
            message="Memory usage is above 90%",
        )
    )

    checker.add_rule(
        AlertRule(
            name="Critical Memory",
            metric="memory.virtual.percent",
            operator="gt",
            threshold=95,
            message="CRITICAL: Memory usage is above 95%",
        )
    )

    # Swap alerts
    checker.add_rule(
        AlertRule(
            name="High Swap",
            metric="memory.swap.percent",
            operator="gt",
            threshold=80,
            message="Swap usage is above 80%",
        )
    )

    return checker
