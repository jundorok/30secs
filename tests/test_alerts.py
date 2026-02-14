"""Tests for alert system and memory leak detection."""

from thirtysecs.alerts import AlertChecker, AlertRule, MemoryLeakDetector, get_default_alert_checker
from thirtysecs.config import settings


class TestAlertRule:
    def test_alert_rule_creation(self):
        rule = AlertRule(
            name="Test Rule",
            metric="cpu.percent",
            operator="gt",
            threshold=80.0,
            message="CPU too high",
        )
        assert rule.name == "Test Rule"
        assert rule.threshold == 80.0


class TestAlertChecker:
    def test_check_cpu_alert_triggered(self):
        checker = AlertChecker()
        checker.add_rule(
            AlertRule(
                name="High CPU",
                metric="cpu.percent",
                operator="gt",
                threshold=90.0,
            )
        )

        snapshot = {"cpu": {"percent": 95.0}}
        alerts = checker.check(snapshot)

        assert len(alerts) == 1
        assert alerts[0].value == 95.0

    def test_check_no_alert_when_below_threshold(self):
        checker = AlertChecker()
        checker.add_rule(
            AlertRule(
                name="High CPU",
                metric="cpu.percent",
                operator="gt",
                threshold=90.0,
            )
        )

        snapshot = {"cpu": {"percent": 50.0}}
        alerts = checker.check(snapshot)

        assert len(alerts) == 0

    def test_nested_metric_path(self):
        checker = AlertChecker()
        checker.add_rule(
            AlertRule(
                name="High Memory",
                metric="memory.virtual.percent",
                operator="gt",
                threshold=80.0,
            )
        )

        snapshot = {"memory": {"virtual": {"percent": 85.0}}}
        alerts = checker.check(snapshot)

        assert len(alerts) == 1

    def test_default_checker_uses_config_thresholds(self):
        checker = get_default_alert_checker(enable_leak_detection=False)

        # Check that rules use config values
        cpu_rule = next(r for r in checker.rules if r.name == "High CPU")
        assert cpu_rule.threshold == settings.alert_cpu_threshold

        memory_rule = next(r for r in checker.rules if r.name == "High Memory")
        assert memory_rule.threshold == settings.alert_memory_threshold


class TestMemoryLeakDetector:
    def test_no_leak_with_insufficient_samples(self):
        detector = MemoryLeakDetector(window_size=5, growth_threshold=5.0)

        # Add fewer samples than window size
        for i in range(3):
            detector.add_sample(50.0 + i * 2)

        leak = detector.check_leak()
        assert leak is None

    def test_leak_detected_with_consistent_growth(self):
        detector = MemoryLeakDetector(window_size=5, growth_threshold=3.0)

        # Simulate consistent memory growth
        samples = [50.0, 52.0, 54.0, 56.0, 58.0]
        for s in samples:
            detector.add_sample(s)

        leak = detector.check_leak()
        assert leak is not None
        assert "memory leak" in leak.message.lower()

    def test_no_leak_with_stable_memory(self):
        detector = MemoryLeakDetector(window_size=5, growth_threshold=5.0)

        # Stable memory usage
        samples = [50.0, 50.5, 49.8, 50.2, 50.1]
        for s in samples:
            detector.add_sample(s)

        leak = detector.check_leak()
        assert leak is None

    def test_no_leak_with_fluctuating_memory(self):
        detector = MemoryLeakDetector(window_size=5, growth_threshold=5.0)

        # Memory goes up and down
        samples = [50.0, 55.0, 48.0, 53.0, 51.0]
        for s in samples:
            detector.add_sample(s)

        leak = detector.check_leak()
        assert leak is None

    def test_stats(self):
        detector = MemoryLeakDetector(window_size=5, growth_threshold=5.0)

        samples = [50.0, 52.0, 54.0]
        for s in samples:
            detector.add_sample(s)

        stats = detector.get_stats()
        assert stats["samples"] == 3
        assert stats["min"] == 50.0
        assert stats["max"] == 54.0
        assert stats["current"] == 54.0
        assert stats["growth"] == 4.0

    def test_sliding_window(self):
        detector = MemoryLeakDetector(window_size=3, growth_threshold=5.0)

        # Fill window
        for s in [10.0, 20.0, 30.0]:
            detector.add_sample(s)

        # Add more samples - should slide
        detector.add_sample(40.0)
        detector.add_sample(50.0)

        stats = detector.get_stats()
        assert stats["samples"] == 3
        assert stats["min"] == 30.0  # Old samples pushed out


class TestAlertCheckerWithLeakDetection:
    def test_leak_detection_enabled_by_default(self):
        checker = get_default_alert_checker()
        assert checker.memory_leak_detector is not None

    def test_leak_detection_can_be_disabled(self):
        checker = get_default_alert_checker(enable_leak_detection=False)
        assert checker.memory_leak_detector is None

    def test_check_includes_leak_detection(self):
        checker = AlertChecker()
        checker.enable_memory_leak_detection(window_size=3, growth_threshold=2.0)

        # Simulate snapshots with growing memory
        snapshots = [
            {"memory": {"virtual": {"percent": 50.0}}},
            {"memory": {"virtual": {"percent": 53.0}}},
            {"memory": {"virtual": {"percent": 56.0}}},
        ]

        alerts = []
        for snap in snapshots:
            alerts = checker.check(snap)

        # After enough samples, leak should be detected
        leak_alerts = [a for a in alerts if "leak" in a.message.lower()]
        assert len(leak_alerts) == 1
