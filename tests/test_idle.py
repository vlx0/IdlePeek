"""Idle math. No live scheme required."""

from __future__ import annotations

import unittest

from idlepeek.idle import format_after, format_span, leftover, overdue
from idlepeek.ui import _headline
from idlepeek.idle import Snap


class SpanTests(unittest.TestCase):
    def test_seconds(self) -> None:
        self.assertEqual(format_span(12), "12 с")

    def test_minutes(self) -> None:
        self.assertEqual(format_span(180), "3 мин")
        self.assertEqual(format_span(185), "3 мин 5 с")

    def test_hours(self) -> None:
        self.assertEqual(format_span(3600), "1 ч")
        self.assertEqual(format_span(5400), "1 ч 30 мин")

    def test_after(self) -> None:
        self.assertEqual(format_after(None), "не прочитан")
        self.assertEqual(format_after(0), "никогда")
        self.assertEqual(format_after(600), "через 10 мин")


class LeftoverTests(unittest.TestCase):
    def test_never(self) -> None:
        self.assertEqual(leftover(999, 0), "в схеме выключен")
        self.assertFalse(overdue(999, 0))

    def test_unknown(self) -> None:
        self.assertEqual(leftover(10, None), "не прочитан")
        self.assertFalse(overdue(10, None))

    def test_remaining(self) -> None:
        self.assertEqual(leftover(20, 80), "ещё 1 мин")
        self.assertFalse(overdue(20, 80))

    def test_overdue(self) -> None:
        self.assertEqual(leftover(90, 60), "уже должен был")
        self.assertTrue(overdue(60, 60))
        self.assertTrue(overdue(61, 60))


class HeadlineTests(unittest.TestCase):
    def test_sleep_overdue(self) -> None:
        text, color = _headline(Snap(idle_sec=700, sleep_sec=600, display_sec=300, scheme="Экономия энергии"))
        self.assertIn("Сон уже должен был", text)
        self.assertEqual(color, "#fca5a5")

    def test_display_overdue(self) -> None:
        text, color = _headline(Snap(idle_sec=400, sleep_sec=0, display_sec=300, scheme="Экономия энергии"))
        self.assertIn("Экран уже должен был", text)
        self.assertEqual(color, "#fde68a")

    def test_both_off(self) -> None:
        text, color = _headline(Snap(idle_sec=12, sleep_sec=0, display_sec=0, scheme="Высокая производительность"))
        self.assertIn("выключены", text)
        self.assertEqual(color, "#fde68a")
