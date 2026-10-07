"""A dependency-free Windows daily checklist."""

from datetime import date, datetime, timedelta
import logging
import os
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from types import TracebackType
from collections.abc import Callable

import startup
import style
from visuals import Dashboard
from store import Store, Task, clock


ABOUT_PATH = Path(__file__).resolve().with_name("ABOUT.md")


class App:
    def __init__(self, root: tk.Tk, store: Store):
        self.root = root
        self.store = store
        self.day = date.today()
        self.last_today = self.day
        self.visible_tasks: dict[str, Task] = {}
        self.signature: object = None
        self.timer: str | None = None
        self.fixed_signature: object = None
        self.fixed_suggestion: tuple[str, str] = ("", "")
        self.daily_suggestion: tuple[str, str] = ("", "")
        self.daily_form_day = self.day
        self.daily_drafts: dict[date, tuple[str, str, str]] = {}
        self.about_tab: ttk.Frame | None = None
        self.about_text: tk.Text | None = None
        self.theme = style.Theme(root)
        root.title("Everyday is a new chance.")
        root.geometry(style.WINDOW_SIZE)
        root.minsize(*style.MIN_WINDOW_SIZE)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error

        header = ttk.Frame(root, padding=(24, 18, 24, 0))
        header.pack(fill="x")
        self.motto = ttk.Label(
            header, text="Everyday is a new chance.", style="Title.TLabel"
        )
        self.motto.pack(side="left")
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=(16, 12))
        self.tasks_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_tab, text="Tasks")
        self.notebook.add(self.settings_tab, text="Settings")
        self.tasks_tab.columnconfigure(0, weight=1)
        self.tasks_tab.rowconfigure(2, weight=1)

        bar = ttk.Frame(self.tasks_tab, padding=12)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Button(bar, text="<", width=3, command=lambda: self.change_day(-1)).pack(side="left")
        self.day_label = ttk.Label(bar, style="Heading.TLabel")
        self.day_label.pack(side="left", padx=10)
        self.next_day_button = ttk.Button(bar, text=">", width=3, command=lambda: self.change_day(1))
        self.next_day_button.pack(side="left")
        ttk.Button(bar, text="Today", command=self.today).pack(side="left", padx=8)
        self.time_label = tk.Label(
            bar, **style.CLOCK_OPTIONS,
        )
        self.time_label.pack(side="right")

        self.dashboard = Dashboard(self.tasks_tab)
        self.dashboard.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        table = ttk.Frame(self.tasks_tab)
        table.grid(row=2, column=0, sticky="nsew", padx=12)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table, columns=("slot", "task", "status"), show="headings", selectmode="browse", height=4,
        )
        for name, label, width in (
            ("slot", "Time", 145), ("task", "Task", 420), ("status", "Status", 200),
        ):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, stretch=name in ("task", "status"))
        for status, (background, foreground) in style.STATUS_COLORS.items():
            self.tree.tag_configure(status, background=background, foreground=foreground)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.config(yscrollcommand=scrollbar.set)
        self.empty_label = ttk.Label(
            table, text="No tasks for this date.\nUse Add task to plan one.",
            style="Muted.TLabel", justify="center",
        )
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_buttons())
        daily_row = ttk.Frame(table)
        daily_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        for column, label in enumerate(("Start", "End", "Task")):
            ttk.Label(daily_row, text=label, style="Muted.TLabel").grid(
                row=0, column=column, sticky="w", pady=(6, 0)
            )
        self.daily_start = tk.StringVar(master=root)
        self.daily_end = tk.StringVar(master=root)
        self.daily_title = tk.StringVar(master=root)
        self.daily_entries, self.add_button = self._entry_row(
            daily_row, 1, self.daily_start, self.daily_end, self.daily_title, self.add_today
        )
        self.daily_feedback = ttk.Label(table, style="Error.TLabel", wraplength=700)
        self.daily_feedback.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        actions = ttk.Frame(self.tasks_tab, padding=12)
        actions.grid(row=3, column=0, sticky="ew")
        self.start_button = ttk.Button(actions, text="Start", style="Accent.TButton", command=self.start)
        self.start_button.pack(side="left")
        self.done_button = ttk.Button(actions, text="Done", style="Accent.TButton", command=self.done)
        self.done_button.pack(side="left", padx=8)
        self.remove_button = ttk.Button(actions, text="Remove", command=self.remove)
        self.remove_button.pack(side="left", padx=8)
        self.startup_var = tk.BooleanVar(master=root, value=startup.enabled())
        self.legend = ttk.Frame(self.tasks_tab, padding=(12, 0, 12, 8))
        self.legend.grid(row=4, column=0, sticky="ew")
        for status, label in (("pending", "Pending"), ("done", "Done"), ("missed", "Missed")):
            tk.Label(
                self.legend, text=label, **style.BADGE_OPTIONS,
                background=self.tree.tag_configure(status, "background"),
                foreground=self.tree.tag_configure(status, "foreground"),
            ).pack(side="left", padx=(0, 8))
        self.footer = ttk.Label(
            self.tasks_tab, style="Muted.TLabel", padding=(12, 0, 12, 16), wraplength=760
        )
        self.footer.grid(row=5, column=0, sticky="ew")
        self._build_settings()
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _event: self.reload_fixed_tasks(),
        )
        self.tick()
        root.after_idle(self.initialize_startup)

    def settings(self) -> None:
        self.notebook.select(self.settings_tab)
        self.reload_fixed_tasks()

    def _build_settings(self) -> None:
        self.settings_tab.columnconfigure(0, weight=1)
        self.settings_tab.rowconfigure(1, weight=1)
        controls = ttk.Frame(self.settings_tab)
        controls.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        reports = ttk.LabelFrame(controls, text="Summaries and help", padding=12)
        reports.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        report_actions = ttk.Frame(reports)
        report_actions.pack(fill="x")
        ttk.Button(report_actions, text="Daily summary", command=self.daily_summary).pack(
            side="left"
        )
        ttk.Button(report_actions, text="Monthly summary", command=self.monthly_summary).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(reports, text="About the app", command=self.show_about).pack(
            anchor="w", pady=(8, 0)
        )

        customization = ttk.LabelFrame(controls, text="Customization", padding=12)
        customization.grid(row=0, column=1, sticky="nsew")
        ttk.Button(customization, text="Deadline margin", command=self.margin).pack(
            anchor="w"
        )
        startup_check = ttk.Checkbutton(
            customization, text="Run at Windows sign-in",
            variable=self.startup_var, command=self.toggle_startup,
        )
        startup_check.pack(anchor="w", pady=(12, 0))
        if not startup.supported():
            startup_check.state(["disabled"])
        fixed = ttk.LabelFrame(
            self.settings_tab, text="Fixed weekday tasks - Monday to Friday", padding=12
        )
        fixed.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 12))
        fixed.columnconfigure(0, weight=1)
        fixed.rowconfigure(0, weight=1)
        table = ttk.Frame(fixed)
        table.grid(row=0, column=0, sticky="nsew")
        table.columnconfigure(2, weight=1)
        table.rowconfigure(0, weight=1)

        self.fixed_table = ttk.Treeview(
            table, columns=("start", "end", "title", "action"),
            show="headings", selectmode="browse", height=4,
        )
        for name, label in (("start", "Start"), ("end", "End"), ("title", "Task"), ("action", "")):
            self.fixed_table.heading(name, text=label)
        self.fixed_table.grid(row=0, column=0, columnspan=4, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, command=self.fixed_table.yview)
        scrollbar.grid(row=0, column=4, sticky="ns")
        self.fixed_table.config(yscrollcommand=scrollbar.set)

        self.fixed_start = tk.StringVar(master=self.root)
        self.fixed_end = tk.StringVar(master=self.root)
        self.fixed_title = tk.StringVar(master=self.root)
        self.fixed_entries, self.fixed_add_button = self._entry_row(
            table, 1, self.fixed_start, self.fixed_end, self.fixed_title, self.save_fixed_task
        )
        for index, name in ((0, "start"), (1, "end"), (3, "action")):
            width = (
                self.fixed_entries[index].winfo_reqwidth() + 8 if index < 2
                else self.fixed_add_button.winfo_reqwidth()
            )
            self.fixed_table.column(name, width=width, minwidth=width, stretch=False)
        self.fixed_table.column("title", width=280, minwidth=100)

        self.fixed_feedback = ttk.Label(fixed, style="Error.TLabel", wraplength=700)
        self.fixed_feedback.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        footer = ttk.Frame(fixed)
        footer.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(footer, text="Stop repeating", command=self.stop_fixed_task).pack(side="left")
        ttk.Label(
            footer, text="Enter a time slot and task in the row above, then press + Add task.",
            style="Muted.TLabel", wraplength=420,
        ).pack(side="left", padx=(12, 0))

    def _entry_row(
        self, parent: ttk.Frame, row: int, start: tk.StringVar, end: tk.StringVar,
        title: tk.StringVar, save: Callable[[], None],
    ) -> tuple[list[ttk.Entry], ttk.Button]:
        parent.columnconfigure(2, weight=1)
        entries = []
        for column, variable in enumerate((start, end, title)):
            entry = ttk.Entry(parent, textvariable=variable, width=6 if column < 2 else 20)
            entry.grid(row=row, column=column, sticky="ew", padx=(0, 8), pady=(8, 0))
            entry.bind("<Return>", lambda _event: save())
            entries.append(entry)
        button = ttk.Button(
            parent, text="+ Add task", style="Accent.TButton", command=save
        )
        button.grid(row=row, column=3, sticky="ew", pady=(8, 0))
        for column in (0, 1, 3):
            parent.columnconfigure(
                column, minsize=entries[column].winfo_reqwidth() + 8
                if column < 2 else button.winfo_reqwidth(),
            )
        return entries, button

    def suggest_times(self, now: datetime) -> None:
        if self.daily_form_day != self.day:
            values = (self.daily_title.get(), self.daily_start.get(), self.daily_end.get())
            if values[0] or values[1:] != self.daily_suggestion:
                self.daily_drafts[self.daily_form_day] = values
            else:
                self.daily_drafts.pop(self.daily_form_day, None)
            title, start, end = self.daily_drafts.get(self.day, ("", "", ""))
            self.daily_title.set(title)
            self.daily_start.set(start)
            self.daily_end.set(end)
            self.daily_suggestion = ("", "")
            self.daily_form_day = self.day
            self.daily_feedback.config(text="")
        earliest = 480
        if self.day == now.date():
            earliest = now.hour * 60 + now.minute + int(bool(now.second or now.microsecond))
        for start, end, previous, day, recurring, feedback in (
            (self.daily_start, self.daily_end, self.daily_suggestion, self.day, False, self.daily_feedback),
            (self.fixed_start, self.fixed_end, self.fixed_suggestion, now.date(), True, self.fixed_feedback),
        ):
            if (start.get(), end.get()) != previous:
                continue
            slot = self.store.first_free_slot(day, 480 if recurring else earliest, recurring=recurring)
            suggested = (clock(slot[0]), clock(slot[1])) if slot else ("", "")
            start.set(suggested[0])
            end.set(suggested[1])
            if recurring:
                self.fixed_suggestion = suggested
            else:
                self.daily_suggestion = suggested
            message = "No free 20-minute slot. Edit the times or choose another date."
            if not slot and not str(feedback["text"]):
                feedback.config(text=message)
            elif slot and str(feedback["text"]) == message:
                feedback.config(text="")

    def reload_fixed_tasks(self) -> None:
        templates = self.store.templates()
        signature = tuple((task["id"], task["title"], task["start"], task["end"]) for task in templates)
        if signature == self.fixed_signature:
            return
        selection = self.fixed_table.selection()
        self.fixed_table.delete(*self.fixed_table.get_children())
        for task in templates:
            self.fixed_table.insert("", "end", iid=str(task["id"]), values=(
                clock(task["start"]), clock(task["end"]), task["title"], "",
            ))
        if selection and self.fixed_table.exists(selection[0]):
            self.fixed_table.selection_set(selection[0])
        self.fixed_signature = signature

    def save_fixed_task(self) -> None:
        try:
            self.store.add_template(
                self.fixed_title.get(), self.fixed_start.get(), self.fixed_end.get(), date.today()
            )
        except ValueError as error:
            self.fixed_feedback.config(text=str(error))
            return
        self.fixed_title.set("")
        self.fixed_start.set("")
        self.fixed_end.set("")
        self.fixed_suggestion = ("", "")
        self.fixed_feedback.config(text="")
        self.refresh()
        self.fixed_entries[2].focus_set()

    def stop_fixed_task(self) -> None:
        selected = self.fixed_table.selection()
        if not selected:
            self.fixed_feedback.config(text="Select a fixed task first.")
            return
        if messagebox.askyesno(
            "Stop repeating", "Stop this task from tomorrow? Today's task and history are kept.",
            parent=self.root,
        ):
            self.store.remove_template(int(selected[0]), date.today())
            self.fixed_feedback.config(text="")
            self.refresh()

    def callback_error(
        self, kind: type[BaseException], error: BaseException, traceback: TracebackType | None
    ) -> None:
        logging.error("Application callback failed", exc_info=(kind, error, traceback))
        messagebox.showerror("Daily Todos error", str(error), parent=self.root)

    def initialize_startup(self) -> None:
        if startup.supported() and not self.store.setting("startup_initialized"):
            try:
                startup.set_enabled(True)
            except OSError as error:
                messagebox.showerror("Startup could not be enabled", str(error), parent=self.root)
                return
            self.startup_var.set(True)
            self.store.set_setting("startup_initialized", "yes")

    def toggle_startup(self) -> None:
        try:
            startup.set_enabled(self.startup_var.get())
        except OSError as error:
            self.startup_var.set(startup.enabled())
            messagebox.showerror("Startup setting failed", str(error), parent=self.root)
            return
        self.store.set_setting("startup_initialized", "yes")

    def tick(self) -> None:
        self.timer = None
        now = datetime.now()
        if now.date() != self.last_today:
            if self.day == self.last_today:
                self.day = now.date()
            self.last_today = now.date()
        try:
            self.refresh(now)
            if (
                now.hour >= 17
                and now > datetime.combine(now.date(), datetime.min.time())
                + timedelta(minutes=1020 + int(self.store.setting("margin")))
                and self.store.tasks(now.date())
                and self.store.setting("summary_shown") != now.date().isoformat()
            ):
                self.store.set_setting("summary_shown", now.date().isoformat())
                self.show_report("End-of-day summary", now.date(), now.date())
        except sqlite3.Error as error:
            logging.exception("Could not refresh task history")
            messagebox.showerror("Database error", str(error), parent=self.root)
            self.footer.config(text="History could not be refreshed. Restart the app after fixing the error.")
            return
        self.timer = self.root.after(1000, self.tick)

    def refresh(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        self.store.materialize(now.date())
        tasks = self.store.tasks(self.day)
        signature = (self.day, tuple((task, task.status(now)) for task in tasks))
        if signature != self.signature:
            selection = self.tree.selection()
            self.tree.delete(*self.tree.get_children())
            self.visible_tasks = {}
            for task in tasks:
                status = task.status(now)
                text = {
                    "done": "Done late" if task.late else "Done",
                    "missed": "Missed",
                    "pending": "Not started",
                }[status]
                if task.started_at and not task.done_at:
                    text = f"{text} / started {datetime.fromisoformat(task.started_at):%H:%M}"
                    if status == "pending":
                        text = f"Started {datetime.fromisoformat(task.started_at):%H:%M}"
                item = str(task.id)
                self.visible_tasks[item] = task
                self.tree.insert("", "end", iid=item, values=(
                    f"{clock(task.start)} - {clock(task.end)}", task.title,
                    text,
                ), tags=(status,))
            if selection and selection[0] in self.visible_tasks:
                self.tree.selection_set(selection[0])
            self.signature = signature
        self.day_label.config(text=self.day.strftime("%a, %d %b %Y"))
        today_tasks = tasks if self.day == now.date() else self.store.tasks(now.date())
        clock_warning = any(task.needs_attention(now) for task in today_tasks)
        self.time_label.config(
            text=now.strftime("%H:%M:%S"),
            background=style.COLORS["clock_red"] if clock_warning else style.COLORS["clock_green"],
        )
        self.footer.config(text=(
            f"08:00-17:00 | Margin: {self.store.setting('margin')} min"
        ))
        self.refresh_progress(tasks, now)
        self.suggest_times(now)
        self.update_buttons()
        self.reload_fixed_tasks()

    def refresh_progress(self, tasks: list[Task], now: datetime) -> None:
        completed = sum(bool(task.done_at) for task in tasks)
        pending = [task for task in tasks if not task.done_at]
        active = next((task for task in pending if task.started_at and not task.missed_at), None)
        upcoming = next((task for task in pending if task.status(now) == "pending"), None)
        focus = active or upcoming
        focus_heading = "Current task" if active else "Next task"
        if focus:
            focus_text = focus.title
            focus_detail = f"{clock(focus.start)} - {clock(focus.end)}"
        elif tasks and completed == len(tasks):
            focus_text, focus_detail = "All tasks done.", ""
        elif tasks:
            focus_text, focus_detail = "No upcoming tasks.", "Unfinished tasks remain in the list."
        else:
            focus_text, focus_detail = "No tasks scheduled.", ""
        self.dashboard.update_metrics(
            completed, len(tasks), focus_heading, focus_text, focus_detail
        )
        if tasks:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.6, anchor="center")

    def selected(self) -> Task | None:
        selection = self.tree.selection()
        return self.visible_tasks.get(selection[0]) if selection else None

    def update_buttons(self) -> None:
        task = self.selected()
        today = date.today()
        current = self.day == today
        planning = today <= self.day <= today + timedelta(days=7)
        unfinished = bool(current and task and not task.done_at)
        self.start_button.config(
            state="normal" if unfinished and task and not task.started_at and not task.missed_at else "disabled"
        )
        self.done_button.config(state="normal" if unfinished else "disabled")
        self.add_button.config(
            state="normal" if planning else "disabled",
        )
        for entry in self.daily_entries:
            entry.config(state="normal" if planning else "disabled")
        self.next_day_button.config(
            state="normal" if self.day < today + timedelta(days=7) else "disabled"
        )
        removable = bool(
            planning and task and not task.done_at and task.template_id is None
            and not task.started_at and not task.missed_at
        )
        self.remove_button.config(state="normal" if removable else "disabled")

    def change_day(self, delta: int) -> None:
        day = self.day + timedelta(days=delta)
        if day <= date.today() + timedelta(days=7):
            self.day = day
            self.refresh()

    def today(self) -> None:
        self.day = date.today()
        self.refresh()

    def start(self) -> None:
        task = self.selected()
        if task:
            self.store.start_task(task.id, datetime.now())
            self.refresh()

    def done(self) -> None:
        task = self.selected()
        if task:
            self.store.done_task(task.id, datetime.now())
            self.refresh()

    def remove(self) -> None:
        task = self.selected()
        if task and messagebox.askyesno("Remove task", f"Remove '{task.title}'?", parent=self.root):
            self.store.remove_task(task.id, self.day)
            self.refresh()

    def add_today(self) -> None:
        try:
            if not date.today() <= self.day <= date.today() + timedelta(days=7):
                raise ValueError("Choose a date from today through seven days ahead.")
            self.store.add_task(
                self.daily_title.get(), self.daily_start.get(), self.daily_end.get(), self.day
            )
        except ValueError as error:
            self.daily_feedback.config(text=str(error))
            return
        self.daily_title.set("")
        self.daily_start.set("")
        self.daily_end.set("")
        self.daily_suggestion = ("", "")
        self.daily_drafts.pop(self.day, None)
        self.daily_feedback.config(text="")
        self.refresh()
        self.daily_entries[2].focus_set()

    def margin(self) -> None:
        value = simpledialog.askinteger(
            "Deadline margin", "Minutes allowed after each task's end time (0-120):",
            initialvalue=int(self.store.setting("margin")), minvalue=0, maxvalue=120,
            parent=self.root,
        )
        if value is not None:
            self.store.set_margin(value, date.today())
            self.refresh()

    def daily_summary(self) -> None:
        self.show_report("Daily summary", self.day, self.day)

    def monthly_summary(self) -> None:
        value = simpledialog.askstring(
            "Monthly summary", "Month (YYYY-MM):", initialvalue=self.day.strftime("%Y-%m"),
            parent=self.root,
        )
        if value is None:
            return
        try:
            first = datetime.strptime(value, "%Y-%m").date().replace(day=1)
        except ValueError:
            messagebox.showerror("Invalid month", "Use YYYY-MM, for example 2026-10.", parent=self.root)
            return
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        self.show_report("Monthly summary", first, last)

    def show_report(self, title: str, first: date, last: date) -> None:
        now = datetime.now()
        self.store.materialize(now.date())
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("650x480")
        self._read_only_text(dialog, self.store.summary(first, last, now))

    def show_about(self) -> None:
        try:
            content = ABOUT_PATH.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            logging.exception("Could not read About the app documentation")
            messagebox.showerror("About the app could not open", str(error), parent=self.root)
            return
        if self.about_tab is None:
            self.about_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.about_tab, text="About the app")
            controls = ttk.Frame(self.about_tab, padding=12)
            controls.pack(fill="x")
            ttk.Button(controls, text="Back to Settings", command=self.settings).pack(side="left")
            self.about_text = self._read_only_text(self.about_tab, content)
        elif self.about_text is not None:
            self.about_text.config(state="normal")
            self.about_text.delete("1.0", "end")
            self.about_text.insert("1.0", content)
            self.about_text.config(state="disabled")
            self.about_text.yview_moveto(0)
        self.notebook.select(self.about_tab)

    def _read_only_text(self, parent: tk.Misc, content: str) -> tk.Text:
        text = tk.Text(parent, wrap="word", **style.REPORT_OPTIONS)
        scrollbar = ttk.Scrollbar(parent, command=text.yview)
        text.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", content)
        text.config(state="disabled")
        return text

    def close(self) -> None:
        if self.timer:
            self.root.after_cancel(self.timer)
        self.store.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DailyTodos"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=folder / "errors.log", level=logging.ERROR)
        store = Store(folder / "todos.sqlite3")
        App(root, store)
    except (OSError, sqlite3.Error) as error:
        logging.exception("Application initialization failed")
        messagebox.showerror("Daily Todos could not start", str(error), parent=root)
        root.destroy()
        return
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
