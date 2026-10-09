"""Local schedules, immutable daily snapshots, and completion history."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sqlite3


def minutes(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError("Use a time in HH:MM format, for example 08:30.") from exc
    return parsed.hour * 60 + parsed.minute


def validate_task(title: str, start: str, end: str) -> tuple[str, int, int]:
    title = title.strip()
    if not title:
        raise ValueError("Enter a task name.")
    begin, finish = minutes(start), minutes(end)
    if not 480 <= begin < finish <= 1020:
        raise ValueError("The time slot must be between 08:00 and 17:00, with start before end.")
    return title, begin, finish


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


class TaskOverlapError(ValueError):
    pass


@dataclass(frozen=True)
class Task:
    id: int
    day: str
    title: str
    start: int
    end: int
    margin: int
    template_id: int | None
    started_at: str | None
    done_at: str | None
    missed_at: str | None = None

    @property
    def slot_end(self) -> datetime:
        return datetime.combine(date.fromisoformat(self.day), time()) + timedelta(
            minutes=self.end
        )

    @property
    def deadline(self) -> datetime:
        return self.slot_end + timedelta(minutes=self.margin)

    def status(self, now: datetime) -> str:
        if self.done_at:
            return "done"
        return "missed" if self.missed_at or now > self.deadline else "pending"

    def needs_attention(self, now: datetime) -> bool:
        return (
            self.day == now.date().isoformat()
            and not self.done_at
            and not self.missed_at
            and now >= self.slot_end
        )

    @property
    def late(self) -> bool:
        return bool(self.done_at and datetime.fromisoformat(self.done_at) > self.deadline)

class Store:
    def __init__(self, path: Path, today: date | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                start INTEGER NOT NULL, end INTEGER NOT NULL,
                active_from TEXT NOT NULL, active_until TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, day TEXT NOT NULL, title TEXT NOT NULL,
                start INTEGER NOT NULL, end INTEGER NOT NULL, margin INTEGER NOT NULL,
                template_id INTEGER, started_at TEXT, done_at TEXT, missed_at TEXT,
                UNIQUE(day, template_id)
            );
            CREATE INDEX IF NOT EXISTS tasks_day ON tasks(day);
            CREATE TABLE IF NOT EXISTS backlog (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                duration INTEGER NOT NULL CHECK(duration BETWEEN 1 AND 540),
                due_date TEXT NOT NULL, scheduled_task_id INTEGER
            );
        """)
        with self.db:
            columns = {row["name"] for row in self.db.execute("PRAGMA table_info(tasks)")}
            if "missed_at" not in columns:
                self.db.execute("ALTER TABLE tasks ADD COLUMN missed_at TEXT")
            self.db.execute(
                "INSERT OR IGNORE INTO settings VALUES ('first_day', ?)",
                ((today or date.today()).isoformat(),),
            )
            self.db.execute("INSERT OR IGNORE INTO settings VALUES ('margin', '10')")

    def close(self) -> None:
        self.db.close()

    def backlog(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM backlog WHERE scheduled_task_id IS NULL ORDER BY due_date, id"
        ).fetchall()

    def add_backlog(self, title: str, duration: str, due_date: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("Enter a task name.")
        try:
            length = int(duration)
        except (ValueError, TypeError) as error:
            raise ValueError("Enter a duration in whole minutes (1-540).") from error
        if not 1 <= length <= 540:
            raise ValueError("Enter a duration in whole minutes (1-540).")
        try:
            due = date.fromisoformat(due_date).isoformat()
            if due != due_date:
                raise ValueError
        except ValueError as error:
            raise ValueError("Use a deadline date in YYYY-MM-DD format.") from error
        with self.db:
            self.db.execute(
                "INSERT INTO backlog (title, duration, due_date) VALUES (?, ?, ?)",
                (title, length, due),
            )

    def schedule_backlog(self, item_id: int, day: date, start: str, now: datetime) -> None:
        if not now.date() <= day <= now.date() + timedelta(days=7):
            raise ValueError("Choose a date from today through seven days ahead.")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            item = self.db.execute(
                "SELECT * FROM backlog WHERE id = ? AND scheduled_task_id IS NULL", (item_id,)
            ).fetchone()
            if item is None:
                raise ValueError("This backlog task has already been scheduled or removed.")
            begin = minutes(start)
            title, begin, finish = validate_task(item["title"], start, clock(begin + item["duration"]))
            self._check_overlap(begin, finish, day, recurring=False)
            task = self.db.execute(
                "INSERT INTO tasks (day, title, start, end, margin) VALUES (?, ?, ?, ?, ?)",
                (day.isoformat(), title, begin, finish, int(self.setting("margin"))),
            )
            self.db.execute(
                "UPDATE backlog SET scheduled_task_id = ? WHERE id = ?", (task.lastrowid, item_id)
            )

    def remove_backlog(self, item_id: int) -> None:
        with self.db:
            changed = self.db.execute(
                "DELETE FROM backlog WHERE id = ? AND scheduled_task_id IS NULL", (item_id,)
            ).rowcount
        if not changed:
            raise ValueError("Select an unscheduled backlog task first.")

    def setting(self, key: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))

    def set_margin(self, margin: int, today: date) -> None:
        if not 0 <= margin <= 120:
            raise ValueError("The margin must be between 0 and 120 minutes.")
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO settings VALUES ('margin', ?)", (str(margin),)
            )
            self.db.execute(
                "UPDATE tasks SET margin = ? WHERE day >= ? AND done_at IS NULL",
                (margin, today.isoformat()),
            )

    def materialize(self, today: date) -> None:
        # Reconstruct days missed while the app was closed using template lifetimes.
        first = date.fromisoformat(self.setting("generated_through", self.setting("first_day")))
        margin = int(self.setting("margin"))
        with self.db:
            day = first
            while day <= today:
                if day.weekday() < 5:
                    self.db.execute("""
                        INSERT OR IGNORE INTO tasks
                            (day, title, start, end, margin, template_id)
                        SELECT ?, title, start, end, ?, id FROM templates
                        WHERE active_from <= ? AND (active_until IS NULL OR active_until >= ?)
                    """, (day.isoformat(), margin, day.isoformat(), day.isoformat()))
                day += timedelta(days=1)
            if today >= first:
                self.db.execute(
                    "INSERT OR REPLACE INTO settings VALUES ('generated_through', ?)",
                    (today.isoformat(),),
                )

    def templates(self) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM templates WHERE active_until IS NULL ORDER BY start, end, id"
        ).fetchall()

    def _reservations(self, day: date, recurring: bool) -> list[sqlite3.Row]:
        parameters = {"day": day.isoformat()}
        reservations: list[sqlite3.Row] = []
        if recurring or day.weekday() < 5:
            template_dates = (
                "active_until IS NULL" if recurring else
                "active_from <= :day AND (active_until IS NULL OR active_until >= :day)"
            )
            reservations.extend(self.db.execute(f"""
                SELECT title, start, end, NULL AS day FROM templates
                WHERE {template_dates} ORDER BY start, end, id
            """, parameters).fetchall())
        task_dates = (
            "day >= :day AND strftime('%w', day) BETWEEN '1' AND '5'"
            if recurring else "day = :day"
        )
        reservations.extend(self.db.execute(f"""
            SELECT title, day, start, end FROM tasks
            WHERE {task_dates} ORDER BY day, start, end, id
        """, parameters).fetchall())
        return reservations

    def _check_overlap(self, begin: int, finish: int, day: date, recurring: bool) -> None:
        for conflict in self._reservations(day, recurring):
            if conflict["start"] >= finish or conflict["end"] <= begin:
                continue
            description = (
                f"fixed task '{conflict['title']}'" if conflict["day"] is None
                else f"'{conflict['title']}' on {conflict['day']}"
            )
            raise TaskOverlapError(
                f"Overlaps with {description} "
                f"({clock(conflict['start'])}-{clock(conflict['end'])}). "
                "Choose a different time slot."
            )

    def first_free_slot(
        self, day: date, earliest: int = 480, duration: int = 20, *, recurring: bool = False,
    ) -> tuple[int, int] | None:
        if duration < 1 or duration > 540:
            raise ValueError("The suggested duration must be between 1 and 540 minutes.")
        begin = max(480, earliest)
        for reservation in sorted(self._reservations(day, recurring), key=lambda row: row["start"]):
            if reservation["end"] <= begin:
                continue
            if begin + duration <= reservation["start"]:
                break
            begin = reservation["end"]
        return (begin, begin + duration) if begin + duration <= 1020 else None

    def add_template(self, title: str, start: str, end: str, today: date) -> None:
        title, begin, finish = validate_task(title, start, end)
        self.materialize(today)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._check_overlap(begin, finish, today, recurring=True)
            self.db.execute(
                "INSERT INTO templates (title, start, end, active_from) VALUES (?, ?, ?, ?)",
                (title, begin, finish, today.isoformat()),
            )
        self.materialize(today)

    def remove_template(self, template_id: int, today: date) -> None:
        self.materialize(today)
        with self.db:
            self.db.execute(
                "UPDATE templates SET active_until = ? WHERE id = ?",
                ((today - timedelta(days=1)).isoformat(), template_id),
            )

    def add_task(self, title: str, start: str, end: str, day: date) -> None:
        title, begin, finish = validate_task(title, start, end)
        with self.db:
            # Hold the write lock across validation and insertion for other app instances.
            self.db.execute("BEGIN IMMEDIATE")
            self._check_overlap(begin, finish, day, recurring=False)
            self.db.execute("""
                INSERT INTO tasks (day, title, start, end, margin)
                VALUES (?, ?, ?, ?, ?)
            """, (day.isoformat(), title, begin, finish, int(self.setting("margin"))))

    def tasks(self, day: date) -> list[Task]:
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE day = ? ORDER BY start, end, id", (day.isoformat(),)
        ).fetchall()
        return [Task(**dict(row)) for row in rows]

    def start_task(self, task_id: int, now: datetime) -> None:
        with self.db:
            changed = self.db.execute("""
                UPDATE tasks SET started_at = ?
                WHERE id = ? AND day = ? AND done_at IS NULL AND started_at IS NULL
                AND missed_at IS NULL
            """, (now.isoformat(), task_id, now.date().isoformat())).rowcount
            if not changed:
                raise ValueError("Only an unstarted, unfinished task from today that hasn't been skipped can be started.")
            # Starting another task acknowledges earlier unfinished work as missed.
            self.db.execute("""
                UPDATE tasks SET missed_at = ?
                WHERE day = ? AND id != ? AND done_at IS NULL AND missed_at IS NULL
                AND (started_at IS NOT NULL OR end <= ?)
            """, (now.isoformat(), now.date().isoformat(), task_id, now.hour * 60 + now.minute))

    def done_task(self, task_id: int, now: datetime) -> None:
        with self.db:
            changed = self.db.execute("""
                UPDATE tasks SET done_at = ?
                WHERE id = ? AND day = ? AND done_at IS NULL
            """, (now.isoformat(), task_id, now.date().isoformat())).rowcount
        if not changed:
            raise ValueError("Only an unfinished task from today can be completed.")

    def remove_task(self, task_id: int, day: date) -> None:
        with self.db:
            changed = self.db.execute("""
                DELETE FROM tasks WHERE id = ? AND day = ?
                AND template_id IS NULL AND started_at IS NULL AND done_at IS NULL
                AND missed_at IS NULL
            """, (task_id, day.isoformat())).rowcount
            if changed:
                self.db.execute("UPDATE backlog SET scheduled_task_id = NULL WHERE scheduled_task_id = ?", (task_id,))
        if not changed:
            raise ValueError("Only an unstarted date-specific task from the selected date can be removed.")

    def summary(self, first: date, last: date, now: datetime) -> str:
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE day BETWEEN ? AND ? ORDER BY day, start, id",
            (first.isoformat(), last.isoformat()),
        ).fetchall()
        tasks = [Task(**dict(row)) for row in rows]
        on_time = [task for task in tasks if task.done_at and not task.late]
        late = [task for task in tasks if task.late]
        missed = [task for task in tasks if task.status(now) == "missed"]
        pending = [task for task in tasks if task.status(now) == "pending"]
        done = len(on_time) + len(late)
        rate = f"{done / len(tasks):.0%}" if tasks else "N/A"
        lines = [
            f"{first.isoformat()} to {last.isoformat()}",
            f"Completed: {done}/{len(tasks)} ({rate})",
            f"On time (including margin): {len(on_time)}",
            f"Completed late: {len(late)}",
            f"Missed: {len(missed)} | Still pending: {len(pending)}",
            "",
        ]
        for heading, group in (
            ("What went well", on_time),
            ("Finished, but later than planned", late),
            ("Needs attention", missed),
        ):
            lines.append(heading)
            lines.extend(f"  {task.day}  {clock(task.start)}  {task.title}" for task in group)
            if not group:
                lines.append("  None yet.")
            lines.append("")
        if not tasks:
            lines.append("No tasks were scheduled in this period.")
        return "\n".join(lines)
