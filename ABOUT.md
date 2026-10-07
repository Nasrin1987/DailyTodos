# About the app

Everyday is a new chance.

Project: Daily Todos
Documentation updated: 7 October 2026

## 1. Purpose and design

Daily Todos is a small, offline Windows checklist for planning and working
through the day. It combines fixed weekday routines with tasks for individual
dates, time slots, Start and Done controls, clear status colors, and factual
daily/monthly summaries.

The project started with a request for a very simple Windows application,
written in Python or C++, that could run at sign-in and support an 08:00-17:00
day. Python was chosen, using only the standard library.

The design was subsequently refined for a user who wanted an ADHD-friendly,
low-distraction interface. This is a design preference, not a medical claim.
The current interface prioritizes:

- Tasks and their timing, rather than branding or reward counters.
- One heading: "Everyday is a new chance."
- A daily progress indicator and a current/next-task card.
- Inline task entry, with errors beside the inputs.
- Secondary controls in Settings, not on the main task screen.
- Gray, green, and red status cues accompanied by readable labels.
- Static, rounded controls without shine, sparkle, sound, or animation.

There are no accounts, online services, external dependencies, or AI-generated
reports. The app does not add demonstration tasks to your real database.

## 2. Installation and launch

Requirements:

- Windows for sign-in startup registration.
- Python 3.10 or newer, with Tcl/Tk support.
- A graphical desktop session for the interface and its UI tests.

Development and automated validation have been performed on Windows with
Python 3.14.0. This does not mean every supported Python version has been tested.

From the project folder, run:

    python .\app.py

Alternatively, double-click launch.pyw, provided Windows associates Python
launcher files with the installed interpreter. This opens the app without a
console window. No pip installation is required.

Keep the source files together, including ABOUT.md: the About view reads this
document from the installation folder, not from the current working directory.
Use Settings > About the app to read it inside the app. The document opens in
a read-only, scrollable tab; Back to Settings returns to the controls. The viewer
displays the document as text rather than requiring a Markdown/browser package.
Opening About again reuses the same tab and reloads the document.

The normal interface initially has Tasks and Settings tabs. About is added
only when requested. Closing the main window exits the program completely;
there is no tray process, background service, or always-running scheduler.

## 3. The Tasks tab

The main screen contains:

- Date arrows, a Today button, and the selected date.
- A boxed clock displaying today's local time.
- Daily progress: completed tasks / total tasks and a percentage ring.
- Current task or Next task, with its time slot.
- A table with Time, Task, and Status columns.
- An inline Start, End, Task, and + Add task row.
- Start, Done, and Remove buttons for the selected task.
- Pending, Done, and Missed legend boxes.
- The 08:00-17:00 schedule range and current deadline margin.

Progress and the focus card refer to the displayed date. The clock always
refers to today, even when you are looking at another date.

An unfinished started task that has not explicitly been skipped takes priority
in the Current task card. Otherwise, Next task shows the first pending task in
time order. This can include a task whose slot has ended but is still within its
deadline margin. A started task can remain the current task when overdue.

An empty day shows 0 / 0 completed and 0%. Other messages distinguish an empty
schedule, an entirely completed schedule, and unfinished work with no pending
task. Long titles are shortened in the card but remain intact in the task table
and database.

### Adding date-specific tasks

1. Choose today or a date up to seven days ahead.
2. Enter the task title and review Start/End in the row below the table.
3. Press + Add task, or press Enter in any of the row's inputs.

The selected date is the date that receives the task. Task entry never opens
a separate editor window. On success, the title is cleared, the table is
refreshed in time order, and another free slot is suggested. Invalid input or
an overlap produces an inline error and preserves the inputs for correction.

Today starts searching for a free 20-minute slot at or after the current time,
never before 08:00. Seconds or microseconds are rounded upward to the next
whole minute. For example, 10:05:12 starts searching from 10:06.

Future dates start searching at 08:00. Suggestions consider the date's saved
tasks and any fixed routines applicable to that weekday/date. They do not
create future routine snapshots just to calculate availability.

