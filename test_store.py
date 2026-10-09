from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest

from store import Store, TaskOverlapError, validate_task


class StoreTests(unittest.TestCase):
    def test_backlog_validation_order_and_persistence(self) -> None:
        for title, duration, deadline in (("", "20", "2026-10-05"), ("x", "0", "2026-10-05"),
                                          ("x", "541", "2026-10-05"), ("x", "1.5", "2026-10-05"),
                                          ("x", "20", "2026-02-30"), ("x", "20", "20261005")):
            with self.subTest(title=title, duration=duration, deadline=deadline), self.assertRaises(ValueError):
                self.store.add_backlog(title, duration, deadline)
        self.store.add_backlog(" Later ", "45", "2026-10-12")
        self.store.add_backlog("Urgent", "30", "2026-10-05")
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual([row["title"] for row in self.store.backlog()], ["Urgent", "Later"])

    def test_backlog_move_is_atomic_and_preserves_due_date(self) -> None:
        self.store.add_backlog("Work", "45", "2026-10-05")
        item = self.store.backlog()[0]
        now = datetime(2026, 10, 5, 8)
        future = self.day + timedelta(days=1)
        self.store.add_template("Routine", "08:00", "09:00", self.day)
        for day, start in ((future, "08:30"), (future, "16:30"), (self.day - timedelta(days=1), "09:00"),
                           (self.day + timedelta(days=8), "09:00")):
            with self.subTest(day=day, start=start), self.assertRaises(ValueError):
                self.store.schedule_backlog(item["id"], day, start, now)
            self.assertEqual(len(self.store.backlog()), 1)
            self.assertEqual(self.store.tasks(future), [])
        self.store.schedule_backlog(item["id"], future, "09:00", now)
        self.assertEqual(self.store.backlog(), [])
        task = self.store.tasks(future)[0]
        self.assertEqual((task.title, task.start, task.end), ("Work", 540, 585))
        with self.assertRaises(ValueError):
            self.store.schedule_backlog(item["id"], future, "10:00", now)
        self.assertEqual(len(self.store.tasks(future)), 1)
        self.store.remove_task(task.id, future)
        self.assertEqual(self.store.backlog()[0]["due_date"], "2026-10-05")
        self.store.remove_backlog(item["id"])
        self.assertEqual(self.store.backlog(), [])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.day = date(2026, 10, 5)  # Monday
        self.path = Path(self.temp.name) / "todos.sqlite3"
        self.store = Store(self.path, self.day)

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_validation(self) -> None:
        self.assertEqual(validate_task(" Work ", "08:00", "17:00"), ("Work", 480, 1020))
        for title, begin, end in (
            ("", "08:00", "09:00"), ("x", "07:59", "09:00"),
            ("x", "16:00", "17:01"), ("x", "09:00", "09:00"),
            ("x", "bad", "09:00"),
        ):
            with self.subTest(title=title, begin=begin, end=end), self.assertRaises(ValueError):
                validate_task(title, begin, end)

    def test_lists_are_sorted_by_slot_not_insertion_order(self) -> None:
        for title, start, end in (
            ("Afternoon", "14:00", "15:00"), ("Morning", "08:00", "09:00"),
            ("Lunch", "12:00", "13:00"),
        ):
            self.store.add_template(title, start, end, self.day)
        self.assertEqual([row["title"] for row in self.store.templates()], ["Morning", "Lunch", "Afternoon"])
        self.store.add_task("Daily", "10:00", "11:00", self.day)
        self.assertEqual(
            [task.title for task in self.store.tasks(self.day)],
            ["Morning", "Daily", "Lunch", "Afternoon"],
        )

    def test_first_free_slot_now_boundaries_and_short_gaps(self) -> None:
        self.assertEqual(self.store.first_free_slot(self.day, 400), (480, 500))
        self.assertEqual(self.store.first_free_slot(self.day, 615), (615, 635))
        self.store.add_task("First", "08:00", "08:10", self.day)
        self.store.add_task("Second", "08:25", "09:00", self.day)
        self.assertEqual(self.store.first_free_slot(self.day), (540, 560))
        self.assertEqual(self.store.first_free_slot(self.day, 1000), (1000, 1020))
        self.assertIsNone(self.store.first_free_slot(self.day, 1001))
        self.assertIsNone(self.store.first_free_slot(self.day, 1020))
        for duration in (0, -1, 541):
            with self.assertRaises(ValueError):
                self.store.first_free_slot(self.day, duration=duration)

    def test_free_slot_uses_template_lifetimes_without_materializing_future(self) -> None:
        self.store.add_template("Routine", "08:00", "09:00", self.day)
        future = self.day + timedelta(days=7)
        generated = self.store.setting("generated_through")
        self.assertEqual(self.store.first_free_slot(future), (540, 560))
        self.assertEqual(self.store.tasks(future), [])
        self.assertEqual(self.store.setting("generated_through"), generated)
        self.store.remove_template(self.store.templates()[0]["id"], self.day)
        self.assertEqual(self.store.first_free_slot(self.day), (540, 560))
        self.assertEqual(self.store.first_free_slot(future), (480, 500))
        weekend = self.day + timedelta(days=5)
        self.assertEqual(self.store.first_free_slot(weekend), (480, 500))

    def test_fixed_free_slot_considers_all_future_weekdays_not_weekends_or_history(self) -> None:
        self.store.add_task("History", "08:00", "09:00", self.day - timedelta(days=1))
        self.store.add_task("Weekend", "08:00", "09:00", self.day + timedelta(days=5))
        self.store.add_task("Future", "08:00", "08:45", self.day + timedelta(days=7))
        self.store.add_template("Routine", "09:00", "10:00", self.day)
        self.assertEqual(self.store.first_free_slot(self.day, recurring=True), (600, 620))
        self.store.add_template("Long routine", "10:00", "17:00", self.day)
        self.assertIsNone(self.store.first_free_slot(self.day, recurring=True))

    def test_daily_overlap_rejected_but_touching_slots_allowed(self) -> None:
        self.store.add_task("Existing", "09:00", "10:00", self.day)
        for start, end in (
            ("09:00", "10:00"), ("08:30", "09:30"), ("09:30", "10:30"),
            ("09:15", "09:45"), ("08:00", "11:00"),
        ):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "Existing"):
                self.store.add_task("Conflict", start, end, self.day)
        self.assertEqual(len(self.store.tasks(self.day)), 1)
        self.store.add_task("Before", "08:00", "09:00", self.day)
        self.store.add_task("After", "10:00", "11:00", self.day)
        self.store.add_task("Another date", "09:00", "10:00", self.day + timedelta(days=1))
        self.assertEqual(len(self.store.tasks(self.day)), 3)

    def test_fixed_overlap_rejected_and_adjacent_routine_allowed(self) -> None:
        self.store.add_template("Routine", "09:00", "10:00", self.day)
        for start, end in (("09:00", "10:00"), ("08:30", "09:30"),
                           ("09:30", "10:30"), ("08:00", "11:00")):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(TaskOverlapError, "Routine"):
                self.store.add_template("Conflict", start, end, self.day)
        self.assertEqual(len(self.store.templates()), 1)
        self.assertEqual(len(self.store.tasks(self.day)), 1)
        self.store.add_template("After", "10:00", "11:00", self.day)
        self.store.add_template("Before", "08:00", "09:00", self.day)
        self.assertEqual([row["title"] for row in self.store.templates()], ["Before", "Routine", "After"])

    def test_future_daily_task_checked_against_unmaterialized_fixed_task(self) -> None:
        self.store.add_template("Routine", "09:00", "10:00", self.day)
        future = self.day + timedelta(days=7)
        self.assertEqual(self.store.tasks(future), [])
        with self.assertRaisesRegex(TaskOverlapError, "Routine.*09:00-10:00"):
            self.store.add_task("Planned conflict", "09:30", "10:30", future)
        self.assertEqual(self.store.tasks(future), [])
        self.store.add_task("Planned after", "10:00", "11:00", future)

    def test_fixed_task_checked_against_future_daily_task(self) -> None:
        future = self.day + timedelta(days=7)
        self.store.add_task("Planned meeting", "09:00", "10:00", future)
        with self.assertRaisesRegex(TaskOverlapError, "Planned meeting.*2026-10-12"):
            self.store.add_template("Conflict", "09:30", "10:30", self.day)
        self.assertEqual(self.store.templates(), [])
        self.assertEqual(self.store.tasks(self.day), [])
        self.assertEqual(len(self.store.tasks(future)), 1)

    def test_weekend_daily_tasks_do_not_conflict_with_weekday_routine(self) -> None:
        saturday = date(2026, 10, 10)
        self.store.add_task("Weekend", "09:00", "10:00", saturday)
        self.store.add_template("Routine", "09:00", "10:00", saturday)
        self.store.add_task("Sunday", "09:00", "10:00", saturday + timedelta(days=1))
        with self.assertRaises(TaskOverlapError):
            self.store.add_task("Monday conflict", "09:00", "10:00", saturday + timedelta(days=2))

    def test_stopped_routine_keeps_today_reserved_but_frees_future_slots(self) -> None:
        self.store.add_template("Old routine", "09:00", "10:00", self.day)
        self.store.remove_template(self.store.templates()[0]["id"], self.day)
        with self.assertRaisesRegex(TaskOverlapError, "Old routine"):
            self.store.add_task("Today conflict", "09:00", "10:00", self.day)
        with self.assertRaisesRegex(TaskOverlapError, "Old routine"):
            self.store.add_template("Replacement today", "09:00", "10:00", self.day)
        self.store.add_template("Replacement tomorrow", "09:00", "10:00", self.day + timedelta(days=1))
        self.assertEqual(self.store.tasks(self.day)[0].title, "Old routine")

    def test_new_routine_ignores_past_daily_tasks(self) -> None:
        self.store.add_task("Yesterday's meeting", "09:00", "10:00", self.day)
        self.store.add_template("New routine", "09:00", "10:00", self.day + timedelta(days=1))
        self.assertEqual(len(self.store.templates()), 1)

    def test_existing_overlaps_are_preserved_on_reopen(self) -> None:
        self.store.add_task("Existing", "09:00", "10:00", self.day)
        with self.store.db:
            self.store.db.execute("""
                INSERT INTO tasks (day, title, start, end, margin)
                VALUES (?, 'Legacy overlap', 570, 630, 10)
            """, (self.day.isoformat(),))
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(len(self.store.tasks(self.day)), 2)
        with self.assertRaises(TaskOverlapError):
            self.store.add_task("New overlap", "10:00", "11:00", self.day)
        self.assertEqual(len(self.store.tasks(self.day)), 2)

    def test_gray_red_green_and_boundary(self) -> None:
        self.store.add_task("Work", "08:00", "09:00", self.day)
        task = self.store.tasks(self.day)[0]
        self.assertEqual(task.status(datetime(2026, 10, 5, 9, 10)), "pending")
        self.assertEqual(task.status(datetime(2026, 10, 5, 9, 10, 1)), "missed")
        self.store.start_task(task.id, datetime(2026, 10, 5, 8))
        self.store.done_task(task.id, datetime(2026, 10, 5, 9, 11))
        completed = self.store.tasks(self.day)[0]
        self.assertEqual(completed.status(datetime(2026, 10, 5, 18)), "done")
        self.assertTrue(completed.late)
        with self.assertRaises(ValueError):
            self.store.done_task(task.id, datetime(2026, 10, 5, 10))

    def test_repeats_weekdays_and_recovers_closed_days(self) -> None:
        self.store.add_template("Routine", "08:00", "08:30", self.day)
        future = self.day + timedelta(days=7)
        self.store.materialize(future)
        self.store.materialize(future)
        for offset in range(8):
            day = self.day + timedelta(days=offset)
            tasks = self.store.tasks(day)
            self.assertEqual(len(tasks), 1 if day.weekday() < 5 else 0)
        report = self.store.summary(self.day, future, datetime(2026, 10, 12, 18))
        self.assertIn("Missed: 6", report)

    def test_template_changes_preserve_history(self) -> None:
        self.store.add_template("Old", "08:00", "08:30", self.day)
        next_day = self.day + timedelta(days=1)
        template = self.store.templates()[0]
        self.store.remove_template(template["id"], next_day)
        self.store.add_template("New", "09:00", "09:30", next_day)
        self.store.materialize(next_day + timedelta(days=1))
        self.assertEqual([t.title for t in self.store.tasks(self.day)], ["Old"])
        self.assertEqual([t.title for t in self.store.tasks(next_day)], ["Old", "New"])
        self.assertEqual([t.title for t in self.store.tasks(next_day + timedelta(days=1))], ["New"])

    def test_margin_snapshots_and_persistence(self) -> None:
        self.store.add_template("Routine", "08:00", "08:30", self.day)
        next_day = self.day + timedelta(days=1)
        self.store.materialize(next_day)
        task = self.store.tasks(next_day)[0]
        self.store.done_task(task.id, datetime(2026, 10, 6, 8, 35))
        self.store.add_task("Extra", "09:00", "09:30", next_day)
        self.store.set_margin(20, next_day)
        self.assertEqual(self.store.tasks(self.day)[0].margin, 10)
        self.assertEqual([t.margin for t in self.store.tasks(next_day)], [10, 20])
        self.store.close()
        self.store = Store(self.path)
        self.assertIsNotNone(self.store.tasks(next_day)[0].done_at)
        self.assertEqual(self.store.setting("margin"), "20")
        with self.assertRaises(ValueError):
            self.store.set_margin(-1, next_day)

    def test_summaries_and_readonly_history(self) -> None:
        for title, begin, end in (
            ("On time", "08:00", "09:00"), ("Late", "09:00", "10:00"),
            ("Missed", "10:00", "11:00"),
        ):
            self.store.add_task(title, begin, end, self.day)
        tasks = self.store.tasks(self.day)
        self.store.done_task(tasks[0].id, datetime(2026, 10, 5, 9, 10))
        self.store.done_task(tasks[1].id, datetime(2026, 10, 5, 10, 11))
        report = self.store.summary(date(2026, 10, 1), date(2026, 10, 31), datetime(2026, 10, 5, 18))
        for expected in ("Completed: 2/3 (67%)", "On time (including margin): 1",
                         "Completed late: 1", "Missed: 1", "What went well"):
            self.assertIn(expected, report)
        with self.assertRaises(ValueError):
            self.store.done_task(tasks[2].id, datetime(2026, 10, 6, 8))
        with self.assertRaises(ValueError):
            self.store.remove_task(tasks[0].id, self.day)

    def test_daily_tasks_do_not_repeat_and_can_be_removed(self) -> None:
        weekend = date(2026, 10, 10)
        self.store.add_task("One off", "08:00", "09:00", weekend)
        task = self.store.tasks(weekend)[0]
        self.store.materialize(weekend + timedelta(days=1))
        self.assertEqual(self.store.tasks(weekend + timedelta(days=1)), [])
        self.store.remove_task(task.id, weekend)
        self.assertEqual(self.store.tasks(weekend), [])

    def test_margin_attention_boundaries(self) -> None:
        self.store.add_task("Work", "08:00", "09:00", self.day)
        task = self.store.tasks(self.day)[0]
        self.assertFalse(task.needs_attention(datetime(2026, 10, 5, 8, 59, 59)))
        for now in (datetime(2026, 10, 5, 9), datetime(2026, 10, 5, 9, 10),
                    datetime(2026, 10, 5, 10)):
            self.assertTrue(task.needs_attention(now))
        self.assertEqual(task.status(datetime(2026, 10, 5, 9, 5)), "pending")
        self.assertFalse(task.needs_attention(datetime(2026, 10, 6, 9)))
        self.store.done_task(task.id, datetime(2026, 10, 5, 9, 5))
        self.assertFalse(self.store.tasks(self.day)[0].needs_attention(datetime(2026, 10, 5, 9, 6)))

    def test_start_next_marks_previous_missed_and_persists(self) -> None:
        for title, begin, end in (
            ("First", "08:00", "08:30"), ("Skipped", "08:30", "09:00"),
            ("Next", "09:00", "10:00"), ("Future", "10:00", "11:00"),
        ):
            self.store.add_task(title, begin, end, self.day)
        first, skipped, next_task, future = self.store.tasks(self.day)
        self.store.start_task(first.id, datetime(2026, 10, 5, 8))
        now = datetime(2026, 10, 5, 9, 5)
        self.store.start_task(next_task.id, now)
        tasks = self.store.tasks(self.day)
        self.assertEqual([task.status(now) for task in tasks], ["missed", "missed", "pending", "pending"])
        self.assertFalse(any(task.needs_attention(now) for task in tasks))
        self.assertIsNone(tasks[-1].missed_at)
        self.assertIn("Missed: 2", self.store.summary(self.day, self.day, now))
        with self.assertRaises(ValueError):
            self.store.start_task(skipped.id, now)
        with self.assertRaises(ValueError):
            self.store.remove_task(skipped.id, self.day)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.tasks(self.day)[0].status(now), "missed")
        self.store.done_task(first.id, datetime(2026, 10, 5, 9, 6))
        self.assertEqual(self.store.tasks(self.day)[0].status(now), "done")

    def test_switching_early_marks_started_task_missed(self) -> None:
        self.store.add_task("First", "08:00", "09:00", self.day)
        self.store.add_task("Next", "09:00", "10:00", self.day)
        first, next_task = self.store.tasks(self.day)
        self.store.start_task(first.id, datetime(2026, 10, 5, 8))
        with self.assertRaises(ValueError):
            self.store.start_task(-1, datetime(2026, 10, 5, 8, 30))
        self.assertIsNone(self.store.tasks(self.day)[0].missed_at)
        now = datetime(2026, 10, 5, 8, 45)
        self.store.start_task(next_task.id, now)
        self.assertEqual(self.store.tasks(self.day)[0].status(now), "missed")

    def test_legacy_database_migration_preserves_tasks(self) -> None:
        legacy_path = Path(self.temp.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_path)) as db:
            db.executescript("""
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY, day TEXT NOT NULL, title TEXT NOT NULL,
                    start INTEGER NOT NULL, end INTEGER NOT NULL, margin INTEGER NOT NULL,
                    template_id INTEGER, started_at TEXT, done_at TEXT,
                    UNIQUE(day, template_id)
                );
                INSERT INTO tasks VALUES (
                    1, '2026-10-05', 'Existing task', 480, 540, 10, NULL, NULL, NULL
                );
            """)
        legacy = Store(legacy_path, self.day)
        try:
            task = legacy.tasks(self.day)[0]
            self.assertEqual(task.title, "Existing task")
            self.assertIsNone(task.missed_at)
            legacy.start_task(task.id, datetime(2026, 10, 5, 8))
        finally:
            legacy.close()

    def test_planned_tasks_persist_and_follow_margin_changes(self) -> None:
        future = self.day + timedelta(days=7)
        self.store.add_task("Planned", "08:00", "09:00", future)
        task = self.store.tasks(future)[0]
        self.store.set_margin(25, self.day)
        self.assertEqual(self.store.tasks(future)[0].margin, 25)
        for action in (self.store.start_task, self.store.done_task):
            with self.assertRaises(ValueError):
                action(task.id, datetime(2026, 10, 5, 8))
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.tasks(future)[0].title, "Planned")
        self.assertEqual(self.store.tasks(future)[0].status(datetime(2026, 10, 5, 18)), "pending")


if __name__ == "__main__":
    unittest.main()
