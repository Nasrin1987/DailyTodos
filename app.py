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
from ui import style
from ui.visuals import Dashboard
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
        self.backlog_signature: object = None
        self.goals_signature: object = None
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
        self.backlog_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_tab, text="Today")
        self.notebook.add(self.backlog_tab, text="Backlog")
        self.goals_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.goals_tab, text="5-Year Goals")
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
        self._build_backlog()
        self._build_goals()
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _event: self.reload_fixed_tasks(),
        )
        self.tick()
        root.after_idle(self.initialize_startup)

    def settings(self) -> None:
        self.notebook.select(self.settings_tab)
        self.reload_fixed_tasks()

    def _build_goals(self) -> None:
        panel = ttk.Frame(self.goals_tab, padding=12)
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="What do you want to achieve over the next five years?",
                  style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        table = ttk.Frame(panel)
        table.grid(row=1, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.goals_table = ttk.Treeview(table, columns=("title", "target", "status"),
                                       show="headings", selectmode="browse")
        for name, label, width in (("title", "Goal", 420), ("target", "Target date", 160), ("status", "Status", 160)):
            self.goals_table.heading(name, text=label)
            self.goals_table.column(name, width=width, stretch=name == "title")
        for status, (background, foreground) in style.STATUS_COLORS.items():
            self.goals_table.tag_configure(status, background=background, foreground=foreground)
        self.goals_table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, command=self.goals_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.goals_table.config(yscrollcommand=scrollbar.set)
        form = ttk.Frame(panel)
        form.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(0, weight=1)
        self.goal_title = tk.StringVar(master=self.root)
        today = date.today()
        target = today.replace(year=today.year + 5, day=min(today.day, 28)) if today.month == 2 else today.replace(year=today.year + 5)
        self.goal_target = tk.StringVar(master=self.root, value=target.isoformat())
        self.goal_entries = []
        for column, (label, variable, width) in enumerate((
            ("Goal title", self.goal_title, 40), ("Target date (YYYY-MM-DD)", self.goal_target, 24),
        )):
            ttk.Label(form, text=label, style="Muted.TLabel").grid(row=0, column=column, sticky="w")
            entry = ttk.Entry(form, textvariable=variable, width=width)
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(4, 0))
            entry.bind("<Return>", lambda _event: self.save_goal())
            self.goal_entries.append(entry)
        ttk.Button(form, text="+ Add goal", style="Accent.TButton", command=self.save_goal).grid(row=1, column=2, pady=(4, 0))
        actions = ttk.Frame(panel)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for label, command in (("Mark complete", lambda: self.complete_goal(True)),
                               ("Reopen", lambda: self.complete_goal(False)), ("Remove", self.remove_goal)):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 8))
        self.goals_feedback = ttk.Label(panel, style="Error.TLabel", wraplength=760)
        self.goals_feedback.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.goals_progress = ttk.Label(panel, style="Muted.TLabel")
        self.goals_progress.grid(row=5, column=0, sticky="w", pady=(8, 0))

    def reload_goals(self, today: date) -> None:
        goals = self.store.goals()
        signature = (today, tuple(tuple(goal) for goal in goals))
        if signature == self.goals_signature:
            return
        selected = self.goals_table.selection()
        self.goals_table.delete(*self.goals_table.get_children())
        for goal in goals:
            status = "done" if goal["completed_at"] else "missed" if goal["target_date"] < today.isoformat() else "pending"
            self.goals_table.insert("", "end", iid=str(goal["id"]), values=(
                goal["title"], goal["target_date"], {"done": "Completed", "missed": "Overdue", "pending": "In progress"}[status]), tags=(status,))
        if selected and self.goals_table.exists(selected[0]):
            self.goals_table.selection_set(selected[0])
        completed = sum(bool(goal["completed_at"]) for goal in goals)
        self.goals_progress.config(text=f"{completed} / {len(goals)} goals completed" if goals else "No goals yet. Add your first five-year goal above.")
        self.goals_signature = signature

    def save_goal(self) -> None:
        try:
            self.store.add_goal(self.goal_title.get(), self.goal_target.get(), date.today())
        except ValueError as error:
            self.goals_feedback.config(text=str(error))
            return
        self.goal_title.set("")
        self.goals_feedback.config(text="")
        self.refresh()
        self.goal_entries[0].focus_set()

    def complete_goal(self, completed: bool) -> None:
        selected = self.goals_table.selection()
        if not selected:
            self.goals_feedback.config(text="Select a goal first.")
            return
        self.store.set_goal_completed(int(selected[0]), completed, datetime.now())
        self.goals_feedback.config(text="")
        self.refresh()

    def remove_goal(self) -> None:
        selected = self.goals_table.selection()
        if not selected:
            self.goals_feedback.config(text="Select a goal first.")
            return
        title = self.goals_table.item(selected[0], "values")[0]
        if messagebox.askyesno("Remove goal", f"Remove '{title}'?", parent=self.root):
            self.store.remove_goal(int(selected[0]))
            self.goals_feedback.config(text="")
            self.refresh()

    def _build_backlog(self) -> None:
        panel = ttk.Frame(self.backlog_tab, padding=12)
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="Save tasks here, then move them into a day's schedule.",
                  style="Muted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        table = ttk.Frame(panel)
        table.grid(row=1, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.backlog_table = ttk.Treeview(table, columns=("title", "duration", "deadline"),
                                         show="headings", selectmode="browse")
        for name, label, width in (("title", "Task", 420), ("duration", "Duration", 120),
                                   ("deadline", "Deadline", 200)):
            self.backlog_table.heading(name, text=label)
            self.backlog_table.column(name, width=width, stretch=name == "title")
        self.backlog_table.tag_configure("overdue", foreground=style.COLORS["error"])
        self.backlog_table.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(table, command=self.backlog_table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.backlog_table.config(yscrollcommand=scrollbar.set)
        self.backlog_table.bind("<<TreeviewSelect>>", lambda _event: self.suggest_backlog_slot())
        form = ttk.Frame(panel)
        form.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        form.columnconfigure(0, weight=1)
        self.backlog_title = tk.StringVar(master=self.root)
        self.backlog_duration = tk.StringVar(master=self.root, value="20")
        self.backlog_deadline = tk.StringVar(master=self.root, value=date.today().isoformat())
        self.backlog_entries = []
        for column, (label, variable, width) in enumerate((
            ("Title", self.backlog_title, 30), ("Duration (minutes)", self.backlog_duration, 16),
            ("Deadline (YYYY-MM-DD)", self.backlog_deadline, 22),
        )):
            ttk.Label(form, text=label, style="Muted.TLabel").grid(row=0, column=column, sticky="w")
            entry = ttk.Entry(form, textvariable=variable, width=width)
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(4, 0))
            entry.bind("<Return>", lambda _event: self.save_backlog())
            self.backlog_entries.append(entry)
        ttk.Button(form, text="+ Add to backlog", style="Accent.TButton", command=self.save_backlog).grid(
            row=1, column=3, pady=(4, 0))
        schedule = ttk.LabelFrame(panel, text="Schedule selected task", padding=12)
        schedule.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.backlog_day = tk.StringVar(master=self.root, value=self.day.isoformat())
        self.backlog_start = tk.StringVar(master=self.root)
        ttk.Label(schedule, text="Day").grid(row=0, column=0, sticky="w")
        self.backlog_date_picker = ttk.Combobox(schedule, textvariable=self.backlog_day, width=12, state="readonly")
        self.backlog_date_picker.grid(row=1, column=0, padx=(0, 8))
        self.backlog_date_picker.bind("<<ComboboxSelected>>", lambda _event: self.suggest_backlog_slot())
        ttk.Label(schedule, text="Start (HH:MM)").grid(row=0, column=1, sticky="w")
        ttk.Entry(schedule, textvariable=self.backlog_start, width=12).grid(row=1, column=1, padx=(0, 8))
        ttk.Button(schedule, text="Find free slot", command=self.suggest_backlog_slot).grid(row=1, column=2, padx=(0, 8))
        ttk.Button(schedule, text="Move to day", style="Accent.TButton", command=self.schedule_backlog).grid(row=1, column=3)
        ttk.Button(schedule, text="Remove", command=self.remove_backlog).grid(row=1, column=4, padx=(8, 0))
        self.backlog_feedback = ttk.Label(panel, style="Error.TLabel", wraplength=760)
        self.backlog_feedback.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(panel, text="Deadline is a due date. Scheduling after it is allowed. Removing an unstarted\nscheduled task returns it to the backlog.",
                  style="Muted.TLabel").grid(row=5, column=0, sticky="w", pady=(8, 0))

    def reload_backlog(self, today: date) -> None:
        items = self.store.backlog()
        signature = (today, tuple(tuple(item) for item in items))
        if signature != self.backlog_signature:
            selection = self.backlog_table.selection()
            self.backlog_table.delete(*self.backlog_table.get_children())
            for item in items:
                overdue = item["due_date"] < today.isoformat()
                self.backlog_table.insert("", "end", iid=str(item["id"]), values=(
                    item["title"], f"{item['duration']} min", item["due_date"] + (" (overdue)" if overdue else "")),
                    tags=("overdue",) if overdue else ())
            if selection and self.backlog_table.exists(selection[0]):
                self.backlog_table.selection_set(selection[0])
            self.backlog_signature = signature
        dates = [(today + timedelta(days=offset)).isoformat() for offset in range(8)]
        self.backlog_date_picker.config(values=dates)
        if self.backlog_day.get() not in dates:
            self.backlog_day.set(today.isoformat())

    def save_backlog(self) -> None:
        try:
            self.store.add_backlog(self.backlog_title.get(), self.backlog_duration.get(), self.backlog_deadline.get())
        except ValueError as error:
            self.backlog_feedback.config(text=str(error))
            return
        self.backlog_title.set("")
        self.backlog_feedback.config(text="")
        self.refresh()
        self.backlog_entries[0].focus_set()

    def suggest_backlog_slot(self) -> None:
        selected = self.backlog_table.selection()
        if not selected:
            return
        item = next((item for item in self.store.backlog() if str(item["id"]) == selected[0]), None)
        if item is None:
            return
        now = datetime.now()
        day = date.fromisoformat(self.backlog_day.get())
        earliest = now.hour * 60 + now.minute + int(bool(now.second or now.microsecond)) if day == now.date() else 480
        slot = self.store.first_free_slot(day, earliest, item["duration"])
        self.backlog_start.set(clock(slot[0]) if slot else "")
        self.backlog_feedback.config(text="" if slot else "No free slot fits this task's duration. Choose another day or enter a start time.")

    def schedule_backlog(self) -> None:
        selected = self.backlog_table.selection()
        if not selected:
            self.backlog_feedback.config(text="Select a backlog task first.")
            return
        try:
            day = date.fromisoformat(self.backlog_day.get())
            self.store.schedule_backlog(int(selected[0]), day, self.backlog_start.get(), datetime.now())
        except ValueError as error:
            self.backlog_feedback.config(text=str(error))
            return
        self.backlog_feedback.config(text="")
        self.backlog_start.set("")
        self.day = day
        self.refresh()
        self.notebook.select(self.tasks_tab)

    def remove_backlog(self) -> None:
        selected = self.backlog_table.selection()
        if not selected:
            self.backlog_feedback.config(text="Select a backlog task first.")
            return
        title = self.backlog_table.item(selected[0], "values")[0]
        if messagebox.askyesno("Remove backlog task", f"Remove '{title}'?", parent=self.root):
            self.store.remove_backlog(int(selected[0]))
            self.backlog_feedback.config(text="")
            self.refresh()

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
        self.reload_backlog(now.date())
        self.reload_goals(now.date())


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