Twenty minutes is the suggested duration, not a required minimum. You may
edit both times, including entering a shorter slot or an earlier time manually.
All saved slots must still be valid and non-overlapping. If no 20-minute slot
fits before 17:00, the inputs are left blank and an explanatory message appears.
You can enter another valid slot or choose a different date.

Automatic suggestions are refreshed while the app runs if the times still
match the previous suggestion. Custom times are not overwritten. Date-specific
drafts survive date navigation in the current session. Unsaved daily and fixed
drafts are not written to the database and disappear when the app closes.

### Dates, Start, Done, and removal

- Planning is available from today through today + seven days, including weekends.
- Past days can be browsed but are read-only in the UI.
- Start and Done are available only for tasks belonging to today.
- Start records the actual start timestamp; it is not a countdown or stopwatch.
- Done records completion and may be used without pressing Start first.
- An overdue task can still be completed today and becomes green.
- A task that was explicitly skipped cannot be restarted, but can still be Done.
- Remove requires confirmation and is available only for an unstarted,
  unfinished, non-skipped, date-specific task on today or a planning date.
- Fixed occurrences, started tasks, and completed history cannot be removed
  through the date-specific Remove button.

When midnight arrives while viewing today, the app advances to the new day.
Browsing a different date does not force that view back to today.

## 4. Fixed weekday tasks

Settings contains a table of routines that repeat Monday through Friday.
Use the inline Start, End, Task, and + Add task row, or press Enter in an input.
No editor window opens. Validation errors remain beneath the row.

The default time is the earliest free slot of at least 20 minutes, searching
from 08:00. This is independent of today's current time because the task is a
recurring routine. Shorter gaps are skipped.

Availability considers:

- Active fixed routines.
- Saved tasks on today and future weekdays, including already-planned daily tasks.
- Preserved weekday snapshots that still reserve their time slots.

Past tasks and weekend-only daily tasks do not block a new weekday routine.
There is no seven-day cutoff for these conflict checks: an existing saved task
on a later weekday still matters. After a routine is saved, the next available
slot is suggested. Times remain editable; 20 minutes is not a minimum enforced
on manually entered tasks.

A new routine applies today when today is a weekday, and on subsequent weekdays.
Future routine occurrences are generated as their dates arrive; they are not
all listed in advance on future date views.

To stop a routine, select it and press Stop repeating, then confirm. The active
template is stopped, while today's existing occurrence and previous history
are preserved. Therefore its preserved time slot may still block a replacement
today, but it no longer reserves future occurrences.

## 5. Scheduling and overlap rules

Every slot must satisfy:

- A nonempty title after trimming whitespace.
- Parseable HH:MM start and end times.
- 08:00 <= start < end <= 17:00.

Lists are sorted by start time, then end time, then identifier, not insertion order.

Intervals are half-open: [start, end). An overlap exists when an existing start
is before the new end AND the existing end is after the new start. Thus
08:00-09:00 and 09:00-10:00 can touch without conflicting.

The deadline margin does not reserve additional schedule time. Completed
tasks retain their scheduled intervals; finishing early does not automatically
make their original slot available for another task.

Daily additions are checked against that date's tasks and applicable fixed
templates, even when a future weekday has not been materialized. Fixed additions
are checked against active templates and all saved today/future weekday tasks.

Overlaps are rejected, rather than merely warned about and allowed. Errors
identify the conflicting task and time, and include its date when relevant.
Existing overlapping data from earlier versions is preserved, not deleted.

Suggestions and save validation use the same reservation rules. A suggestion
does not reserve a slot: saving checks availability again. Check-and-insert uses
a SQLite BEGIN IMMEDIATE transaction so another app instance cannot insert a
conflicting task between validation and the write.

## 6. Status colors, the clock, and the margin

The default deadline margin is 10 minutes; Settings accepts 0-120 minutes.
A task's deadline is its scheduled end plus its saved margin.

Task row status:

- Gray / pending: unfinished and not explicitly skipped, through its deadline.
  The text may say Not started or Started followed by a timestamp.
- Red / missed: unfinished and explicitly skipped, or the current time is
  strictly after its deadline.
- Green / done: completed, even if it was late. Late completion says Done late.

