"""Edit ACTIVE_SCHEME or any hex color below, then restart the app."""

ACTIVE_SCHEME = "dark"

SCHEMES = {
    "dark": {
        "background": "#101522",
        "surface": "#192131",
        "raised": "#252e40",
        "text": "#edf2ff",
        "muted": "#a8b5cb",
        "border": "#364259",
        "accent": "#596fa8",
        "accent_hover": "#687fb8",
        "accent_pressed": "#495e91",
        "focus": "#9fb5ee",
        "progress": "#83d6b7",
        "hover": "#2b3750",
        "pressed": "#35415b",
        "disabled": "#1e2738",
        "disabled_text": "#8894aa",
        "selection": "#394666",
        "clock_green": "#175b4a",
        "clock_red": "#913b51",
        "clock_text": "#ffffff",
        "error": "#ffadbd",
        "button_text": "#ffffff",
        "pending_background": "#252e40",
        "pending_text": "#d0d8e7",
        "done_background": "#193d38",
        "done_text": "#83eed1",
        "missed_background": "#452735",
        "missed_text": "#ffadbd",
    },
    "light": {
        "background": "#f5f7fa",
        "surface": "#ffffff",
        "raised": "#e8edf3",
        "text": "#233047",
        "muted": "#53647a",
        "border": "#cbd5e1",
        "accent": "#49639d",
        "accent_hover": "#3b548b",
        "accent_pressed": "#304777",
        "focus": "#365fbb",
        "progress": "#24845d",
        "hover": "#edf1f7",
        "pressed": "#dfe6ef",
        "disabled": "#e8edf3",
        "disabled_text": "#66758a",
        "selection": "#dce7fa",
        "clock_green": "#247451",
        "clock_red": "#a6374d",
        "clock_text": "#ffffff",
        "error": "#9f2540",
        "button_text": "#ffffff",
        "pending_background": "#eeeeee",
        "pending_text": "#333333",
        "done_background": "#d7eddf",
        "done_text": "#195332",
        "missed_background": "#f8dce2",
        "missed_text": "#80283c",
    },
}

COLORS = SCHEMES[ACTIVE_SCHEME]
STATUS_COLORS = {
    status: (COLORS[f"{status}_background"], COLORS[f"{status}_text"])
    for status in ("pending", "done", "missed")
}
