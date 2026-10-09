# Daily Todos

A simple local Windows checklist using Python, Tkinter, and SQLite. No pip packages needed.
The interface focuses on tasks and timing, with daily progress and the current/next
task. Today, Backlog, 5-Year Goals, and Settings stay in one window.

## About the app

Read [ABOUT.md](ABOUT.md) for the full product guide, architecture, database
model, development history, design decisions, validation, and limitations.
**Settings > About the app** opens that same document in a read-only tab inside
the main window. **Back to Settings** returns to the controls. Keep the document
beside `app.py`; opening About again reloads it without adding another tab.

## Run

Install Python 3.10 or later with Tcl/Tk support, then run:

```powershell
python .\app.py
```

Or double-click `launch.pyw` to open it without a console window.

On its first launch, the app registers itself for **Windows sign-in**, without administrator
rights. Open **Settings** and uncheck **Run at Windows sign-in** to disable it. Keep this folder and Python
in place; if you move either, launch the app again and re-enable the checkbox.
The startup launch uses `pythonw.exe`, so there is no console window.
Closing the window exits the app; it is not a background service or tray app.

## Use

- **5-Year Goals**: save a goal title and target date (`YYYY-MM-DD`) between
  today and five years from today. Goals persist locally, sorted with open goals
  first and then by target date. Press **+ Add goal** or Enter to save. Select
  a goal to **Mark complete**, **Reopen**, or **Remove** (with confirmation). Overdue goals are labeled; completed goals
  stay visible, with a completed/total count. The default target is five years
  ahead (February 29 becomes February 28). These goals are separate from daily
  task progress and reports; there is no automatic link to backlog tasks.

- **Backlog**: save a title, duration in whole minutes (1-540), and deadline
  date (`YYYY-MM-DD`). Press **+ Add to backlog** or Enter to save.
  Items are sorted by deadline, with overdue dates labeled. **Remove** deletes
  a selected unscheduled item after confirmation.
  Select an item, choose today or a date up to seven days ahead, and use
  **Find free slot** to suggest a start time for its full duration. You can edit
  Start before pressing **Move to day**. The move checks normal schedule rules,
  removes the item from Backlog, and opens that day's Today view. If scheduling
  fails, the item stays in Backlog. Deadlines are due dates; scheduling after
  them is allowed. Removing an eligible unstarted scheduled task returns it to
  Backlog with its original duration and deadline. Backlog items persist locally
  and do not count toward daily progress until scheduled.

- **Today** shows the selected day's schedule; its date arrows also let you
  browse history and plan ahead. **Backlog** holds unscheduled work,
  **5-Year Goals** tracks long-term goals, and **Settings** contains summaries,
  fixed weekday tasks, the deadline margin, sign-in startup, and About the app.
- **Fixed weekday tasks**: enter Start, End, and Task in the inline row beneath
  the fixed-task table in Settings, then click **+ Add task** (or press Enter).
  No additional window opens, and validation errors appear below the row.
  Start/End suggest the earliest free **20-minute** slot from 08:00, considering
  active routines and all saved tasks on today/future weekdays. A shorter gap is
  skipped. After adding a task, the next available slot is suggested.
  New tasks apply today (if it is a weekday) and on subsequent weekdays. Stop repeating
  removes future occurrences but preserves today's list and history.
- Use the date arrows to plan up to **seven days ahead**, including weekends.
  Enter Start, End, and Task in the row below the Today table and press **+ Add task**
  (or Enter) to save for the displayed date. No editor window opens; errors
  appear inline and keep your input. Today suggests the first free 20-minute
  slot **at or after now**, rounded up to the next minute when necessary;
  future days start searching at 08:00. Suggestions include that date's saved
  tasks and applicable routines. You can edit either time, including shorter
  slots; 20 minutes is a suggestion, not a minimum task length. If no suggested
  slot fits before 17:00, the row shows a message instead of invalid times.
  Custom times and per-date drafts survive refreshes and navigation during this
  session; only saved tasks persist after closing. History entry is disabled.
  Future date-specific tasks can also be removed; Start
  and Done are only available on the task's actual day. Fixed weekday tasks
  continue to be generated when their day arrives.
- Each slot must be within **08:00-17:00**. Both lists are sorted by start time.
  Overlapping slots are rejected with the conflicting task's name and time.
  Adjacent slots (for example 08:00-09:00 and 09:00-10:00) are allowed; the
  deadline margin does not reserve extra schedule time. Daily tasks are checked
  against that date's tasks and applicable fixed weekday tasks, even on future
  dates. New fixed tasks are also checked against already-planned weekday tasks.
  Existing overlapping tasks from older versions are kept, not deleted.