Completion exactly at the deadline is on time. The dark color scheme uses
dark gray, deep green, and rose-red shades; the light scheme uses lighter shades.
The legend boxes label the same states, so meaning does not depend on color alone.

The boxed clock has a different, earlier warning threshold:

- It is green while today's unfinished, non-skipped tasks have not reached
  their scheduled ends.
- It becomes red at a task's scheduled end, when that task enters its margin.
- It stays red while any such task still needs attention, including beyond
  the margin.
- Done removes that task's warning; the clock can stay red if another task
  still needs attention.

Starting another task explicitly marks other unfinished tasks as missed when
they were previously started or their scheduled end has passed. Their missed_at
timestamps are saved. These acknowledged/skipped tasks no longer keep the clock
red, but remain red in the table until completed.

Example: with a 09:00 end and 10-minute margin, the clock turns red at 09:00.
The task row remains pending through 09:10 and becomes missed after 09:10.
Completing at 09:10 is on time; completing later is Done late.

Changing the margin updates unfinished tasks dated today or later. It does not
alter completed tasks' saved margins or existing historical snapshots.

## 7. Summaries and reflection

Settings > Daily summary reports on the selected date.
Settings > Monthly summary accepts a month in YYYY-MM format.

Reports include:

- Completed / total tasks and completion percentage.
- On-time completions, including the saved margin.
- Late completions.
- Missed tasks and remaining pending tasks.
- What went well: tasks completed on time.
- Finished, but later than planned: late completions.
- Needs attention: missed tasks.

These are factual summaries of local records, not generated coaching or AI
interpretation. Pending tasks contribute to totals but are not a separate
per-task list in the report. The reports open in read-only, scrollable windows.

An end-of-day report normally opens once after 17:00 + the current margin,
provided today has tasks. Launching later that same evening can trigger it.
A saved date marker prevents repeated automatic reports for that day. There
is no automatic monthly popup and no retrospective popup for every missed day.

When the app has been closed, the next launch reconstructs missing weekday
occurrences from the routines' lifetimes. Those records become available in
history and monthly reports, including missed tasks. Reconstruction starts
from the recorded first/generated day, not indefinitely into the past.

The interface refreshes approximately once per second while open. Nothing
runs when the application is closed.

## 8. Storage, privacy, backups, and startup

Normal Windows data location:

    %LOCALAPPDATA%\DailyTodos\todos.sqlite3

The application writes errors.log in the same folder. If LOCALAPPDATA is
unavailable, the application uses a DailyTodos folder under the user's home.
Moving the source folder does not normally move the database.

Saved task titles, time slots, routine definitions, timestamps, and settings
stay in a local SQLite file. There is no synchronization, telemetry, network
access, authentication, or application-level database encryption.

To back up or restore:

1. Close all running instances of the app.
2. Copy todos.sqlite3 to a safe location.
3. To restore, keep a copy of the current database, replace it with the backup,
   and launch the app again.

A restored backup restores the records and settings it contained; later changes
are not merged automatically. Back up source customizations separately, including
color_scheme.py. Deleting the installation folder alone does not delete user data.

Windows startup uses the current user's registry Run key:

    HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run

The registry value is named DailyTodos and contains a quoted command pointing
to the interpreter and app.py. python.exe is replaced with its pythonw.exe
sibling when appropriate. No administrator rights are needed.

On the first Windows launch, the app attempts to register startup automatically.
Use Settings > Run at Windows sign-in to enable or disable it. If Python or the
source folder moves, open the app from its new location and re-enable startup.
Startup registration is unavailable on other platforms; the checkbox is disabled.

Before removing the app, disable sign-in startup to avoid leaving a command
pointing to missing files. Source deletion and database deletion are separate
decisions; there is no uninstaller.

## 9. Repository architecture

The project uses only Python's standard library:

- Tkinter/ttk for widgets and the event loop.
- Canvas for the static progress and current/next-task cards.
- SQLite for persistence.
- datetime for local dates, times, and deadlines.
- winreg for Windows startup registration.
- unittest, tempfile, and mocks for automated validation.

Files and responsibilities:

- app.py: main window, Tasks/Settings/About views, inline forms, button state,
  refresh loop, reports, startup initialization, and surfaced/logged errors.
