"""Static daily progress and current/next-task cards."""

import tkinter as tk
from tkinter import font as tkfont

from . import style


def rounded_box(canvas: tk.Canvas, x: float, y: float, width: float, height: float, fill: str) -> None:
    radius = 12
    canvas.create_polygon(
        x + radius, y, x + width - radius, y, x + width, y,
        x + width, y + radius, x + width, y + height - radius,
        x + width, y + height, x + width - radius, y + height,
        x + radius, y + height, x, y + height, x, y + height - radius,
        x, y + radius, x, y, smooth=True, splinesteps=24,
        fill=fill, outline=style.COLORS["border"], width=1,
    )


class Dashboard(tk.Canvas):
    def __init__(self, parent: tk.Misc):
        super().__init__(
            parent, height=style.DASHBOARD_HEIGHT, background=style.COLORS["background"],
            highlightthickness=0,
        )
        self.completed = 0
        self.total = 0
        self.focus_heading = "Next task"
        self.focus_text = "No tasks scheduled."
        self.focus_detail = ""
        self.focus_font = tkfont.Font(root=self, font=style.HEADING_FONT)
        self.focus_display = self.focus_text
        self._signature: object = None
        self.bind("<Configure>", lambda _event: self.draw())

    def update_metrics(
        self, completed: int, total: int,
        focus_heading: str, focus_text: str, focus_detail: str,
    ) -> None:
        signature = (completed, total, focus_heading, focus_text, focus_detail)
        if signature == self._signature:
            return
        self.completed, self.total = completed, total
        self.focus_heading, self.focus_text, self.focus_detail = focus_heading, focus_text, focus_detail
        self._signature = signature
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        width = max(600, self.winfo_width())
        gap = 12
        progress_width = (width - gap) * 0.38
        next_width = width - gap - progress_width
        height = style.DASHBOARD_HEIGHT - 6
        palette = style.COLORS
        rounded_box(self, 1, 1, progress_width - 2, height, palette["surface"])
        rounded_box(self, progress_width + gap, 1, next_width - 1, height, palette["surface"])
        self.create_text(20, 23, text="Daily progress", anchor="w", font=style.HEADING_FONT, fill=palette["muted"])
        self.create_text(
            20, 62, text=f"{self.completed} / {self.total} done", anchor="w",
            font=style.METRIC_FONT, fill=palette["text"],
        )
        center_x, center_y = progress_width - 52, 57
        self.create_oval(center_x - 29, center_y - 29, center_x + 29, center_y + 29,
                         outline=palette["raised"], width=5)
        percent = round(self.completed / self.total * 100) if self.total else 0
        if percent:
            self.create_arc(
                center_x - 29, center_y - 29, center_x + 29, center_y + 29,
                start=90, extent=-360 * self.completed / self.total, style="arc",
                outline=palette["progress"], width=5,
            )
        self.create_text(center_x, center_y, text=f"{percent}%", font=style.SMALL_FONT, fill=palette["text"])
        x = progress_width + gap + 20
        self.create_text(x, 23, text=self.focus_heading, anchor="w", font=style.HEADING_FONT, fill=palette["muted"])
        self.focus_display = self.focus_text
        if self.focus_font.measure(self.focus_display) > next_width - 40:
            shortened = self.focus_text
            while shortened and self.focus_font.measure(shortened + "...") > next_width - 40:
                shortened = shortened[:-1]
            self.focus_display = shortened.rstrip() + "..."
        self.create_text(x, 53, text=self.focus_display, anchor="w", font=self.focus_font, fill=palette["text"])
        self.create_text(x, 82, text=self.focus_detail, anchor="w", font=style.BODY_FONT, fill=palette["muted"])
