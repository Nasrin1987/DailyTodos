"""Simple Tkinter styling. Colors are configured separately in ui/color_scheme.py."""

import math
import tkinter as tk
from tkinter import ttk
from .color_scheme import COLORS, STATUS_COLORS

BODY_FONT = ("Segoe UI", 11)
HEADING_FONT = ("Segoe UI", 11, "bold")
TITLE_FONT = ("Segoe UI", 16, "bold")
METRIC_FONT = ("Segoe UI", 22, "bold")
SMALL_FONT = ("Segoe UI", 9)
CLOCK_FONT = ("Segoe UI", 12, "bold")
WINDOW_SIZE = "1000x800"
MIN_WINDOW_SIZE = (940, 760)
BUTTON_RADIUS = 12
DASHBOARD_HEIGHT = 112
CLOCK_OPTIONS = {
    "font": CLOCK_FONT, "width": 8,
    "background": COLORS["clock_green"], "foreground": COLORS["clock_text"],
    "relief": "solid", "borderwidth": 1, "padx": 12, "pady": 8,
}
BADGE_OPTIONS = {
    "font": BODY_FONT, "width": 9, "padx": 8, "pady": 4,
    "relief": "solid", "borderwidth": 1,
}
REPORT_OPTIONS = {
    "font": BODY_FONT, "background": COLORS["surface"], "foreground": COLORS["text"],
    "padx": 18, "pady": 18, "borderwidth": 0,
    "selectbackground": COLORS["selection"],
}


def rounded_image(root: tk.Tk, fill: str, border: str, radius: int) -> tk.PhotoImage:
    size = radius * 2 + 6
    image = tk.PhotoImage(master=root, width=size, height=size)
    # Transparent corners and a stretchable center give real rounded ttk buttons.
    for inset, color in ((0, border), (1, fill)):
        curve = radius - inset
        for y in range(inset, size - inset):
            distance = max(inset + curve - (y + 0.5), (y + 0.5) - (size - inset - curve), 0)
            offset = curve - math.sqrt(max(0, curve * curve - distance * distance))
            left = math.ceil(inset + offset - 0.5)
            image.put(color, to=(left, y, size - left, y + 1))
    return image