- Select a task and press **Start**, then **Done**. Start records a timestamp;
  Done can also be used without Start. Buttons stay available for overdue tasks.
- The boxed clock is green until an unfinished task reaches its slot's end
  (the beginning of its margin), then stays red until Done or you Start another
  task. Starting another task marks previously started unfinished tasks and
  unfinished tasks whose slots have ended as missed (red), keeping that history.
  These missed tasks no longer keep the clock red, but can still be marked Done.
  The clock always reflects today, even when browsing history.
- Pending tasks are gray (darker in the default dark theme). After the slot's end plus the margin they turn
  red. Completed tasks turn green, including late completions, which are marked
  **Done late** in the list and reports.
- **Deadline margin** defaults to 10 minutes. Changes affect today's unfinished
  tasks and future tasks, not historical or already-completed tasks.
- Browse past days using the arrows; history is read-only.
- Daily and monthly summaries show completion totals, on-time successes, late
  finishes, and missed tasks. The monthly report accepts `YYYY-MM`.
- An end-of-day summary opens once after **17:00 + margin**, or on a later
  launch that evening. Days when the app was closed are reconstructed on the next
  launch, so missed fixed tasks still appear in history and monthly reports.
  Colors only update while the app is open. Summaries are factual, not AI-generated.

Data is kept in `%LOCALAPPDATA%\DailyTodos\todos.sqlite3`; errors are logged in
the same folder. Back up the database with the app closed. No network connection
is used and no example tasks are added automatically.

## Tests

Run from the project root. Tests live in `tests/`:

```powershell
python -m unittest discover -v
```

To run only storage and scheduling tests:

```powershell
python -m unittest -v tests.test_store
```

UI tests need a desktop session with Tcl/Tk available. Tests use temporary databases
and mock startup registration; they do not change your real checklist or sign-in settings.

## Appearance

`ui/color_scheme.py` is the single place to change colors:

1. Set `ACTIVE_SCHEME = "dark"` (default) or `ACTIVE_SCHEME = "light"`.
2. To customize a scheme, edit its hex colors in `SCHEMES`. For example,
   `background` changes the window, `surface` changes the cards, and `accent`
   changes Start/Done and primary actions. Keep hover/pressed colors coordinated.
3. `pending_*`, `done_*`, and `missed_*` control task rows, goal rows, and legend boxes.
   `clock_green`, `clock_red`, and `clock_text` control the boxed clock.
   `progress` controls the daily completion ring.
4. Save the file and restart the app. Colors are not a separate Settings control.

`ui/style.py` imports the selected scheme and contains fonts, window sizing, and
rounded button styles. `ui/visuals.py` draws the two static information cards.
`app.py` assembles the UI; scheduling and history remain in `store.py`.

- The main window heading is **Everyday is a new chance.** There is no app branding,
  XP, level, achievements, sparkle setting, decorative shine, or animation.
- **Daily progress** shows completed/total tasks and a percentage for the
  selected date, not lifetime statistics. An empty day shows 0 / 0 and 0%.
- **Current task** shows an unfinished started task first. Otherwise **Next task**
  shows the first pending task in time order, with its time slot. The card updates
  after Start/Done and date changes. If all tasks are done or none remain pending,
  it says so. Long titles are shortened in the card, but remain intact in the table.
- The task table contains only Time, Task, and Status. Gray pending, green done,
  and red missed rows have matching labeled legend boxes, so color is not the
  only indicator. The dark scheme uses darker shades of these colors.
- Rounded buttons retain hover, pressed, disabled, and keyboard-focus states.
  Lists have vertical scrollbars; an empty day has a short Add task prompt.
- Settings retains summaries, margin, startup, About, and the inline fixed-task entry
  row. Daily-task entry also uses an inline row. Summaries use their existing dialogs. Windows message
  boxes retain system styling.

Removing the former rewards/effects does not delete tasks or completion history
and needs no database migration. An old saved effects preference is simply unused.

## Verification

Standard-library tests cover selected-date progress, current/next-task timing,
absence of rewards and effects, both color schemes, inline overlap feedback,
task controls, rounded button states, minimum-size layout, scheduling, and history.
Free-slot tests cover current-time boundaries, short gaps, future weekday reservations,
template lifetimes, full schedules, inline keyboard entry, and date-specific drafts.
Backlog tests cover validation, persistence, atomic moves, conflict handling,
returning removed daily tasks, and minimum-size layout. Goal tests cover target
dates, persistence, completion, reopening, removal, and minimum-size layout.
The full suite passed 68 tests on 9 October 2026. Tests use temporary databases
and do not change your real tasks or Windows startup settings.
