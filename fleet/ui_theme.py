"""Fuelzone look & feel for the FleetCard helper window.

Presentation only: colour tokens, a type ramp and a few styled Tk building blocks.
Nothing here creates a Tk root, widgets, fonts or images at import time, so it is
safe to import before ``root = tk.Tk()``. The app hides old screens with pack_forget
and never destroys widgets, so the bars shown on every screen are created once (on
the main thread, in style_root) and simply re-packed.
"""
import tkinter as tk

# ---- Colour tokens ------------------------------------------------------------
BG = "#F2F4F8"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F6F8FB"
BORDER = "#DCE1E8"
BORDER_STRONG = "#B8C1CD"
TEXT = "#16202C"
TEXT_MUTED = "#5B6575"
TEXT_SUBTLE = "#8B94A3"

NAVY = "#0F2B46"
NAVY_RAISED = "#23486E"
NAVY_TEXT = "#FFFFFF"
NAVY_TEXT_MUTED = "#9DB3C9"
AMBER = "#F5A623"

ACCENT = "#1F6FEB"
ACCENT_HOVER = "#1A60D1"
ACCENT_PRESSED = "#154FAD"
ON_ACCENT = "#FFFFFF"
DISABLED_BG = "#E3E7ED"
DISABLED_FG = "#97A1AF"

TONES = {
    "info": {"bg": "#EAF2FF", "fg": "#0B4AA8", "border": "#BCD3F7"},
    "success": {"bg": "#E8F6EE", "fg": "#136C38", "border": "#B3DEC3"},
    "error": {"bg": "#FDEDEC", "fg": "#B42318", "border": "#F3C4C0"},
    "warning": {"bg": "#FFF5DE", "fg": "#845400", "border": "#EFD39A"},
}

# ---- Type ramp (plain tuples; Tk resolves them lazily) ------------------------
FAMILY = "Segoe UI"
FAMILY_SEMIBOLD = "Segoe UI Semibold"
FONT_BRAND = (FAMILY_SEMIBOLD, 12)
FONT_BRAND_SUB = (FAMILY, 10)
FONT_VERSION = (FAMILY, 9)
APP_VERSION = "v1.1"   # shown after the brand in the nav bar
FONT_STEP = (FAMILY_SEMIBOLD, 9)
FONT_CAPTION = (FAMILY_SEMIBOLD, 9)
FONT_BODY = (FAMILY, 10)
FONT_SMALL = (FAMILY, 9)
FONT_INPUT = (FAMILY, 15)
FONT_INPUT_COMPACT = (FAMILY, 14)
FONT_BUTTON = (FAMILY_SEMIBOLD, 11)
FONT_STATUS = (FAMILY_SEMIBOLD, 12)
FONT_NOTICE = (FAMILY_SEMIBOLD, 10)

# Widgets and images that are created once and reused across screens.
_SHARED = {}


def status_tone(text):
    """Tone for a status message; mirrors the app's own startswith checks (read-only)."""
    if text.startswith("Rego"):
        return "success"
    if text.startswith("Err"):
        return "error"
    return "info"


def tone_colors(tone):
    t = TONES[tone]
    return dict(fg=t["fg"], bg=t["bg"], highlightbackground=t["border"], highlightcolor=t["border"])


def notice_options(tone, **overrides):
    """Label options for a tinted notice (processing, errors, hints)."""
    opts = dict(font=FONT_NOTICE, padx=12, pady=2, bd=0, highlightthickness=1, **tone_colors(tone))
    opts.update(overrides)
    return opts


