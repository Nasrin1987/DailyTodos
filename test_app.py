from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from app import ABOUT_PATH, App
import startup
import style
import color_scheme
from store import Store


class UITests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "todos.sqlite3")
        self.store.set_setting("summary_shown", date.today().isoformat())
        self.startup_enabled = patch("startup.enabled", return_value=False)
        self.startup_supported = patch("startup.supported", return_value=False)
        self.startup_enabled.start()
        self.startup_supported.start()
        self.app = App(self.root, self.store)
        self.callback_errors: list[BaseException] = []
        self.root.report_callback_exception = lambda _kind, error, _traceback: self.callback_errors.append(error)
        self.root.update()

    def tearDown(self) -> None:
        self.app.close()
        self.startup_enabled.stop()
        self.startup_supported.stop()
        self.temp.cleanup()
        self.assertEqual(self.callback_errors, [], "Tkinter callbacks must not fail silently")

    def test_task_colors_and_start_done_controls(self) -> None:
        today = date.today()
        self.store.add_task("Test task", "08:00", "09:00", today)
        self.app.refresh(datetime.combine(today, datetime.min.time()).replace(hour=8))
        item = self.app.tree.get_children()[0]
        self.assertEqual(self.app.tree.item(item, "tags"), ("pending",))
        self.app.tree.selection_set(item)
        self.app.update_buttons()
        self.assertEqual(str(self.app.start_button["state"]), "normal")
        self.app.start()
        self.assertIsNotNone(self.store.tasks(today)[0].started_at)
        self.assertEqual(str(self.app.start_button["state"]), "disabled")
        self.app.refresh(datetime.combine(today, datetime.min.time()).replace(hour=10))
        self.assertEqual(self.app.tree.item(item, "tags"), ("missed",))
        self.app.done()
        self.assertEqual(self.app.tree.item(item, "tags"), ("done",))
        self.assertEqual(str(self.app.done_button["state"]), "disabled")
        self.assertEqual(str(self.app.remove_button["state"]), "disabled")

    def test_history_is_readonly_and_report_renders(self) -> None:
        self.store.add_task("Today", "08:00", "09:00", date.today())
        self.app.refresh()
        self.app.change_day(-1)
        self.assertEqual(str(self.app.add_button["state"]), "disabled")
        self.app.today()
        self.app.daily_summary()
        windows = [child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)]
        self.assertEqual(len(windows), 1)
        text = next(child for child in windows[0].winfo_children() if isinstance(child, tk.Text))
        self.assertIn("Completed: 0/1", text.get("1.0", "end"))
        self.assertEqual(str(text["state"]), "disabled")

    def test_fixed_tasks_table_renders_in_settings_tab(self) -> None:
        self.store.add_template("Routine", "08:00", "08:30", date.today())
        self.app.settings()
        windows = [child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)]
        self.assertEqual(windows, [])
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))
        items = self.app.fixed_table.get_children()
        self.assertEqual(len(items), 1)
        self.assertEqual(self.app.fixed_table.item(items[0], "values"), ("08:00", "08:30", "Routine", ""))

    def test_fixed_task_controls_are_not_clipped(self) -> None:
        self.root.deiconify()
        self.root.wait_visibility()
        self.app.settings()
        for size in (style.WINDOW_SIZE, f"{style.MIN_WINDOW_SIZE[0]}x{style.MIN_WINDOW_SIZE[1]}"):
            self.root.geometry(size)
            self.root.update()
            self.root.update_idletasks()
            for label, button in self.controls(self.app.settings_tab).items():
                with self.subTest(size=size, control=label):
                    self.assertTrue(button.winfo_ismapped())
                    self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                    self.assertLessEqual(
                        button.winfo_rooty() - self.root.winfo_rooty() + button.winfo_reqheight(),
                        self.root.winfo_height(),
                    )
                    self.assertLessEqual(
                        button.winfo_rootx() - self.root.winfo_rootx() + button.winfo_reqwidth(),
                        self.root.winfo_width(),
                    )
            for entry in self.app.fixed_entries:
                self.assertTrue(entry.winfo_ismapped())
            self.assertGreater(self.app.fixed_table.winfo_height(), 40)

    def test_fixed_task_plus_button_adds_and_refreshes_table(self) -> None:
        self.app.settings()
        add_button = self.app.fixed_add_button
        self.assertEqual(str(add_button["style"]), "Accent.TButton")
        self.app.fixed_title.set("Morning routine")
        with patch("app.tk.Toplevel", side_effect=AssertionError("No extra window expected")):
            add_button.invoke()
        templates = self.store.templates()
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["title"], "Morning routine")
        listing = self.app.fixed_table
        items = listing.get_children()
        self.assertEqual(len(items), 1)
        self.assertEqual(listing.item(items[0], "values"), ("08:00", "08:20", "Morning routine", ""))
        self.assertEqual(self.app.fixed_title.get(), "")
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)], [])
        if date.today().weekday() < 5:
            self.assertEqual(self.store.tasks(date.today())[0].title, "Morning routine")

    def test_daily_row_rejects_overlap_and_keeps_input_for_correction(self) -> None:
        today = date.today()
        self.store.add_template("Existing routine", "08:00", "09:00", today)
        self.app.day = today + timedelta(days=max(0, 7 - today.weekday()) if today.weekday() >= 5 else 0)

        self.app.refresh()
        self.app.daily_title.set("Conflicting task")
        self.app.daily_start.set("08:00")
        self.app.daily_end.set("08:30")
        with (
            patch("app.tk.Toplevel", side_effect=AssertionError("No editor window expected")),
            patch("app.messagebox.showerror") as show_error,
        ):
            self.app.add_button.invoke()
            show_error.assert_not_called()
        self.assertIn("Existing routine", str(self.app.daily_feedback["text"]))
        self.assertEqual(self.app.daily_title.get(), "Conflicting task")
        self.assertEqual(len(self.store.templates()), 1)
        self.assertFalse(any(task.title == "Conflicting task" for task in self.store.tasks(self.app.day)))

    def test_inline_fixed_row_rejects_overlap_without_popup(self) -> None:
        self.store.add_template("Existing routine", "08:00", "09:00", date.today())
        self.app.settings()
        self.app.fixed_title.set("Conflict")
        self.app.fixed_start.set("08:00")
        self.app.fixed_end.set("08:30")
        with patch("app.messagebox.showerror") as show_error:
            self.app.fixed_add_button.invoke()
            show_error.assert_not_called()
        self.assertIn("Existing routine", str(self.app.fixed_feedback["text"]))
        self.assertEqual(self.app.fixed_title.get(), "Conflict")
        self.assertEqual(len(self.store.templates()), 1)
        self.app.fixed_start.set("09:00")
        self.app.fixed_end.set("09:30")
        self.app.fixed_add_button.invoke()
        self.assertEqual(len(self.store.templates()), 2)
        self.assertEqual(str(self.app.fixed_feedback["text"]), "")

    def test_fixed_row_validation_and_draft_survive_tab_changes(self) -> None:
        self.app.settings()
        self.app.fixed_add_button.invoke()
        self.assertIn("task name", str(self.app.fixed_feedback["text"]))
        self.app.fixed_title.set("Draft")
        self.app.fixed_start.set("bad")
        self.app.fixed_add_button.invoke()
        self.assertIn("HH:MM", str(self.app.fixed_feedback["text"]))
        self.app.notebook.select(self.app.tasks_tab)
        self.app.refresh()
        self.app.settings()
        self.assertEqual(self.app.fixed_title.get(), "Draft")
        self.assertEqual(self.app.fixed_start.get(), "bad")
        self.assertEqual(self.store.templates(), [])

    def test_enter_in_fixed_row_saves_without_an_editor_window(self) -> None:
        self.root.deiconify()
        self.root.wait_visibility()
        self.app.settings()
        self.root.update()
        self.app.fixed_title.set("Keyboard task")
        self.app.fixed_entries[2].focus_force()
        self.root.update()
        self.app.fixed_entries[2].event_generate("<Return>")
        self.root.update()
        self.assertEqual(self.store.templates()[0]["title"], "Keyboard task")
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)], [])

    def test_stop_fixed_task_from_settings_keeps_history(self) -> None:
        self.store.add_template("Routine", "08:00", "08:30", date.today())
        self.app.settings()
        self.app.stop_fixed_task()
        self.assertIn("Select a fixed task", str(self.app.fixed_feedback["text"]))
        self.app.fixed_table.selection_set(self.app.fixed_table.get_children()[0])
        with patch("app.messagebox.askyesno", return_value=True):
            self.controls(self.app.settings_tab)["Stop repeating"].invoke()
        self.assertEqual(self.store.templates(), [])
        self.assertEqual(self.app.fixed_table.get_children(), ())
        if date.today().weekday() < 5:
            self.assertEqual(self.store.tasks(date.today())[0].title, "Routine")

    def test_fixed_and_daily_tables_sort_new_earlier_tasks(self) -> None:
        self.store.add_template("Afternoon", "14:00", "15:00", date.today())
        self.app.settings()
        self.app.fixed_title.set("Morning")
        self.app.fixed_add_button.invoke()
        listing = self.app.fixed_table
        self.assertEqual(
            [listing.item(item, "values")[2] for item in listing.get_children()],
            ["Morning", "Afternoon"],
        )
        self.store.add_task("Later daily", "16:00", "17:00", date.today())
        self.store.add_task("Earlier daily", "10:00", "11:00", date.today())
        self.app.refresh()
        times = [self.app.tree.item(item, "values")[0] for item in self.app.tree.get_children()]
        self.assertEqual(times, sorted(times))

    def test_theme_uses_rounded_images_and_preserves_button_states(self) -> None:
        theme = self.app.theme
        self.assertEqual(str(self.root["background"]), style.COLORS["background"])
        self.assertEqual(str(self.app.motto["style"]), "Title.TLabel")
        self.assertEqual(str(self.app.start_button["style"]), "Accent.TButton")
        for name, images in theme.images.items():
            self.assertIn("Friendly.", theme.style.layout(name)[0][0])
            self.assertEqual(set(images), {"normal", "disabled", "pressed", "active", "focus"})
            for image in images.values():
                self.assertTrue(image.transparency_get(0, 0))
                self.assertFalse(image.transparency_get(image.width() // 2, image.height() // 2))
                self.assertIn(str(image), self.root.image_names())
            self.assertNotEqual(
                images["normal"].get(images["normal"].width() // 2, images["normal"].height() // 2),
                images["active"].get(images["active"].width() // 2, images["active"].height() // 2),
            )
            self.assertNotEqual(
                images["normal"].get(images["normal"].width() // 2, 0),
                images["focus"].get(images["focus"].width() // 2, 0),
            )
            self.assertEqual(
                theme.style.lookup(name, "foreground", ("disabled",)), style.COLORS["disabled_text"]
            )
        self.assertEqual(str(self.app.start_button["state"]), "disabled")

    def test_styled_controls_fit_minimum_window(self) -> None:
        width, height = style.MIN_WINDOW_SIZE
        self.root.geometry(f"{width}x{height}")
        self.root.deiconify()
        self.root.wait_visibility()
        self.root.update_idletasks()
        for label, button in self.controls(self.app.tasks_tab).items():
            with self.subTest(control=label):
                self.assertGreater(button.winfo_width(), 1)
                self.assertGreaterEqual(button.winfo_x(), 0)
                self.assertLessEqual(
                    button.winfo_x() + button.winfo_width(), button.master.winfo_width()
                )
                self.assertLessEqual(
                    button.winfo_rooty() - self.root.winfo_rooty() + button.winfo_reqheight(),
                    self.root.winfo_height(),
                )
        for entry in self.app.daily_entries:
            self.assertTrue(entry.winfo_ismapped())
            self.assertGreaterEqual(entry.winfo_height(), entry.winfo_reqheight())
            self.assertLessEqual(
                entry.winfo_rooty() - self.root.winfo_rooty() + entry.winfo_reqheight(),
                self.root.winfo_height(),
            )
        self.assertGreater(self.app.tree.winfo_height(), 40)
        self.app.settings()
        self.root.update_idletasks()
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))

    def test_motto_and_one_week_navigation_limit(self) -> None:
        self.assertEqual(str(self.app.motto["text"]), "Everyday is a new chance.")
        today = date.today()
        for offset in range(1, 8):
            self.app.next_day_button.invoke()
            self.assertEqual(self.app.day, today + timedelta(days=offset))
            self.assertEqual(str(self.app.add_button["state"]), "normal")
        self.assertEqual(str(self.app.next_day_button["state"]), "disabled")
        self.app.change_day(1)
        self.assertEqual(self.app.day, today + timedelta(days=7))
        self.app.change_day(-1)
        self.assertEqual(str(self.app.next_day_button["state"]), "normal")
        self.app.today()
        self.assertEqual(str(self.app.add_button["text"]), "+ Add task")

    def test_add_future_task_row_saves_selected_day_and_can_remove(self) -> None:
        target = date.today() + timedelta(days=7)
        self.app.change_day(7)

        self.app.daily_title.set("Next week's task")
        with patch("app.tk.Toplevel", side_effect=AssertionError("No editor window expected")):
            self.app.add_button.invoke()
        tasks = self.store.tasks(target)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Next week's task")
        self.assertEqual(self.store.tasks(date.today()), [])
        self.assertEqual(self.store.setting("generated_through"), date.today().isoformat())
        self.app.tree.selection_set(str(tasks[0].id))
        self.app.update_buttons()
        self.assertEqual(str(self.app.start_button["state"]), "disabled")
        self.assertEqual(str(self.app.done_button["state"]), "disabled")
        self.assertEqual(str(self.app.remove_button["state"]), "normal")
        with patch("app.messagebox.askyesno", return_value=True):
            self.app.remove_button.invoke()
        self.assertEqual(self.store.tasks(target), [])

    def test_daily_row_rejects_date_outside_planning_window(self) -> None:
        for offset in (-1, 8):
            self.app.day = date.today() + timedelta(days=offset)

            self.app.daily_title.set("Invalid date")
            with patch("app.messagebox.showerror") as show_error:
                self.app.add_today()
                show_error.assert_not_called()
            self.assertIn("seven days", str(self.app.daily_feedback["text"]))
            self.assertEqual(self.store.tasks(self.app.day), [])

    def test_today_suggestion_uses_now_and_next_free_twenty_minutes(self) -> None:
        today = date.today()
        now = datetime.combine(today, datetime.min.time()).replace(hour=10, minute=5, second=12)
        self.app.daily_start.set("")
        self.app.daily_end.set("")
        self.app.daily_suggestion = ("", "")
        self.app.refresh(now)
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("10:06", "10:26"))
        self.store.add_task("Busy", "10:00", "10:40", today)
        self.app.refresh(now)
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("10:40", "11:00"))
        self.app.daily_title.set("New task")
        with (
            patch("app.datetime") as mocked,
            patch("app.tk.Toplevel", side_effect=AssertionError("No editor window expected")),
        ):
            mocked.now.return_value = now
            mocked.fromisoformat.side_effect = datetime.fromisoformat
            self.app.add_button.invoke()
        self.assertEqual([task.title for task in self.store.tasks(today)], ["Busy", "New task"])
        self.assertEqual(self.app.daily_title.get(), "")
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("11:00", "11:20"))

    def test_daily_drafts_and_custom_times_survive_refresh_and_date_changes(self) -> None:
        self.app.daily_title.set("Draft for today")
        self.app.daily_start.set("12:15")
        self.app.daily_end.set("12:45")
        self.app.refresh()
        self.assertEqual(self.app.daily_start.get(), "12:15")
        self.app.change_day(1)
        self.assertEqual(self.app.daily_title.get(), "")
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("08:00", "08:20"))
        self.app.daily_title.set("Tomorrow's draft")
        self.app.change_day(-1)
        self.assertEqual(self.app.daily_title.get(), "Draft for today")
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("12:15", "12:45"))
        self.app.change_day(1)
        self.assertEqual(self.app.daily_title.get(), "Tomorrow's draft")

    def test_no_free_slot_feedback_and_manual_shorter_slot(self) -> None:
        today = date.today()
        now = datetime.combine(today, datetime.min.time()).replace(hour=16, minute=50)
        self.app.daily_start.set("")
        self.app.daily_end.set("")
        self.app.daily_suggestion = ("", "")
        self.app.refresh(now)
        self.assertIn("No free 20-minute slot", str(self.app.daily_feedback["text"]))
        self.assertEqual((self.app.daily_start.get(), self.app.daily_end.get()), ("", ""))
        self.app.daily_title.set("Short task")
        self.app.daily_start.set("16:50")
        self.app.daily_end.set("17:00")
        self.app.add_button.invoke()
        self.assertEqual(self.store.tasks(today)[0].title, "Short task")

    def test_fixed_suggestions_skip_short_gaps_and_future_daily_reservations(self) -> None:
        today = date.today()
        target = today + timedelta(days=(7 - today.weekday()) % 7)
        self.store.add_task("Planned", "08:00", "08:45", target)
        self.store.add_template("Routine", "09:00", "10:00", today)
        self.app.refresh()
        self.assertEqual((self.app.fixed_start.get(), self.app.fixed_end.get()), ("10:00", "10:20"))
        self.app.fixed_title.set("New routine")
        self.app.fixed_add_button.invoke()
        self.assertEqual((self.app.fixed_start.get(), self.app.fixed_end.get()), ("10:20", "10:40"))

    def test_daily_row_enter_and_history_readonly(self) -> None:
        self.root.deiconify()
        self.root.wait_visibility()
        self.app.change_day(1)
        self.app.daily_title.set("Keyboard daily task")
        self.app.daily_entries[2].focus_force()
        self.root.update()
        self.app.daily_entries[2].event_generate("<Return>")
        self.root.update()
        self.assertEqual(self.store.tasks(self.app.day)[0].title, "Keyboard daily task")
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)], [])
        self.app.change_day(-2)
        for entry in self.app.daily_entries:
            self.assertEqual(str(entry["state"]), "disabled")
        self.assertEqual(str(self.app.add_button["state"]), "disabled")

    def test_boxed_clock_margin_done_and_next_start(self) -> None:
        today = date.today()
        at = datetime.combine(today, datetime.min.time())
        self.store.add_task("First", "08:00", "09:00", today)
        self.store.add_task("Next", "09:00", "10:00", today)
        first, next_task = self.store.tasks(today)
        self.store.start_task(first.id, at.replace(hour=8))
        self.app.refresh(at.replace(hour=8, minute=59, second=59))
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_green"])
        self.assertEqual(str(self.app.time_label["relief"]), "solid")
        self.assertGreater(int(self.app.time_label["borderwidth"]), 0)
        self.app.refresh(at.replace(hour=9))
        self.assertEqual(str(self.app.time_label["text"]), "09:00:00")
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_red"])
        self.app.refresh(at.replace(hour=9, minute=5))
        self.assertEqual(self.app.tree.item(str(first.id), "tags"), ("pending",))
        self.app.tree.selection_set(str(next_task.id))
        self.app.update_buttons()
        with patch("app.datetime") as mocked_time:
            mocked_time.now.return_value = at.replace(hour=9, minute=5)
            mocked_time.fromisoformat.side_effect = datetime.fromisoformat
            self.app.start_button.invoke()
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_green"])
        self.assertEqual(self.app.tree.item(str(first.id), "tags"), ("missed",))
        self.app.refresh(at.replace(hour=10))
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_red"])
        self.store.done_task(next_task.id, at.replace(hour=10, minute=2))
        self.app.refresh(at.replace(hour=10, minute=2))
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_green"])
        self.assertEqual(self.app.tree.item(str(first.id), "tags"), ("missed",))
        self.assertEqual(self.app.tree.item(str(next_task.id), "tags"), ("done",))

    def test_clock_uses_today_when_browsing_history(self) -> None:
        today = date.today()
        self.app.refresh()
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_green"])
        self.store.add_task("Today", "08:00", "09:00", today)
        self.app.day = today - timedelta(days=1)
        self.app.refresh(datetime.combine(today, datetime.min.time()).replace(hour=9, minute=5))
        self.assertEqual(str(self.app.time_label["background"]), style.COLORS["clock_red"])

    def test_legend_uses_labeled_color_boxes(self) -> None:
        boxes = self.app.legend.winfo_children()
        self.assertEqual([str(box["text"]) for box in boxes], ["Pending", "Done", "Missed"])
        for box, status in zip(boxes, ("pending", "done", "missed")):
            self.assertIsInstance(box, tk.Label)
            self.assertEqual(str(box["background"]), str(self.app.tree.tag_configure(status, "background")))
            self.assertEqual(str(box["foreground"]), str(self.app.tree.tag_configure(status, "foreground")))
            self.assertEqual(str(box["relief"]), "solid")
            self.assertGreater(int(box["borderwidth"]), 0)
        for text in ("Gray: pending", "Green: done", "Red: missed"):
            self.assertNotIn(text, str(self.app.footer["text"]))
        self.app.refresh()
        self.assertEqual([str(box["text"]) for box in boxes], ["Pending", "Done", "Missed"])

    def controls(self, parent: tk.Misc) -> dict[str, ttk.Button | ttk.Checkbutton]:
        result: dict[str, ttk.Button | ttk.Checkbutton] = {}
        for child in parent.winfo_children():
            if isinstance(child, tk.Toplevel):
                continue
            if isinstance(child, (ttk.Button, ttk.Checkbutton)):
                result[str(child["text"])] = child
            result.update(self.controls(child))
        return result

    def test_settings_is_a_tab_without_extra_windows(self) -> None:
        moved = {
            "Daily summary", "Monthly summary", "+ Add task", "Stop repeating",
            "Deadline margin", "Run at Windows sign-in", "About the app",
        }
        main_controls = self.controls(self.app.tasks_tab)
        self.assertTrue({"Start", "Done", "+ Add task", "Remove"} <= main_controls.keys())
        self.assertTrue((moved - {"+ Add task"}).isdisjoint(main_controls))
        self.assertIs(main_controls["+ Add task"], self.app.add_button)
        self.app.settings()
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))
        self.assertEqual(
            [self.app.notebook.tab(tab, "text") for tab in self.app.notebook.tabs()], ["Tasks", "Settings"]
        )
        settings_controls = self.controls(self.app.settings_tab)
        self.assertTrue(moved <= settings_controls.keys())
        self.assertIs(settings_controls["+ Add task"], self.app.fixed_add_button)
        self.assertTrue(settings_controls["Run at Windows sign-in"].instate(["disabled"]))
        self.app.notebook.select(self.app.tasks_tab)
        self.app.settings()
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)], [])

    def test_settings_buttons_keep_existing_actions(self) -> None:
        with (
            patch.object(self.app, "show_report") as report,
            patch("app.simpledialog.askstring", return_value=date.today().strftime("%Y-%m")),
            patch("app.simpledialog.askinteger", return_value=None) as margin,
        ):
            self.app.settings()
            controls = self.controls(self.app.settings_tab)
            controls["Daily summary"].invoke()
            controls["Monthly summary"].invoke()
            controls["Deadline margin"].invoke()
            self.assertEqual([call.args[0] for call in report.call_args_list], ["Daily summary", "Monthly summary"])
            margin.assert_called_once()

    def test_about_opens_repo_document_in_readonly_tab_without_a_window(self) -> None:
        self.assertEqual(ABOUT_PATH, Path(__file__).resolve().with_name("ABOUT.md"))
        content = ABOUT_PATH.read_text(encoding="utf-8")
        self.app.settings()
        button = self.controls(self.app.settings_tab)["About the app"]
        with patch("app.tk.Toplevel", side_effect=AssertionError("About must stay in the main window")):
            button.invoke()
        self.assertEqual(self.app.notebook.select(), str(self.app.about_tab))
        self.assertEqual(
            [self.app.notebook.tab(tab, "text") for tab in self.app.notebook.tabs()],
            ["Tasks", "Settings", "About the app"],
        )
        text = self.app.about_text
        assert text is not None
        self.assertEqual(text.get("1.0", "end-1c"), content)
        self.assertEqual(str(text["state"]), "disabled")
        self.assertTrue(str(text["yscrollcommand"]))
        self.root.geometry(f"{style.MIN_WINDOW_SIZE[0]}x{style.MIN_WINDOW_SIZE[1]}")
        self.root.deiconify()
        self.root.wait_visibility()
        self.root.update()
        self.assertTrue(text.winfo_ismapped())
        self.assertGreater(text.winfo_height(), 40)
        self.assertLess(text.yview()[1], 1)
        text.yview_moveto(1)
        self.assertGreater(text.yview()[0], 0)
        text.insert("1.0", "Must not edit")
        self.assertEqual(text.get("1.0", "end-1c"), content)
        assert self.app.about_tab is not None
        self.controls(self.app.about_tab)["Back to Settings"].invoke()
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))
        self.assertEqual([child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)], [])

    def test_about_reuses_tab_and_reloads_the_single_document_source(self) -> None:
        self.app.show_about()
        original_text = self.app.about_text
        original_tab = self.app.about_tab
        self.app.settings()
        with patch("app.ABOUT_PATH") as document:
            document.read_text.return_value = "# About the app\nUpdated documentation.\n"
            self.controls(self.app.settings_tab)["About the app"].invoke()
            document.read_text.assert_called_once_with(encoding="utf-8")
        self.assertIs(self.app.about_text, original_text)
        self.assertIs(self.app.about_tab, original_tab)
        self.assertEqual(len(self.app.notebook.tabs()), 3)
        assert self.app.about_text is not None
        self.assertEqual(
            self.app.about_text.get("1.0", "end-1c"),
            "# About the app\nUpdated documentation.\n",
        )
        self.assertEqual(str(self.app.about_text["state"]), "disabled")

    def test_about_read_errors_are_reported_without_an_empty_tab(self) -> None:
        for error in (
            FileNotFoundError("Missing ABOUT.md"),
            PermissionError("Cannot read ABOUT.md"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                patch("app.ABOUT_PATH") as document,
                patch("app.messagebox.showerror") as show_error,
                self.assertLogs(level="ERROR"),
            ):
                document.read_text.side_effect = error
                self.app.show_about()
                show_error.assert_called_once_with(
                    "About the app could not open", str(error), parent=self.root,
                )
            self.assertIsNone(self.app.about_tab)
            self.assertEqual(len(self.app.notebook.tabs()), 2)
        self.app.show_about()
        text = self.app.about_text
        assert text is not None
        previous = text.get("1.0", "end-1c")
        self.app.settings()
        with (
            patch("app.ABOUT_PATH") as document,
            patch("app.messagebox.showerror"),
            self.assertLogs(level="ERROR"),
        ):
            document.read_text.side_effect = FileNotFoundError("Missing ABOUT.md")
            self.app.show_about()
        self.assertEqual(text.get("1.0", "end-1c"), previous)
        self.assertEqual(self.app.notebook.select(), str(self.app.settings_tab))

    def test_settings_margin_and_startup_changes(self) -> None:
        self.app.settings()
        controls = self.controls(self.app.settings_tab)
        with patch("app.simpledialog.askinteger", return_value=25):
            controls["Deadline margin"].invoke()
        self.assertEqual(self.store.setting("margin"), "25")
        self.assertIn("Margin: 25 min", str(self.app.footer["text"]))
        controls["Run at Windows sign-in"].state(["!disabled"])
        with patch("startup.set_enabled") as enable:
            controls["Run at Windows sign-in"].invoke()
            enable.assert_called_once_with(True)
        self.assertTrue(self.app.startup_var.get())
        self.assertEqual(self.store.setting("startup_initialized"), "yes")
        self.app.notebook.select(self.app.tasks_tab)
        self.app.settings()
        self.assertTrue(self.app.startup_var.get())

    def test_daily_progress_and_empty_state(self) -> None:
        self.assertEqual(self.app.dashboard.total, 0)
        self.assertTrue(self.app.empty_label.place_info())
        self.store.add_task("Small win", "08:00", "09:00", date.today())
        self.app.refresh()
        task = self.store.tasks(date.today())[0]
        self.app.tree.selection_set(str(task.id))
        self.app.done()
        self.assertEqual(self.app.dashboard.completed, 1)
        self.assertEqual(self.app.dashboard.total, 1)
        self.assertEqual(self.app.dashboard.focus_text, "All tasks done.")
        self.assertEqual(self.app.empty_label.place_info(), {})
        self.app.refresh()
        self.assertEqual(self.app.dashboard.completed, 1)
        self.app.change_day(1)
        self.assertEqual(self.app.dashboard.completed, 0)
        self.assertEqual(self.app.dashboard.total, 0)

    def test_simple_ui_has_no_branding_rewards_or_effects(self) -> None:
        self.assertEqual(self.root.title(), "Everyday is a new chance.")
        self.assertEqual(tuple(self.app.tree["columns"]), ("slot", "task", "status"))
        self.assertNotIn("Completion sparkle", self.controls(self.app.settings_tab))
        self.assertFalse(hasattr(self.app.dashboard, "celebrate"))
        text = []

        def collect(parent: tk.Misc) -> None:
            for child in parent.winfo_children():
                if isinstance(child, (tk.Label, ttk.Label)):
                    text.append(str(child["text"]))
                collect(child)

        collect(self.root)
        text.extend(
            str(self.app.dashboard.itemcget(item, "text"))
            for item in self.app.dashboard.find_all()
            if self.app.dashboard.type(item) == "text"
        )
        visible_text = " ".join(text).lower()
        for removed in ("daily todos", "focus & flow", "xp", "level", "achievements", "sparkle"):
            self.assertNotIn(removed, visible_text)

    def test_focus_title_fits_the_card_at_narrow_sizes(self) -> None:
        self.app.dashboard.update_metrics(
            0, 1, "Next task", "A very long task title " * 20, "08:00 - 09:00"
        )
        available = (max(600, self.app.dashboard.winfo_width()) - 12) * 0.62 - 40
        self.assertLessEqual(self.app.dashboard.focus_font.measure(self.app.dashboard.focus_display), available)
        self.assertTrue(self.app.dashboard.focus_display.endswith("..."))

    def test_current_and_next_task_follow_start_and_done(self) -> None:
        today = date.today()
        at = datetime.combine(today, datetime.min.time()).replace(hour=8)
        self.store.add_task("First", "08:00", "09:00", today)
        self.store.add_task("Second", "09:00", "10:00", today)
        first, second = self.store.tasks(today)
        self.app.refresh(at)
        self.assertEqual(self.app.dashboard.focus_heading, "Next task")
        self.assertEqual(self.app.dashboard.focus_text, "First")
        self.store.start_task(first.id, at)
        self.app.refresh(at)
        self.assertEqual(self.app.dashboard.focus_heading, "Current task")
        self.assertEqual(self.app.dashboard.focus_detail, "08:00 - 09:00")
        self.store.done_task(first.id, at.replace(minute=30))
        self.app.refresh(at.replace(minute=30))
        self.assertEqual(self.app.dashboard.focus_heading, "Next task")
        self.assertEqual(self.app.dashboard.focus_text, "Second")
        self.assertEqual(self.app.dashboard.completed, 1)
        self.app.refresh(at.replace(hour=11))
        self.assertEqual(self.app.dashboard.focus_text, "No upcoming tasks.")

    def test_color_schemes_are_complete_and_shared(self) -> None:
        required = set(color_scheme.SCHEMES["dark"])
        self.assertEqual(set(color_scheme.SCHEMES["light"]), required)
        self.assertIs(style.COLORS, color_scheme.COLORS)
        for scheme in color_scheme.SCHEMES.values():
            for name, value in scheme.items():
                with self.subTest(name=name, value=value):
                    self.assertRegex(value, r"^#[0-9a-fA-F]{6}$")
                    self.root.winfo_rgb(value)
        for status in ("pending", "done", "missed"):
            self.assertEqual(style.STATUS_COLORS[status], (
                style.COLORS[f"{status}_background"], style.COLORS[f"{status}_text"],
            ))


class StartupTests(unittest.TestCase):
    def test_pythonw_command_handles_spaces(self) -> None:
        with (
            patch("startup.sys.executable", r"C:\Program Files\Python\python.exe"),
            patch("startup.Path.is_file", return_value=True),
        ):
            command = startup.command()
        self.assertTrue(command.startswith('"C:\\Program Files\\Python\\pythonw.exe"'))
        self.assertIn("app.py", command)

    def test_missing_launcher_is_an_error(self) -> None:
        with patch("startup.Path.is_file", return_value=False), self.assertRaises(FileNotFoundError):
            startup.command()


if __name__ == "__main__":
    unittest.main()