- store.py: task records, validation, snapshots, reservations, free-slot search,
  overlap rejection, timestamp updates, margins, and report calculations.
- startup.py: Windows registry integration and quoted launcher construction.
- launch.pyw: small no-console entry point calling app.main().
- color_scheme.py: dark/light semantic palettes and shared status colors.
- style.py: fonts, sizing, rounded ttk image elements, and widget styles.
- visuals.py: two static Canvas cards, the progress ring, and title fitting.
- test_store.py: persistence and scheduling regression tests.
- test_app.py: UI, startup, appearance, inline-entry, and interaction tests.
- README.md: quick-start, everyday usage, customization, and test instructions.
- ABOUT.md: this comprehensive product, technical, and development-history guide.

The UI delegates saved-state changes to Store. There is no web server, external
frontend, dependency lockfile, or separate build pipeline.

### Database model

settings contains key/value strings. Used keys include first_day,
generated_through, margin, startup_initialized, and summary_shown. The startup
checkbox's actual enabled state is read from the registry. A legacy effects
preference may remain from an earlier design but is unused.

templates contains id, title, start, end, active_from, and active_until.
An active_until of NULL identifies an active routine.

tasks contains id, day, title, start, end, margin, template_id, started_at,
done_at, and missed_at. template_id is NULL for a date-specific task.
Times are integer minutes since midnight; dates and recorded timestamps are
ISO strings. A unique (day, template_id) constraint prevents duplicate routine
snapshots for a date, and an index supports date-based task queries.

Routine snapshots copy their title, slot, and margin into tasks, keeping
existing occurrences separate from future template behavior. Snapshot generation
uses template lifetimes and INSERT OR IGNORE, so refreshes do not duplicate them.
Future availability checks do not advance generated_through.

Older databases without missed_at are upgraded by adding that column. Removing
the former rewards/effects required no task-data migration because rewards had
been derived from saved completion history.

### Styling and customization

Edit color_scheme.py and restart:

- ACTIVE_SCHEME selects "dark" or "light".
- background, surface, raised, text, muted, and border define the base palette.
- accent, accent_hover, and accent_pressed define primary button states.
- focus, hover, pressed, disabled, and disabled_text define interaction states.
- pending_*, done_*, and missed_* define shared row/legend colors.
- clock_green, clock_red, and clock_text define the boxed clock.
- progress defines the completion-ring color.

All palette values are hex colors. Keep text/background combinations readable.
There is no runtime theme picker. Fonts, button radius, card height, and default/
minimum window dimensions live in style.py, not in the UI assembly code.

Rounded ttk buttons use generated PhotoImage backgrounds with transparent
corners and a stretchable center. Image references are retained so Tk does not
discard them. Buttons preserve hover, pressed, focus, and disabled states.
Grid layouts reserve space for inline rows and controls, avoiding the earlier
problem where an expanding table clipped the buttons.

## 10. What we implemented and refined

This is a chronological account of the work, not a list of additional features
currently planned.

1. Built the original Python/Tkinter/SQLite app: weekday routines, daily tasks,
   08:00-17:00 slots, Start/Done, status colors, margin, reports, and Windows startup.
2. Moved summaries, margin, startup, and fixed-task controls away from Tasks into
   Settings so the main view could focus on today's work.
3. Added the boxed clock's green/red margin warning and saved missed_at behavior
   when moving on to another task.
4. Replaced verbose color explanations with labeled Pending, Done, and Missed
   legend boxes.
5. Added a motivational heading and planning through seven days ahead, including
   removal of eligible future daily tasks and today-only Start/Done.
6. Separated styling from UI code, added truly rounded buttons, and corrected
   sizing/state details and clipped fixed-task controls.
7. Added automatic time ordering and strict overlap rejection for daily and
   recurring work, including future reservations and adjacent-slot boundaries.
8. Replaced the separate Settings window with a tab. Replaced repeated fixed-task
   editor dialogs with an inline row and visible + Add task button.
9. Explored a modern dark, gamified dashboard with XP, levels, achievements,
   shine, and optional completion sparkle.