def panel_options(**overrides):
    opts = dict(bg=SURFACE, bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
    opts.update(overrides)
    return opts


def panel(master, **overrides):
    """White card with a hairline border."""
    return tk.Frame(master, **panel_options(**overrides))


def entry_options(font=FONT_INPUT, **overrides):
    """Flat white input: the flat border doubles as inner padding, the ring turns accent on focus."""
    opts = dict(font=font, relief="flat", bd=7, bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                insertwidth=2, highlightthickness=1, highlightbackground=BORDER_STRONG,
                highlightcolor=ACCENT, selectbackground=ACCENT, selectforeground=ON_ACCENT,
                disabledbackground=SURFACE_ALT, disabledforeground=TEXT_MUTED)
    opts.update(overrides)
    return opts


def style_root(root):
    """Main-thread setup: background, taskbar icon, status icons and both header bars."""
    root.configure(bg=BG)
    icons = [logo_image(root, size) for size in (48, 32, 16)]
    icons = [icon for icon in icons if icon is not None]
    if icons:
        try:
            root.iconphoto(True, *icons)
        except tk.TclError:
            pass
    logo_image(root, 24)
    for tone in _ICON_MARKS:
        status_icon(root, tone)
    for step in (1, 2):
        _SHARED[("header", step)] = Header(root, step=step)


def show_header(root, step):
    """Pack the shared brand bar for a screen (1 = card, 2 = odometer).

    One bar per step is created once and re-packed, so the bar belonging to the screen
    before has to come down first - otherwise both stay packed and the window grows a
    second navbar as soon as the operator swipes a card.
    """
    header = _SHARED.get(("header", step))
    if header is None:
        header = _SHARED[("header", step)] = Header(root, step=step)
    for key, widget in _SHARED.items():
        if key[0] == "header" and key[1] != step:
            widget.pack_forget()
    content_frame = getattr(root, "_content_frame", None)
    if content_frame is not None:
        header.pack(fill="x", before=content_frame)
    else:
        header.pack(fill="x")
    return header


def show_footer(root, connected):
    """Pack the shared footer showing the database state and the Tab hint."""
    key = ("footer", bool(connected))
    footer = _SHARED.get(key)
    if footer is None:
        footer = _SHARED[key] = StatusFooter(root, connected)
    footer.pack(side="bottom", fill="x")
    return footer


class Header(tk.Canvas):
    """Navy brand bar: logo, product name and a Card > Odometer progress indicator."""

    HEIGHT = 40
    STEPS = ("Card", "Odometer")

    def __init__(self, master, step=1, **kw):
        super().__init__(master, height=self.HEIGHT, bg=NAVY, bd=0, highlightthickness=0, **kw)
        self._step = step
        self.bind("<Configure>", self._draw, add="+")

    def _draw(self, _event=None):
        self.delete("all")
        mid = self.HEIGHT // 2
        x = 16
        logo = logo_image(self, 24)
        if logo is not None:
            self.create_image(x, mid, image=logo, anchor="w")
            x += 34
        brand = self.create_text(x, mid, text="Fuelzone", font=FONT_BRAND, fill=NAVY_TEXT, anchor="w")
        version = self.create_text(self.bbox(brand)[2] + 6, mid + 1, text=APP_VERSION,
                                   font=FONT_VERSION, fill=NAVY_TEXT_MUTED, anchor="w")
        x = self.bbox(version)[2] + 10
        self.create_line(x, mid - 9, x, mid + 9, fill=NAVY_RAISED)
        self.create_text(x + 10, mid, text="FleetCard", font=FONT_BRAND_SUB, fill=NAVY_TEXT_MUTED, anchor="w")

        right = self.winfo_width() - 16
        for index in range(len(self.STEPS), 0, -1):
            done, active = index < self._step, index == self._step
            label = self.create_text(right, mid, text=self.STEPS[index - 1], font=FONT_STEP, anchor="e",
                                     fill=NAVY_TEXT if active else NAVY_TEXT_MUTED)
            cx = self.bbox(label)[0] - 13
            if active:
                fill, outline, mark = AMBER, AMBER, NAVY
            elif done:
                fill, outline, mark = NAVY_RAISED, NAVY_RAISED, AMBER
            else:
                fill, outline, mark = NAVY, NAVY_TEXT_MUTED, NAVY_TEXT_MUTED
            self.create_oval(cx - 9, mid - 9, cx + 9, mid + 9, fill=fill, outline=outline)
            self.create_text(cx, mid, text="✓" if done else str(index), font=FONT_STEP, fill=mark)
            right = cx - 19
            if index > 1:
                chevron = self.create_text(right, mid - 1, text="›", font=(FAMILY, 13),
                                           fill=NAVY_TEXT_MUTED, anchor="e")
                right = self.bbox(chevron)[0] - 8


class Button(tk.Button):
    """Flat button with hover and disabled colours.

    It is still a real tk.Button (invoke/config/command all behave the same); it
    only repaints itself when its state is changed through configure/config.
    """

    KINDS = {
        "primary": dict(bg=ACCENT, fg=ON_ACCENT, hover=ACCENT_HOVER, pressed=ACCENT_PRESSED,
                        border=ACCENT, focus=NAVY),
        "secondary": dict(bg=SURFACE, fg=TEXT, hover="#EEF2F7", pressed="#E2E8F0",
                          border=BORDER_STRONG, focus=ACCENT),
    }

    def __init__(self, master=None, kind="primary", **kw):
        self._kind = self.KINDS[kind]
        self._hover = False
        opts = dict(font=FONT_BUTTON, relief="flat", bd=0, overrelief="flat", padx=18, pady=7,
                    highlightthickness=1, fg=self._kind["fg"], activeforeground=self._kind["fg"],
                    activebackground=self._kind["pressed"], disabledforeground=DISABLED_FG)
        opts.update(kw)
        super().__init__(master, **opts)
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self._paint()

    def configure(self, cnf=None, **kw):
        result = super().configure(cnf, **kw)
        if "state" in kw or (isinstance(cnf, dict) and "state" in cnf):
            self._paint()
        return result

    config = configure

    def _on_enter(self, _event):
        self._hover = True
        self._paint()

    def _on_leave(self, _event):
        self._hover = False
        self._paint()

    def _paint(self):
        kind = self._kind
        try:
            if str(self.cget("state")) == "disabled":
                tk.Button.configure(self, bg=DISABLED_BG, highlightbackground=DISABLED_BG,
                                    highlightcolor=DISABLED_BG, cursor="arrow")
            else:
                tk.Button.configure(self, bg=kind["hover"] if self._hover else kind["bg"],
                                    highlightbackground=kind["border"], highlightcolor=kind["focus"],
                                    cursor="hand2")
        except tk.TclError:
            pass


class StatusBanner(tk.Label):
    """Single-line tinted status bound to a StringVar; colour and icon follow the status text.

    Like the original label it never wraps, so a long error cannot push the buttons off screen.
    """

    def __init__(self, master, textvariable, **kw):
        opts = dict(textvariable=textvariable, font=FONT_STATUS, anchor="w", compound="left",
                    padx=12, pady=7, bd=0, highlightthickness=1)
        opts.update(kw)
        super().__init__(master, **opts)
        self._var = textvariable
        self._tone = None
        textvariable.trace_add("write", self._sync)
        self._sync()

    def _sync(self, *_args):
        try:
            tone = status_tone(self._var.get())
            if tone == self._tone:
                return
            self._tone = tone
            icon = _SHARED.get(("icon", tone))
            self.configure(image=icon if icon is not None else "", **tone_colors(tone))
        except tk.TclError:
            pass


class StatusFooter(tk.Frame):
    """Bottom bar with the database connection state and the card-reader hint."""

    def __init__(self, master, connected, **kw):
        super().__init__(master, bg=SURFACE, bd=0, highlightthickness=0, **kw)
        tk.Frame(self, bg=BORDER, height=1).pack(side="top", fill="x")
        row = tk.Frame(self, bg=SURFACE)
        row.pack(fill="x", padx=16, pady=6)
        dot = TONES["success" if connected else "error"]["fg"]
        tk.Label(row, text="●", fg=dot, bg=SURFACE, font=(FAMILY, 9)).pack(side="left")
        tk.Label(row, text="Database online" if connected else "Database offline",
                 fg=TEXT_MUTED, bg=SURFACE, font=FONT_SMALL).pack(side="left", padx=(5, 0))
        tk.Label(row, text="Swipe or type card, then Tab or Enter", fg=TEXT_SUBTLE, bg=SURFACE,
                 font=FONT_SMALL).pack(side="right")


# ---- Category table helpers ----------------------------------------------------
def style_option_menu(menubutton):
    menubutton.configure(font=FONT_BODY, bg=SURFACE, fg=TEXT, activebackground=SURFACE_ALT,
                         activeforeground=TEXT, relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER_STRONG, highlightcolor=ACCENT, anchor="w",
                         padx=10, pady=3, width=19, cursor="hand2")
    menu = menubutton.nametowidget(menubutton.cget("menu"))
    menu.configure(font=FONT_BODY, bg=SURFACE, fg=TEXT, activebackground=ACCENT,
                   activeforeground=ON_ACCENT, bd=0, relief="flat", activeborderwidth=0)


def mark_choice(menubutton, variable, placeholder="Select"):
    """Amber outline while a row still shows the placeholder; neutral once a category is chosen."""
    try:
        pending = variable.get() == placeholder
        menubutton.configure(highlightbackground=AMBER if pending else BORDER_STRONG,
                             fg=TEXT_MUTED if pending else TEXT)
    except tk.TclError:
        pass


def readonly_cell_options(**overrides):
    opts = dict(relief="flat", bd=0, highlightthickness=0, font=FONT_BODY, width=8, justify="right",
                disabledbackground=SURFACE, disabledforeground=TEXT, cursor="arrow")
    opts.update(overrides)
    return opts


# ---- Generated images (main thread only; cached) --------------------------------
_ICON_MARKS = {
    "info": [((8.0, 8.0), (8.0, 4.4)), ((8.0, 8.0), (10.8, 9.6))],
    "success": [((4.5, 8.3), (7.0, 10.8)), ((7.0, 10.8), (11.6, 5.4))],
    "error": [((5.3, 5.3), (10.7, 10.7)), ((10.7, 5.3), (5.3, 10.7))],
}


def status_icon(widget, tone):
    """16px round status glyph (clock, check or cross) plus an 8px gap, on the tone background."""
    key = ("icon", tone)
    if key not in _SHARED:
        t = TONES[tone]
        try:
            image = tk.PhotoImage(master=widget, width=24, height=16)
            image.put(_icon_pixels(t["bg"], t["fg"], _ICON_MARKS[tone]), to=(0, 0))
        except tk.TclError:
            image = None
        _SHARED[key] = image
    return _SHARED[key]


def logo_image(widget, size):
    """Brand mark (amber tile with a navy fuel drop); None if Tk refuses."""
    key = ("logo", size)
    if key not in _SHARED:
        try:
            image = tk.PhotoImage(master=widget, width=size, height=size)
            data, clear = _logo_pixels(size)
            image.put(data, to=(0, 0))
            for x, y in clear:
                image.transparency_set(x, y, True)
        except (tk.TclError, AttributeError):
            image = None
        _SHARED[key] = image
    return _SHARED[key]


def _icon_pixels(bg, fg, strokes, samples=3):
    back, ring, white = _rgb(bg), _rgb(fg), (255, 255, 255)
    total = samples * samples
    rows = []
    for y in range(16):
        row = []
        for x in range(24):
            disc = mark = 0
            for sy in range(samples):
                for sx in range(samples):
                    px, py = x + (sx + 0.5) / samples, y + (sy + 0.5) / samples
                    if (px - 8) ** 2 + (py - 8) ** 2 <= 64:
                        disc += 1
                        if any(_segment_distance(px, py, a, b) <= 0.95 for a, b in strokes):
                            mark += 1
            row.append(_hex(_mix(_mix(back, ring, disc / total), white, mark / total)))
        rows.append("{" + " ".join(row) + "}")
    return " ".join(rows)


def _logo_pixels(size, samples=3):
    amber, navy = _rgb(AMBER), _rgb(NAVY)
    total = samples * samples
    rows, clear = [], []
    for y in range(size):
        row = []
        for x in range(size):
            tile = drop = 0
            for sy in range(samples):
                for sx in range(samples):
                    u = (x + (sx + 0.5) / samples) / size
                    v = (y + (sy + 0.5) / samples) / size
                    if _in_tile(u, v):
                        tile += 1
                        if _in_drop(u, v):
                            drop += 1
            if tile * 2 < total:
                clear.append((x, y))
            row.append(_hex(_mix(amber, navy, drop / tile if tile else 0.0)))
        rows.append("{" + " ".join(row) + "}")
    return " ".join(rows), clear


def _segment_distance(px, py, a, b):
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _mix(a, b, fraction):
    return tuple(round(x + (y - x) * fraction) for x, y in zip(a, b))


def _rgb(hex_colour):
    return tuple(int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def _in_tile(u, v, radius=0.24):
    dx = max(abs(u - 0.5) - (0.5 - radius), 0.0)
    dy = max(abs(v - 0.5) - (0.5 - radius), 0.0)
    return dx * dx + dy * dy <= radius * radius


def _in_drop(u, v, cx=0.5, cy=0.6, r=0.21, tip=0.17):
    if (u - cx) ** 2 + (v - cy) ** 2 <= r * r:
        return True
    d = cy - tip
    sin_t = r / d
    cos_sq = 1 - sin_t * sin_t
    tangent_v = tip + d * cos_sq
    return tip <= v <= tangent_v and abs(u - cx) <= (v - tip) * sin_t / cos_sq ** 0.5