class Theme:
    def __init__(self, root: tk.Tk):
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.images: dict[str, dict[str, tk.PhotoImage]] = {}
        scale = max(1.0, float(root.tk.call("tk", "scaling")) / (96 / 72))
        radius = round(BUTTON_RADIUS * scale)
        root.configure(background=COLORS["background"])
        root.option_add("*Toplevel.background", COLORS["background"])
        self.style.configure(
            ".", font=BODY_FONT, background=COLORS["background"],
            foreground=COLORS["text"],
        )
        self.style.configure("Title.TLabel", font=TITLE_FONT, foreground=COLORS["text"])
        self.style.configure("Heading.TLabel", font=HEADING_FONT)
        self.style.configure("Muted.TLabel", foreground=COLORS["muted"])
        self.style.configure("Error.TLabel", foreground=COLORS["error"])
        self.style.configure(
            "TNotebook", borderwidth=0, tabmargins=(0, 0, 0, 8),
            bordercolor=COLORS["background"], lightcolor=COLORS["background"],
            darkcolor=COLORS["background"],
        )
        self.style.configure("TNotebook.Tab", font=HEADING_FONT, padding=(18, 10))
        self.style.map(
            "TNotebook.Tab", background=[("selected", COLORS["surface"]), ("active", COLORS["hover"])],
            foreground=[("selected", COLORS["accent"])],
        )
        self.style.configure("TLabelframe", bordercolor=COLORS["border"], relief="solid")
        self.style.configure("TLabelframe.Label", font=HEADING_FONT, foreground=COLORS["muted"])
        self.style.configure("TCheckbutton", padding=(0, 6))
        self.style.map("TCheckbutton", background=[("active", COLORS["background"])])
        self.style.configure(
            "Vertical.TScrollbar", background=COLORS["raised"],
            troughcolor=COLORS["background"], bordercolor=COLORS["background"],
            arrowcolor=COLORS["muted"], relief="flat",
        )
        self.style.map("Vertical.TScrollbar", background=[("active", COLORS["hover"])])
        self.style.configure(
            "TSpinbox", fieldbackground=COLORS["surface"], foreground=COLORS["text"],
            arrowcolor=COLORS["muted"], background=COLORS["raised"], padding=6,
        )
        self.style.configure(
            "TEntry", fieldbackground=COLORS["surface"], padding=7,
            bordercolor=COLORS["border"], lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
        )
        self.style.map("TEntry", bordercolor=[("focus", COLORS["accent"])])
        self.style.configure(
            "Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
            rowheight=round(38 * scale), bordercolor=COLORS["border"], borderwidth=0,
            lightcolor=COLORS["border"], darkcolor=COLORS["border"],
        )
        self.style.configure(
            "Treeview.Heading", font=HEADING_FONT, background=COLORS["hover"],
            foreground=COLORS["muted"], padding=(10, 12), relief="flat",
        )
        self.style.map("Treeview.Heading", background=[("active", COLORS["pressed"])])
        self.style.map(
            "Treeview", background=[("selected", COLORS["selection"])],
            foreground=[("selected", COLORS["text"])],
        )
        self._buttons(root, "TButton", radius, accent=False)
        self._buttons(root, "Accent.TButton", radius, accent=True)
        self.tab_images = {
            "normal": rounded_image(root, COLORS["background"], COLORS["background"], radius),
            "selected": rounded_image(root, COLORS["raised"], COLORS["accent"], radius),
            "active": rounded_image(root, COLORS["surface"], COLORS["border"], radius),
            "focus": rounded_image(root, COLORS["raised"], COLORS["focus"], radius),
        }
        self.style.element_create(
            "Midnight.tab", "image", self.tab_images["normal"],
            *[(state, self.tab_images[state]) for state in ("focus", "selected", "active")],
            border=radius, sticky="nsew",
        )
        self.style.layout("TNotebook.Tab", [("Midnight.tab", {
            "sticky": "nsew", "children": [("Notebook.padding", {
                "sticky": "nsew", "children": [("Notebook.label", {"sticky": "nsew"})],
            })],
        })])
        self.style.map("TNotebook.Tab", background=[
            ("selected", COLORS["background"]), ("active", COLORS["background"]),
        ], foreground=[("selected", COLORS["text"]), ("active", COLORS["text"])])

    def _buttons(self, root: tk.Tk, name: str, radius: int, accent: bool) -> None:
        normal = COLORS["accent"] if accent else COLORS["surface"]
        fills = {
            "normal": normal,
            "disabled": COLORS["disabled"],
            "pressed": COLORS["accent_pressed"] if accent else COLORS["pressed"],
            "active": COLORS["accent_hover"] if accent else COLORS["hover"],
            "focus": normal,
        }
        images = {
            state: rounded_image(
                root, fill,
                COLORS["focus"]
                if state == "focus" else (fill if accent else COLORS["border"]),
                radius,
            )
            for state, fill in fills.items()
        }
        self.images[name] = images
        element = f"Friendly.{name}.background"
        self.style.element_create(
            element, "image", images["normal"],
            *[(state, images[state]) for state in ("disabled", "pressed", "active", "focus")],
            border=radius, sticky="nsew",
        )
        self.style.layout(name, [(element, {
            "sticky": "nsew", "children": [
                ("Button.padding", {"sticky": "nsew", "children": [
                    ("Button.label", {"sticky": "nsew"})
                ]})
            ],
        })])
        self.style.configure(
            name, font=HEADING_FONT, padding=(14, 8), anchor="center",
            background=COLORS["background"], borderwidth=0,
            bordercolor=COLORS["background"], lightcolor=COLORS["background"],
            darkcolor=COLORS["background"],
            foreground=COLORS["button_text"] if accent else COLORS["text"],
        )
        self.style.map(
            name, foreground=[("disabled", COLORS["disabled_text"])],
            background=[(state, COLORS["background"]) for state in ("disabled", "pressed", "active", "focus")],
        )