10. Simplified that redesign following the request for a very simple,
    task/timing-focused interface. Removed branding, XP, levels, achievements,
    shine, and all completion effects. Kept daily progress and current/next task.
    The heading became exactly "Everyday is a new chance."
11. Centralized semantic colors in color_scheme.py, including editable dark and
    light schemes, while retaining separate layout/typography styling.
12. Replaced the daily-task popup with an inline row matching fixed-task entry.
    Added first-free-slot suggestions: today at/after now, future dates from
    08:00, and fixed routines in the earliest available 20-minute gap. Preserved
    custom times, per-date session drafts, inline errors, and schedule checks.
13. Added this comprehensive About document and a Settings entry that opens it
    inside the same main window.

The intermediate gamified version is historical context only. Its reward
features are not active in the current application. Existing tasks and completion
history were preserved through the redesigns.

## 11. Validation and maintenance

Run from the project folder:

    python -m unittest -v test_app test_store

Tests use temporary databases and mock startup integration. They do not modify
the user's real checklist or registry startup setting. UI tests need a desktop
session with Tk available. Tk callback errors are collected so asynchronous
widget failures cannot silently pass the UI suite.

Coverage includes:

- Input validation, sorting, overlapping slots, and adjacent boundaries.
- Daily/fixed reservations, future plans, weekends, and stopped routines.
- Deadline/status boundaries and the clock's distinct warning threshold.
- Start/Done, explicitly missed tasks, removal, and read-only history.
- Margin persistence, migrations, routine reconstruction, and summaries.
- Inline keyboard entry, errors, custom times, and date-specific drafts.
- Free-slot search at/after now, short gaps, and no available 20-minute slot.
- Progress/current-next behavior and removal of distracting rewards/effects.
- Shared color schemes, rounded button states, and minimum-size layout.
- Quoted startup commands and settings actions.
- About document loading, reuse, read-only presentation, and read-error feedback.

The inline-entry milestone passed 58 tests, and its light-theme UI run passed
34 tests. These are historical validation counts, not fixed targets for future
work; the current suite includes the additional About tests.

When changing behavior, update README.md and this document, run the relevant
existing tests, and verify that errors remain visible and saved history intact.
Keep user data out of the source folder and out of any example fixtures.

## 12. Limitations and troubleshooting

Current limitations:

- One local user's checklist; no shared accounts, sync, or collaboration.
- One fixed 08:00-17:00 range, not a configurable workday or overnight schedule.
- Routines repeat Monday-Friday as a group, not arbitrary selected weekdays.
- Future routine reservations are checked but are not all displayed as future
  task rows until those dates arrive.
- Start is a timestamp, not a duration tracker, countdown, or reminder alarm.
- No tray mode, sound notifications, continuous background process, or automatic
  monthly notification.
- No built-in task editing, undo, database export/import wizard, backup scheduler,
  installer, packaged executable, or single-instance enforcement.
- Dates/times use the computer's local clock without timezone conversion.
- Session drafts are not recovered after closing or a crash.
- System dialogs keep Windows styling; the About viewer is a text viewer.

If startup fails, run app.py from a PowerShell window to see interpreter errors,
and check errors.log for application errors. Confirm Python includes Tk and
that the data folder is writable. A database refresh error is surfaced and
stops the normal refresh loop; resolve it and restart rather than assuming the
display is still current.

If a button is disabled, select an eligible task and check the displayed date.
Start/Done are today-only; history is read-only. Already started, completed, or
explicitly skipped tasks have different allowed actions.

If a task cannot be added, check its title, HH:MM times, 08:00-17:00 boundaries,
and the inline conflict message. A fixed task can conflict with a saved future
weekday task even when today's list appears free.

If no default slot is available, a 20-minute gap does not fit in the applicable
schedule. Choose another date for a daily task, revise your schedule, or enter
a shorter valid slot manually. The app never silently moves or deletes other
tasks to make room.

If About cannot open, ensure ABOUT.md is beside app.py and readable as UTF-8.
The app reports/logs the read error instead of displaying a blank success view.

If sign-in startup stops working after moving files or Python, open the new
installation and re-enable Run at Windows sign-in. If the UI does not fit your
display, review scaling and the window/font sizing constants in style.py.
