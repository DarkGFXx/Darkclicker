import time
import math
import random
import threading
import ctypes
from ctypes import wintypes
import tkinter as tk
import customtkinter as ctk
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
from PIL import Image, ImageDraw, ImageTk, ImageFont

# Try importing pystray for PC system tray support
try:
    import pystray
    from pystray import MenuItem as item
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

# Appearance configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Dynamic theme: a black interface with one user-controlled secondary color.
THEMES = {
    "Custom": {
        "bg_dark": "#000000",
        "container_bg": "#0A0A0A",
        "container_border": "#FFFFFF",
        "text_on_container": "#FFFFFF",
        "accent": "#FFFFFF",
        "accent_hover": "#BDBDBD",
        "btn_dark": "#000000",
        "btn_dark_hover": "#161616",
        "particle_rgb": (255, 255, 255),
        "text_light": "#FFFFFF",
        "text_sub": "#FFFFFF",
        "status_inactive": "#666666",
    }
}

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Mapping UI keyboard labels to pynput Key objects or characters
KEY_MAPPINGS = {
    "Esc": Key.esc, "F1": Key.f1, "F2": Key.f2, "F3": Key.f3, "F4": Key.f4,
    "F5": Key.f5, "F6": Key.f6, "F7": Key.f7, "F8": Key.f8, "F9": Key.f9,
    "F10": Key.f10, "F11": Key.f11, "F12": Key.f12,
    "Back": Key.backspace, "Tab": Key.tab, "Caps": Key.caps_lock, "Enter": Key.enter,
    "Shift": Key.shift, "Shift ": Key.shift_r, "Ctrl": Key.ctrl, "Ctrl ": Key.ctrl_r,
    "Alt": Key.alt, "Alt ": Key.alt_r, "Space": Key.space
}


def get_active_window_title():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value


def get_open_window_titles():
    titles = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def enum_windows_callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title and title not in titles and title != "Program Manager":
                    titles.append(title)
        return True

    cb = EnumWindowsProc(enum_windows_callback)
    user32.EnumWindows(cb, 0)
    return sorted(titles, key=lambda s: s.lower())


def generate_black_tan_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill="#D2B48C")

    font_loaded = False
    for font_name in ["arialbd.ttf", "segoeuib.ttf", "Helvetica-Bold.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font = ImageFont.truetype(font_name, 170)
            draw.text((size / 2, size / 2 - 12), "D", fill="#0A0A0C", font=font, anchor="mm")
            font_loaded = True
            break
        except OSError:
            continue

    if not font_loaded:
        draw.pieslice([60, 48, 196, 208], start=270, end=90, fill="#0A0A0C")
        draw.rectangle([60, 48, 110, 208], fill="#0A0A0C")

    return ImageTk.PhotoImage(img)


def generate_knife_icon(color="#D2B48C"):
    size = 22
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(7, 3), (15, 3), (17, 11), (9, 13)], fill=color)
    draw.line([(15, 3), (17, 11)], fill="#FFFFFF", width=1)
    draw.polygon([(9, 13), (17, 11), (14, 19), (6, 19)], fill="#444444")
    draw.line([(7, 12), (18, 10)], fill="#666666", width=2)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def format_button_name(button):
    mapping = {
        Button.left: "M1 / LEFT",
        Button.right: "M2 / RIGHT",
        Button.middle: "M3 / WHEEL",
        Button.x1: "M4 / SIDE 1",
        Button.x2: "M5 / SIDE 2",
    }
    return mapping.get(button, str(button).replace("Button.", "").upper())


class KBMSelectorWindow(ctk.CTkToplevel):
    """Standalone, frameless selector for keyboard and extra mouse inputs."""

    MOUSE_BUTTONS = (
        ("M1 / LEFT", Button.left),
        ("M2 / RIGHT", Button.right),
        ("M3 / MIDDLE", Button.middle),
        ("M4 / SIDE 1", Button.x1),
        ("M5 / SIDE 2", Button.x2),
    )

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        theme = THEMES[parent.current_theme_name]

        self.overrideredirect(True)
        self.geometry("940x430")
        self.resizable(False, False)
        self.configure(fg_color=theme["bg_dark"])
        self.attributes("-topmost", True)
        self._drag_x = 0
        self._drag_y = 0
        self.key_buttons = {}
        self.mouse_buttons = {}

        self.rows = [
            ["Esc", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
            ["~", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Back"],
            ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
            ["Caps", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
            ["Shift", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift "],
            ["Ctrl", "Alt", "Space", "Alt ", "Ctrl "],
        ]
        self.key_widths = {
            "Esc": 45, "Back": 70, "Tab": 60, "Caps": 70, "Enter": 80,
            "Shift": 90, "Shift ": 90, "Ctrl": 60, "Ctrl ": 60,
            "Alt": 55, "Alt ": 55, "Space": 260,
        }

        self._create_titlebar()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=(6, 14))

        keyboard_panel = ctk.CTkFrame(
            body, fg_color=theme["container_bg"], border_color=theme["container_border"],
            border_width=1, corner_radius=12
        )
        keyboard_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        keyboard_header = ctk.CTkFrame(keyboard_panel, fg_color="transparent")
        keyboard_header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            keyboard_header, text="KEYBOARD LAYOUT", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["accent"]
        ).pack(side="left")
        ctk.CTkButton(
            keyboard_header, text="SELECT ALL", width=78, height=22,
            font=ctk.CTkFont(size=9, weight="bold"), fg_color=theme["btn_dark"],
            hover_color=theme["btn_dark_hover"], text_color=theme["accent"], command=self._select_all_keys
        ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(
            keyboard_header, text="CLEAR", width=56, height=22,
            font=ctk.CTkFont(size=9, weight="bold"), fg_color=theme["btn_dark"],
            hover_color=theme["btn_dark_hover"], text_color=theme["accent"], command=self._clear_all
        ).pack(side="right")

        for row in self.rows:
            row_frame = ctk.CTkFrame(keyboard_panel, fg_color="transparent")
            row_frame.pack(anchor="w", padx=12, pady=3)
            for key in row:
                button = ctk.CTkButton(
                    row_frame, text=key.strip(), width=self.key_widths.get(key, 42), height=34,
                    font=ctk.CTkFont(size=9, weight="bold"), corner_radius=6,
                    command=lambda selected_key=key: self._toggle_key(selected_key)
                )
                button.pack(side="left", padx=2)
                self.key_buttons[key] = button

        mouse_panel = ctk.CTkFrame(
            body, width=200, fg_color=theme["container_bg"], border_color=theme["container_border"],
            border_width=1, corner_radius=12
        )
        mouse_panel.pack(side="right", fill="y")
        mouse_panel.pack_propagate(False)
        ctk.CTkLabel(
            mouse_panel, text="MOUSE / OTHER", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["accent"]
        ).pack(anchor="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(
            mouse_panel, text="Select alongside keys\nto trigger them together.", justify="left",
            font=ctk.CTkFont(size=10), text_color=theme["text_light"]
        ).pack(anchor="w", padx=14, pady=(0, 12))

        for label, button_value in self.MOUSE_BUTTONS:
            button = ctk.CTkButton(
                mouse_panel, text=label, width=170, height=36, corner_radius=7,
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda selected_button=button_value: self._toggle_mouse_button(selected_button)
            )
            button.pack(padx=14, pady=4)
            self.mouse_buttons[button_value] = button

        self._refresh_styles()

    def _create_titlebar(self):
        theme = THEMES[self.parent.current_theme_name]
        bar = ctk.CTkFrame(self, height=42, fg_color="#050505", corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        title = ctk.CTkLabel(
            bar, text="DARKCLICKER  //  KBM, OTHER CONFIGURATION",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=theme["accent"]
        )
        title.pack(side="left", padx=14)
        for widget in (bar, title):
            widget.bind("<ButtonPress-1>", self._start_drag, add="+")
            widget.bind("<B1-Motion>", self._drag, add="+")

        ctk.CTkButton(
            bar, text="✕", width=34, height=30, fg_color="transparent", hover_color="#B91C1C",
            text_color="#FFFFFF", corner_radius=6, command=self.destroy
        ).pack(side="right", padx=(2, 8), pady=6)
        ctk.CTkButton(
            bar, text="—", width=34, height=30, fg_color="transparent",
            hover_color=theme["btn_dark_hover"], text_color=theme["accent"], corner_radius=6,
            command=self._minimize
        ).pack(side="right", padx=2, pady=6)

    def _start_drag(self, event):
        self._drag_x, self._drag_y = event.x_root, event.y_root

    def _drag(self, event):
        self.geometry(f"+{self.winfo_x() + event.x_root - self._drag_x}+{self.winfo_y() + event.y_root - self._drag_y}")
        self._drag_x, self._drag_y = event.x_root, event.y_root

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()
        self.bind("<FocusIn>", self._restore_after_minimize, add="+")

    def _restore_after_minimize(self, _event=None):
        self.overrideredirect(True)
        self.unbind("<FocusIn>")

    def _toggle_key(self, key_label):
        if key_label in self.parent.selected_kbm_keys:
            self.parent.selected_kbm_keys.remove(key_label)
        else:
            self.parent.selected_kbm_keys.add(key_label)
        self._refresh_styles()

    def _toggle_mouse_button(self, button_value):
        if button_value in self.parent.selected_mouse_buttons:
            self.parent.selected_mouse_buttons.remove(button_value)
        else:
            self.parent.selected_mouse_buttons.add(button_value)
        self._refresh_styles()

    def _select_all_keys(self):
        self.parent.selected_kbm_keys.update(key for row in self.rows for key in row)
        self._refresh_styles()

    def _clear_all(self):
        self.parent.selected_kbm_keys.clear()
        self.parent.selected_mouse_buttons.clear()
        self._refresh_styles()

    def _refresh_styles(self):
        theme = THEMES[self.parent.current_theme_name]
        for key, button in self.key_buttons.items():
            selected = key in self.parent.selected_kbm_keys
            button.configure(
                fg_color=theme["accent"] if selected else theme["btn_dark"],
                hover_color=theme["accent_hover"] if selected else theme["btn_dark_hover"],
                text_color="#000000" if selected else theme["text_light"],
            )
        for button_value, button in self.mouse_buttons.items():
            selected = button_value in self.parent.selected_mouse_buttons
            button.configure(
                fg_color=theme["accent"] if selected else theme["btn_dark"],
                hover_color=theme["accent_hover"] if selected else theme["btn_dark_hover"],
                text_color="#000000" if selected else theme["text_light"],
            )

class MinimizeNotificationPopup(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("440x120")
        self.configure(fg_color="#0A0A0C")

        self._drag_start_x = 0
        self._drag_start_y = 0

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 440) // 2
        y = (sh - 120) // 2
        self.geometry(f"440x120+{x}+{y}")

        self.canvas = tk.Canvas(self, bg="#0A0A0C", bd=0, highlightthickness=0, relief="flat")
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.particles = []
        for _ in range(22):
            self.particles.append({
                'x': random.randint(5, 435),
                'y': random.randint(-120, 0),
                'speed': random.uniform(0.8, 2.5),
                'size': random.uniform(0.6, 1.0),
                'pulse_phase': random.uniform(0, 6.28),
            })

        self.text_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.text_frame.place(relx=0.5, rely=0.5, anchor="center")

        self.msg_frame = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        self.msg_frame.pack(anchor="center", pady=(0, 6))

        l1 = ctk.CTkLabel(self.msg_frame, text="DarkClicker has been minimized, Use ", font=ctk.CTkFont(size=11), text_color="#E0D3C3")
        l1.pack(side="left")

        l2 = ctk.CTkLabel(self.msg_frame, text="SHIFT + F5", font=ctk.CTkFont(size=11, weight="bold"), text_color="#D2B48C")
        l2.pack(side="left")

        l3 = ctk.CTkLabel(self.msg_frame, text=" to kill conveniently when in tray.", font=ctk.CTkFont(size=11), text_color="#E0D3C3")
        l3.pack(side="left")

        self.countdown = 6
        self.timer_label = ctk.CTkLabel(self.text_frame, text=f"Close in {self.countdown} seconds", font=ctk.CTkFont(size=11, weight="bold"), text_color="#8C7A6B")
        self.timer_label.pack(anchor="center")

        for w in [self, self.canvas, self.text_frame, self.msg_frame, l1, l2, l3, self.timer_label]:
            self._make_draggable(w)

        self.after(10, self._apply_rounded_corners)
        self._anim_running = True
        self._animate()
        self._countdown_step()

    def _make_draggable(self, widget):
        widget.bind("<ButtonPress-1>", self._start_window_drag, add="+")
        widget.bind("<B1-Motion>", self._on_window_drag, add="+")

    def _start_window_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_window_drag(self, event):
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")

    def _apply_rounded_corners(self):
        try:
            hwnd = user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            rgn = gdi32.CreateRoundRectRgn(0, 0, 440, 120, 18, 18)
            user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def _animate(self):
        if not self._anim_running or not self.winfo_exists():
            return
        self.canvas.delete("cursor")
        for p in self.particles:
            p['y'] += p['speed']
            p['pulse_phase'] += 0.06
            if p['y'] > 120:
                p['y'] = -15
                p['x'] = random.randint(5, 435)

            scale = p['size'] * (1.0 + 0.12 * math.sin(p['pulse_phase']))
            color_val = int(120 + 60 * math.sin(p['pulse_phase']))
            hex_color = f"#{color_val:02x}{color_val:02x}{color_val:02x}"

            x, y = p['x'], p['y']
            pts = [
                x, y,
                x, y + (10 * scale),
                x + (3 * scale), y + (8 * scale),
                x + (5 * scale), y + (12 * scale),
                x + (7 * scale), y + (11 * scale),
                x + (5 * scale), y + (7 * scale),
                x + (8 * scale), y + (7 * scale)
            ]
            self.canvas.create_polygon(pts, fill=hex_color, outline="", tags="cursor")

        self.after(35, self._animate)

    def _countdown_step(self):
        if not self.winfo_exists():
            return
        if self.countdown > 0:
            self.timer_label.configure(text=f"Close in {self.countdown} seconds")
            self.countdown -= 1
            self.after(1000, self._countdown_step)
        else:
            self._anim_running = False
            self.destroy()


class DarkClicker(ctk.CTk):
    UNIVERSAL_APP = "All Applications (Universal)"

    def __init__(self):
        super().__init__()

        self.current_theme_name = "Custom"
        theme = THEMES[self.current_theme_name]

        # Window Setup with Default Always-On-Top
        self.overrideredirect(True)
        self.geometry("440x720+400+150")
        self.configure(fg_color=theme["bg_dark"])
        self.attributes("-topmost", True)

        self._drag_start_x = 0
        self._drag_start_y = 0

        self.icon_image = generate_black_tan_icon()
        self.knife_image = generate_knife_icon(theme["accent"])
        self.iconphoto(False, self.icon_image)

        # Controllers
        self.clicking = False
        self._click_state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self.mouse = MouseController()
        self.kbd_controller = KeyboardController()
        self.click_thread = None

        # KBM Storage & Window Handle
        self.selected_kbm_keys = set()
        self.selected_mouse_buttons = set()
        self.kbm_window = None

        # Hotkey and Flags
        self.current_hotkey = keyboard.Key.f6
        self.hotkey_name = "F6"
        self.capturing_hotkey = False
        self.is_synthetic_click = False
        self.ignore_trigger_until = 0
        self.flash_state = False
        self.pressed_keys = set()
        self._keyboard_hotkey_down = False
        self._mouse_hotkey_down = False
        self._hold_hotkey_source = None
        self._last_synthetic_mouse_click = 0.0
        self._polled_keyboard_down = False
        self._polled_hotkey_key = None
        self._polled_mouse_down = False
        self._polled_mouse_button = None
        self._hotkey_poll_after = None

        # CPS Dragging Dampener
        self._slider_drag_start_x = 0
        self._slider_start_val = 50

        # Tray Thread State
        self.tray_icon = None

        # Listeners
        self.kbd_listener = None
        self.mouse_listener = None
        self.cap_kbd = None
        self.cap_mouse = None

        # Variables
        self.cps_var = ctk.IntVar(value=50)
        self.max_speed_var = ctk.BooleanVar(value=False)
        self.hold_hotkey_var = ctk.BooleanVar(value=False)
        self.always_on_top_var = ctk.BooleanVar(value=True)
        self.theme_var = ctk.StringVar(value="white")
        self.mouse_button_var = ctk.StringVar(value="Left")
        self.click_type_var = ctk.StringVar(value="Single")
        self.target_app_var = ctk.StringVar(value=self.UNIVERSAL_APP)

        # Particle & Ripple Pools
        self.cursors_particles = []
        self.ripples = []
        self._init_falling_cursors()

        # UI & Canvas Creation
        self._create_background_canvas()
        self._create_infused_titlebar()
        self._create_ui()

        self.update_idletasks()
        self._apply_rounded_corners()

        self._init_system_tray()
        self._start_global_listeners()
        self._hotkey_poll_after = self.after(15, self._poll_keyboard_hotkey)
        self.refresh_app_list()

        self.bind_all("<Button-1>", self._spawn_ripple_event)

        self.after(30, self._animation_loop)
        self.after(500, self._flash_loop)

    def _apply_rounded_corners(self):
        try:
            hwnd = user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            rgn = gdi32.CreateRoundRectRgn(0, 0, 440, 660, 24, 24)
            user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def _init_system_tray(self):
        if not HAS_PYSTRAY:
            return

        def create_tray_image():
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill=THEMES[self.current_theme_name]["accent"])
            try:
                font = ImageFont.truetype("arialbd.ttf", 42)
                draw.text((32, 28), "D", fill="#0A0A0C", font=font, anchor="mm")
            except OSError:
                draw.text((32, 28), "D", fill="#0A0A0C", anchor="mm")
            return img

        menu = (
            item('Show DarkClicker', lambda: self.after(0, self._restore_from_tray), default=True),
            item('Toggle Clicker', lambda: self.after(0, self.toggle_clicking)),
            item('Exit', lambda: self.after(0, self._on_close))
        )
        self.tray_icon = pystray.Icon("DarkClicker", create_tray_image(), "DarkClicker Engine", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _init_falling_cursors(self):
        for _ in range(45):
            self.cursors_particles.append({
                'x': random.randint(5, 435),
                'y': random.randint(-660, 0),
                'speed': random.uniform(1.0, 3.2),
                'size': random.uniform(0.65, 1.25),
                'pulse_phase': random.uniform(0, 6.28),
            })

    def _create_background_canvas(self):
        theme = THEMES[self.current_theme_name]
        self.bg_canvas = tk.Canvas(self, bg=theme["bg_dark"], bd=0, highlightthickness=0, relief="flat")
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Transparent Canvas Text
        self.logo_text_id = self.bg_canvas.create_text(
            20, 28, text="DarkClicker",
            font=("Segoe Script", 24, "bold"),
            fill=theme["text_light"], anchor="w"
        )
        # Modified Subtitle Header Text
        self.subtitle_text_id = self.bg_canvas.create_text(
            20, 56, text="CLASS-A MOUSE & KBM CLICKER",
            font=("Inter", 8, "bold"),
            fill=theme["text_sub"], anchor="w"
        )
        self.status_text_id = self.bg_canvas.create_text(
            20, 74, text="● SYSTEM INACTIVE",
            font=("Inter", 9, "bold"),
            fill=theme["status_inactive"], anchor="w"
        )
        self.footer_text_id = self.bg_canvas.create_text(
            44, 700, text="Shift + F5 to killswitch",
            font=("Inter", 9, "bold"),
            fill=theme["text_sub"], anchor="w"
        )

        self.bg_canvas.bind("<ButtonPress-1>", self._start_window_drag, add="+")
        self.bg_canvas.bind("<B1-Motion>", self._on_window_drag, add="+")

    def _create_infused_titlebar(self):
        theme = THEMES[self.current_theme_name]
        self.header_bar = ctk.CTkFrame(self, fg_color="transparent", width=80, height=35)
        self.header_bar.place(x=350, y=10)

        self.min_btn = ctk.CTkButton(
            self.header_bar,
            text="─",
            width=30, height=30,
            fg_color="transparent",
            hover_color=theme["btn_dark_hover"],
            border_width=0,
            text_color=theme["accent"],
            corner_radius=6,
            command=self._minimize_window
        )
        self.min_btn.pack(side="left", padx=2)

        self.close_btn = ctk.CTkButton(
            self.header_bar,
            text="✕",
            width=30, height=30,
            fg_color="transparent",
            hover_color="#DC2626",
            border_width=0,
            text_color="#FFFFFF",
            corner_radius=6,
            command=self._on_close
        )
        self.close_btn.pack(side="left", padx=2)

    def _create_ui(self):
        theme = THEMES[self.current_theme_name]

        self.container = ctk.CTkFrame(
            self,
            fg_color=theme["container_bg"],
            corner_radius=16,
            border_width=1,
            border_color=theme["container_border"],
            width=400, height=470
        )
        self.container.pack_propagate(False)
        self.container.place(x=20, y=92)

        # Target App Lock
        app_header = ctk.CTkFrame(self.container, fg_color="transparent")
        app_header.pack(fill="x", padx=16, pady=(10, 2))

        self.app_lbl = ctk.CTkLabel(
            app_header,
            text="TARGET APPLICATION LOCK",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.app_lbl.pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            app_header,
            text="↻ REFRESH",
            width=65, height=18,
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=theme["btn_dark"],
            hover_color=theme["btn_dark_hover"],
            text_color=theme["accent"],
            corner_radius=4,
            command=self.refresh_app_list
        )
        self.refresh_btn.pack(side="right")

        self.app_selector = ctk.CTkOptionMenu(
            self.container,
            values=[self.UNIVERSAL_APP],
            variable=self.target_app_var,
            fg_color=theme["btn_dark"],
            button_color=theme["btn_dark_hover"],
            button_hover_color=theme["btn_dark"],
            dropdown_fg_color=theme["btn_dark"],
            text_color="#E0D3C3",
            corner_radius=8
        )
        self.app_selector.pack(fill="x", padx=16, pady=(2, 6))

        self.sep1 = ctk.CTkFrame(self.container, fg_color=theme["container_border"], height=1)
        self.sep1.pack(fill="x", padx=16, pady=2)

        # CPS Control Section (Up to 2500 CPS)
        cps_header = ctk.CTkFrame(self.container, fg_color="transparent")
        cps_header.pack(fill="x", padx=16, pady=(6, 0))

        self.cps_lbl = ctk.CTkLabel(
            cps_header,
            text="TARGET SPEED",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.cps_lbl.pack(side="left")

        self.cps_display_label = ctk.CTkLabel(
            cps_header,
            text="50 CPS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.cps_display_label.pack(side="right")

        self.cps_slider = ctk.CTkSlider(
            self.container,
            from_=1,
            to=2500,
            number_of_steps=2499,
            variable=self.cps_var,
            command=self._on_slider_move,
            button_color=theme["btn_dark"],
            button_hover_color=theme["btn_dark_hover"],
            progress_color=theme["btn_dark"],
            fg_color=theme["container_border"]
        )
        self.cps_slider.pack(fill="x", padx=16, pady=(4, 2))

        self.cps_slider.bind("<ButtonPress-1>", self._on_slider_press, add="+")
        self.cps_slider.bind("<B1-Motion>", self._on_slider_drag, add="+")

        self.precision_note = ctk.CTkLabel(
            self.container,
            text="Hold CTRL for precise speed toggle",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.precision_note.pack(anchor="e", padx=16, pady=(0, 2))

        # Max Speed Switch
        self.max_speed_switch = ctk.CTkSwitch(
            self.container,
            text="Enable Unlimited / Max Speed",
            variable=self.max_speed_var,
            command=self._toggle_max_speed,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["text_on_container"],
            progress_color=theme["btn_dark"],
            button_color="#E0D3C3",
            button_hover_color="#FFFFFF"
        )
        self.max_speed_switch.pack(anchor="w", padx=16, pady=(0, 4))

        self.sep2 = ctk.CTkFrame(self.container, fg_color=theme["container_border"], height=1)
        self.sep2.pack(fill="x", padx=16, pady=2)

        # Mouse / KBM Options
        options_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        options_frame.pack(fill="x", padx=16, pady=4)

        btn_col = ctk.CTkFrame(options_frame, fg_color="transparent")
        btn_col.pack(side="left", fill="x", expand=True, padx=(0, 8))

        mb_header = ctk.CTkFrame(btn_col, fg_color="transparent")
        mb_header.pack(fill="x")

        self.mb_lbl = ctk.CTkLabel(mb_header, text="MOUSE / INPUT", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme["text_on_container"])
        self.mb_lbl.pack(side="left")

        self.kbm_cfg_btn = ctk.CTkButton(
            mb_header, text="⌨ CONFIG", width=55, height=16,
            font=ctk.CTkFont(size=8, weight="bold"),
            fg_color=theme["btn_dark"], hover_color=theme["btn_dark_hover"],
            text_color=theme["accent"], corner_radius=4,
            command=self._open_kbm_selector
        )

        self.button_selector = ctk.CTkOptionMenu(
            btn_col,
            values=["Left", "Right", "Middle", "KBM, Other"],
            variable=self.mouse_button_var,
            command=self._on_input_option_changed,
            fg_color=theme["btn_dark"],
            button_color=theme["btn_dark_hover"],
            button_hover_color=theme["btn_dark"],
            dropdown_fg_color=theme["btn_dark"],
            text_color="#E0D3C3",
            corner_radius=8
        )
        self.button_selector.pack(fill="x", pady=(2, 0))

        type_col = ctk.CTkFrame(options_frame, fg_color="transparent")
        type_col.pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.ct_lbl = ctk.CTkLabel(type_col, text="CLICK TYPE", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme["text_on_container"])
        self.ct_lbl.pack(anchor="w")

        self.type_selector = ctk.CTkOptionMenu(
            type_col,
            values=["Single", "Double"],
            variable=self.click_type_var,
            fg_color=theme["btn_dark"],
            button_color=theme["btn_dark_hover"],
            button_hover_color=theme["btn_dark"],
            dropdown_fg_color=theme["btn_dark"],
            text_color="#E0D3C3",
            corner_radius=8
        )
        self.type_selector.pack(fill="x", pady=(2, 0))

        self.sep3 = ctk.CTkFrame(self.container, fg_color=theme["container_border"], height=1)
        self.sep3.pack(fill="x", padx=16, pady=2)

        # Hotkey Header & Selector
        hotkey_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        hotkey_frame.pack(fill="x", padx=16, pady=(4, 2))

        self.hk_lbl = ctk.CTkLabel(
            hotkey_frame,
            text="TOGGLE / HOLD HOTKEY",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.hk_lbl.pack(side="left")

        self.hotkey_btn = ctk.CTkButton(
            hotkey_frame,
            text=f"[{self.hotkey_name}]",
            width=110, height=24,
            fg_color=theme["btn_dark"],
            hover_color=theme["btn_dark_hover"],
            text_color=theme["accent"],
            border_width=1,
            border_color=theme["btn_dark_hover"],
            corner_radius=6,
            command=self._listen_for_new_hotkey
        )
        self.hotkey_btn.pack(side="right")

        # Switches & Theme Selector Grid
        bottom_grid = ctk.CTkFrame(self.container, fg_color="transparent")
        bottom_grid.pack(fill="x", padx=16, pady=(4, 6))

        left_switches = ctk.CTkFrame(bottom_grid, fg_color="transparent")
        left_switches.pack(side="left", anchor="w")

        self.hold_hotkey_switch = ctk.CTkSwitch(
            left_switches,
            text="Hold hotkey",
            variable=self.hold_hotkey_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["text_on_container"],
            progress_color=theme["btn_dark"],
            button_color="#E0D3C3",
            button_hover_color="#FFFFFF"
        )
        self.hold_hotkey_switch.pack(anchor="w", pady=(0, 4))

        self.always_on_top_switch = ctk.CTkSwitch(
            left_switches,
            text="Always on top",
            variable=self.always_on_top_var,
            command=self._toggle_always_on_top,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["text_on_container"],
            progress_color=theme["btn_dark"],
            button_color="#E0D3C3",
            button_hover_color="#FFFFFF"
        )
        self.always_on_top_switch.pack(anchor="w")

        right_theme = ctk.CTkFrame(bottom_grid, fg_color="transparent")
        right_theme.pack(side="right", anchor="e")

        self.theme_lbl = ctk.CTkLabel(
            right_theme,
            text="ACCENT COLOR",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["text_on_container"]
        )
        self.theme_lbl.pack(anchor="e")

        self.theme_selector = ctk.CTkEntry(
            right_theme,
            textvariable=self.theme_var,
            width=120, height=24,
            fg_color=theme["btn_dark"],
            border_color=theme["btn_dark_hover"],
            text_color=theme["accent"],
            placeholder_text="blue or #00aaff",
            placeholder_text_color=theme["text_sub"],
            corner_radius=6
        )
        self.theme_selector.bind("<KeyRelease>", self._on_theme_typed)
        self.theme_selector.pack(anchor="e", pady=(2, 0))

        # Primary Start / Stop Button
        self.toggle_btn = ctk.CTkButton(
            self,
            text="START CLICKING",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            fg_color="transparent",
            hover_color=theme["bg_dark"],
            text_color=theme["accent"],
            corner_radius=20,
            border_width=0,
            border_color=theme["accent"],
            width=400, height=38,
            command=self.toggle_clicking
        )
        self.toggle_btn.place(x=20, y=580)
        self.toggle_btn.bind("<Enter>", self._toggle_button_enter, add="+")
        self.toggle_btn.bind("<Leave>", self._toggle_button_leave, add="+")

        # Footer Knife Icon
        self.knife_lbl = ctk.CTkLabel(self, image=self.knife_image, text="", fg_color="transparent")
        self.knife_lbl.place(x=20, y=682)

    def _on_input_option_changed(self, choice):
        if choice == "KBM, Other":
            self.kbm_cfg_btn.pack(side="right", padx=(4, 0))
            self._open_kbm_selector()
        else:
            self.kbm_cfg_btn.pack_forget()

    def _toggle_button_enter(self, _event=None):
        self.toggle_btn.configure(
            border_width=2,
            border_color=THEMES[self.current_theme_name]["accent"],
        )

    def _toggle_button_leave(self, _event=None):
        self.toggle_btn.configure(border_width=0)

    def _open_kbm_selector(self):
        if self.kbm_window is None or not self.kbm_window.winfo_exists():
            self.kbm_window = KBMSelectorWindow(self)
        else:
            self.kbm_window.lift()
            self.kbm_window.focus_force()

    def _toggle_always_on_top(self):
        self.attributes("-topmost", self.always_on_top_var.get())

    def _on_theme_typed(self, _event=None):
        """Apply any valid Tk color name or hexadecimal color as it is typed."""
        color_text = self.theme_selector.get().strip()
        if not color_text:
            return
        try:
            red, green, blue = self.winfo_rgb(color_text)
        except tk.TclError:
            return

        accent = f"#{red // 256:02x}{green // 256:02x}{blue // 256:02x}"
        hover = f"#{max(0, red // 320):02x}{max(0, green // 320):02x}{max(0, blue // 320):02x}"
        THEMES["Custom"].update(
            accent=accent,
            accent_hover=hover,
            container_border=accent,
            text_sub=accent,
            particle_rgb=(red // 256, green // 256, blue // 256),
        )
        self.theme_var.set(color_text)
        self._apply_theme("Custom")

    def _apply_theme(self, theme_name="Custom"):
        self.current_theme_name = "Custom"
        t = THEMES["Custom"]

        self.configure(fg_color=t["bg_dark"])
        self.bg_canvas.configure(bg=t["bg_dark"])

        self.bg_canvas.itemconfig(self.logo_text_id, fill=t["text_light"])
        self.bg_canvas.itemconfig(self.subtitle_text_id, fill=t["text_sub"])
        self.bg_canvas.itemconfig(self.footer_text_id, fill=t["text_sub"])

        if not self.clicking:
            self.bg_canvas.itemconfig(self.status_text_id, fill=t["status_inactive"])

        self.container.configure(fg_color=t["container_bg"], border_color=t["container_border"])
        self.sep1.configure(fg_color=t["container_border"])
        self.sep2.configure(fg_color=t["container_border"])
        self.sep3.configure(fg_color=t["container_border"])

        for lbl in [self.app_lbl, self.cps_lbl, self.cps_display_label, self.precision_note,
                    self.mb_lbl, self.ct_lbl, self.hk_lbl, self.theme_lbl]:
            lbl.configure(text_color=t["text_on_container"])

        for sw in [self.max_speed_switch, self.hold_hotkey_switch, self.always_on_top_switch]:
            sw.configure(text_color=t["text_on_container"], progress_color=t["btn_dark"])

        for menu in [self.app_selector, self.button_selector, self.type_selector]:
            menu.configure(
                fg_color=t["btn_dark"],
                button_color=t["btn_dark_hover"],
                button_hover_color=t["btn_dark"],
                dropdown_fg_color=t["btn_dark"]
            )
        self.theme_selector.configure(
            fg_color=t["btn_dark"], border_color=t["btn_dark_hover"], text_color=t["accent"]
        )

        self.refresh_btn.configure(fg_color=t["btn_dark"], hover_color=t["btn_dark_hover"], text_color=t["accent"])
        self.kbm_cfg_btn.configure(fg_color=t["btn_dark"], hover_color=t["btn_dark_hover"], text_color=t["accent"])
        self.hotkey_btn.configure(fg_color=t["btn_dark"], hover_color=t["btn_dark_hover"], border_color=t["btn_dark_hover"], text_color=t["accent"])
        self.min_btn.configure(hover_color=t["btn_dark_hover"], text_color=t["accent"])

        self.toggle_btn.configure(
            fg_color="transparent", hover_color=t["bg_dark"], text_color=t["accent"],
            border_color=t["accent"]
        )

        self.cps_slider.configure(button_color=t["btn_dark"], button_hover_color=t["btn_dark_hover"],
                                  progress_color=t["btn_dark"], fg_color=t["container_border"])

        self.knife_image = generate_knife_icon(t["accent"])
        self.knife_lbl.configure(image=self.knife_image)

        if self.kbm_window and self.kbm_window.winfo_exists():
            self.kbm_window.configure(fg_color=t["bg_dark"])
            self.kbm_window._refresh_styles()

    def _start_window_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_window_drag(self, event):
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")

    def _minimize_window(self):
        self.withdraw()
        try:
            MinimizeNotificationPopup(self)
        except Exception:
            pass

    def _restore_from_tray(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _is_ctrl_pressed(self):
        try:
            return (user32.GetAsyncKeyState(0x11) & 0x8000) != 0
        except Exception:
            return False

    def _on_slider_press(self, event):
        self._slider_drag_start_x = event.x
        self._slider_start_val = self.cps_var.get()

    def _on_slider_drag(self, event):
        theme = THEMES[self.current_theme_name]
        ctrl_held = self._is_ctrl_pressed()

        if ctrl_held:
            dx = event.x - self._slider_drag_start_x
            inc_delta = int(dx / 8.0)
            new_val = max(1, min(2500, self._slider_start_val + inc_delta))
            self.cps_var.set(new_val)
            self.cps_slider.set(new_val)
            # Transient Neon White glow when CTRL is held
            self.precision_note.configure(text_color="#FFFFFF")
            if not self.max_speed_var.get():
                self.cps_display_label.configure(text=f"{new_val} CPS")
        else:
            val = self.cps_slider.get()
            snapped = max(1, min(2500, int(round(val / 5.0) * 5)))
            self.cps_var.set(snapped)
            self.cps_slider.set(snapped)
            self.precision_note.configure(text_color=theme["text_on_container"])
            if not self.max_speed_var.get():
                self.cps_display_label.configure(text=f"{snapped} CPS")

    def _on_slider_move(self, value):
        theme = THEMES[self.current_theme_name]
        if self._is_ctrl_pressed():
            self.precision_note.configure(text_color="#FFFFFF")
        else:
            self.precision_note.configure(text_color=theme["text_on_container"])
            snapped = max(1, min(2500, int(round(value / 5.0) * 5)))
            self.cps_var.set(snapped)
            if not self.max_speed_var.get():
                self.cps_display_label.configure(text=f"{snapped} CPS")

    def _spawn_ripple_event(self, event):
        x = event.x_root - self.winfo_rootx()
        y = event.y_root - self.winfo_rooty()
        self.ripples.append({
            'x': x,
            'y': y,
            'radius': 3,
            'max_radius': 45,
        })

    def _flash_loop(self):
        theme = THEMES[self.current_theme_name]
        if self.clicking:
            self.flash_state = not self.flash_state
            flash_color = theme["accent"] if self.flash_state else theme["text_sub"]
            self.bg_canvas.itemconfig(
                self.status_text_id,
                text="● SYSTEM ACTIVE - CLICKING",
                fill=flash_color
            )
        else:
            self.bg_canvas.itemconfig(
                self.status_text_id,
                text="● SYSTEM INACTIVE",
                fill=theme["status_inactive"]
            )
        self.after(500, self._flash_loop)

    def _animation_loop(self):
        # Continuous precision label transient glow check
        theme = THEMES[self.current_theme_name]
        if self._is_ctrl_pressed():
            self.precision_note.configure(text_color="#FFFFFF")
        else:
            self.precision_note.configure(text_color=theme["text_on_container"])

        self.bg_canvas.delete("particle")
        self.bg_canvas.delete("ripple")

        t = THEMES[self.current_theme_name]
        r_base, g_base, b_base = t["particle_rgb"]

        for p in self.cursors_particles:
            p['y'] += p['speed']
            p['pulse_phase'] += 0.06
            if p['y'] > 720:
                p['y'] = -20
                p['x'] = random.randint(5, 435)

            scale = p['size'] * (1.0 + 0.12 * math.sin(p['pulse_phase']))
            factor = 0.55 + 0.45 * math.sin(p['pulse_phase'])
            r = int(r_base * factor)
            g = int(g_base * factor)
            b = int(b_base * factor)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"

            x, y = p['x'], p['y']
            pts = [
                x, y,
                x, y + (13 * scale),
                x + (4 * scale), y + (10 * scale),
                x + (7 * scale), y + (15 * scale),
                x + (9 * scale), y + (14 * scale),
                x + (6 * scale), y + (9 * scale),
                x + (10 * scale), y + (9 * scale)
            ]
            self.bg_canvas.create_polygon(pts, fill=hex_color, outline="", tags="particle")

        active_ripples = []
        for rip in self.ripples:
            rip['radius'] += 2.8
            progress = rip['radius'] / rip['max_radius']
            if progress < 1.0:
                alpha_factor = 1.0 - progress
                r = int(r_base * alpha_factor)
                g = int(g_base * alpha_factor)
                b = int(b_base * alpha_factor)
                hex_ripple = f"#{r:02x}{g:02x}{b:02x}"

                x, y, rad = rip['x'], rip['y'], rip['radius']
                self.bg_canvas.create_oval(
                    x - rad, y - rad, x + rad, y + rad,
                    outline=hex_ripple, width=2, tags="ripple"
                )
                active_ripples.append(rip)

        self.ripples = active_ripples

        self.bg_canvas.tag_lower("particle")
        self.bg_canvas.tag_lower("ripple")

        self.after(30, self._animation_loop)

    def refresh_app_list(self):
        current_selection = self.target_app_var.get()
        windows = get_open_window_titles()
        options = [self.UNIVERSAL_APP] + windows
        self.app_selector.configure(values=options)
        if current_selection not in options:
            self.target_app_var.set(self.UNIVERSAL_APP)

    def _toggle_max_speed(self):
        if self.max_speed_var.get():
            self.cps_slider.configure(state="disabled")
            self.cps_display_label.configure(text="UNLIMITED")
        else:
            self.cps_slider.configure(state="normal")
            self.cps_display_label.configure(text=f"{self.cps_var.get()} CPS")

    def _get_target_button(self):
        btn = self.mouse_button_var.get()
        if btn == "Right":
            return Button.right
        elif btn == "Middle":
            return Button.middle
        return Button.left

    def toggle_clicking(self):
        if self.clicking:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        with self._click_state_lock:
            if self.clicking:
                return
            self.clicking = True
            self._stop_event.clear()
        theme = THEMES[self.current_theme_name]
        self.toggle_btn.configure(
            text="STOP CLICKING",
            fg_color="transparent",
            hover_color=theme["bg_dark"],
            text_color=theme["accent"]
        )
        self.click_thread = threading.Thread(target=self._click_loop, daemon=True)
        self.click_thread.start()

    def stop_clicking(self):
        with self._click_state_lock:
            self.clicking = False
            self._stop_event.set()
        theme = THEMES[self.current_theme_name]
        self.toggle_btn.configure(
            text="START CLICKING",
            fg_color="transparent",
            hover_color=theme["bg_dark"],
            text_color=theme["accent"]
        )

    def trigger_killswitch(self):
        self.stop_clicking()
        self.bg_canvas.itemconfig(
            self.status_text_id,
            text="● KILLSWITCH ACTIVATED",
            fill="#EF4444"
        )

    def _click_loop(self):
        is_double = self.click_type_var.get() == "Double"

        while self.clicking and not self._stop_event.is_set():
            target_app = self.target_app_var.get()
            if target_app != self.UNIVERSAL_APP:
                active_window = get_active_window_title()
                if target_app.lower() not in active_window.lower():
                    time.sleep(0.05)
                    continue

            self.is_synthetic_click = True
            mode = self.mouse_button_var.get()
            clicks = 2 if is_double else 1

            if self._stop_event.is_set():
                self.is_synthetic_click = False
                break

            # Execute Mouse or KBM Keyboard Keys
            if mode == "KBM, Other":
                for k_label in list(self.selected_kbm_keys):
                    pynput_key = KEY_MAPPINGS.get(k_label, k_label.lower())
                    try:
                        self.kbd_controller.press(pynput_key)
                        self.kbd_controller.release(pynput_key)
                    except Exception:
                        pass
                for mouse_button in list(self.selected_mouse_buttons):
                    try:
                        self._last_synthetic_mouse_click = time.monotonic()
                        self.mouse.click(mouse_button, clicks)
                    except Exception:
                        pass
            else:
                target_btn = self._get_target_button()
                try:
                    self._last_synthetic_mouse_click = time.monotonic()
                    self.mouse.click(target_btn, clicks)
                except Exception:
                    pass

            time.sleep(0.0005)
            self.is_synthetic_click = False

            if self.max_speed_var.get():
                self._stop_event.wait(0.0001)
            else:
                cps = max(1, self.cps_var.get())
                delay = 1.0 / cps
                self._stop_event.wait(delay)

    @staticmethod
    def _mouse_virtual_key(button):
        return {
            Button.left: 0x01,
            Button.right: 0x02,
            Button.middle: 0x04,
            Button.x1: 0x05,
            Button.x2: 0x06,
        }.get(button)

    def _physical_mouse_down(self, button):
        virtual_key = self._mouse_virtual_key(button)
        if virtual_key is None:
            return False
        try:
            return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)
        except Exception:
            return False

    @staticmethod
    def _keyboard_virtual_key(key):
        function_keys = {
            keyboard.Key.f1: 0x70, keyboard.Key.f2: 0x71,
            keyboard.Key.f3: 0x72, keyboard.Key.f4: 0x73,
            keyboard.Key.f5: 0x74, keyboard.Key.f6: 0x75,
            keyboard.Key.f7: 0x76, keyboard.Key.f8: 0x77,
            keyboard.Key.f9: 0x78, keyboard.Key.f10: 0x79,
            keyboard.Key.f11: 0x7A, keyboard.Key.f12: 0x7B,
        }
        if key in function_keys:
            return function_keys[key]
        char = getattr(key, "char", None)
        if char and len(char) == 1:
            value = ord(char.upper())
            if "A" <= char.upper() <= "Z" or "0" <= char <= "9":
                return value
        return None

    def _poll_keyboard_hotkey(self):
        """Use Windows key state for reliable keyboard or mouse edges."""
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        hotkey = self.current_hotkey
        keyboard_vk = self._keyboard_virtual_key(hotkey)
        mouse_vk = self._mouse_virtual_key(hotkey)
        if keyboard_vk is not None:
            self._polled_mouse_down = False
            self._polled_mouse_button = None
            if hotkey != self._polled_hotkey_key:
                self._polled_keyboard_down = False
                self._polled_hotkey_key = hotkey
            try:
                is_down = bool(user32.GetAsyncKeyState(keyboard_vk) & 0x8000)
            except Exception:
                is_down = False

            if is_down and not self._polled_keyboard_down:
                self._polled_keyboard_down = True
                self._keyboard_hotkey_down = True
                if self.hold_hotkey_var.get():
                    self._hold_hotkey_source = "keyboard"
                    self.start_clicking()
                else:
                    self.toggle_clicking()
            elif not is_down and self._polled_keyboard_down:
                self._polled_keyboard_down = False
                self._keyboard_hotkey_down = False
                self.pressed_keys.discard(hotkey)
                if self._hold_hotkey_source == "keyboard":
                    self._stop_hold_from_hotkey("keyboard")
        elif mouse_vk is not None:
            self._polled_keyboard_down = False
            self._polled_hotkey_key = None
            if hotkey != self._polled_mouse_button:
                self._polled_mouse_down = False
                self._polled_mouse_button = hotkey
            try:
                is_down = bool(user32.GetAsyncKeyState(mouse_vk) & 0x8000)
            except Exception:
                is_down = False

            if is_down and not self._polled_mouse_down:
                self._polled_mouse_down = True
                self._mouse_hotkey_down = True
                if self.hold_hotkey_var.get():
                    self._hold_hotkey_source = "mouse"
                    self.start_clicking()
                else:
                    self.toggle_clicking()
            elif not is_down and self._polled_mouse_down:
                self._polled_mouse_down = False
                self._mouse_hotkey_down = False
                if self._hold_hotkey_source == "mouse":
                    self._stop_hold_from_hotkey("mouse")
        else:
            self._polled_keyboard_down = False
            self._polled_hotkey_key = None
            self._polled_mouse_down = False
            self._polled_mouse_button = None

        self._hotkey_poll_after = self.after(15, self._poll_keyboard_hotkey)

    def _watch_keyboard_hotkey_release(self, key):
        """Clear a missed pynput release once Windows reports the key up."""
        if key != self.current_hotkey or not self._keyboard_hotkey_down:
            return
        virtual_key = self._keyboard_virtual_key(key)
        if virtual_key is not None:
            try:
                still_down = bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)
            except Exception:
                still_down = True
            if still_down:
                self.after(35, self._watch_keyboard_hotkey_release, key)
                return

        self._keyboard_hotkey_down = False
        self.pressed_keys.discard(key)
        if self._hold_hotkey_source == "keyboard":
            self.after(0, self._stop_hold_from_hotkey, "keyboard")

    def _start_hold_from_hotkey(self, source):
        still_down = (
            self._keyboard_hotkey_down if source == "keyboard"
            else self._mouse_hotkey_down
        )
        if self._hold_hotkey_source == source and still_down:
            self.start_clicking()

    def _stop_hold_from_hotkey(self, source):
        if self._hold_hotkey_source == source:
            self._hold_hotkey_source = None
            self.stop_clicking()

    def _reconcile_mouse_hotkey(self):
        """Recover a physical release that overlapped a generated click."""
        button = self.current_hotkey
        if self._mouse_virtual_key(button) is None or not self._mouse_hotkey_down:
            return
        if self._physical_mouse_down(button):
            return
        self._mouse_hotkey_down = False
        if self._hold_hotkey_source == "mouse":
            self.after(0, self._stop_hold_from_hotkey, "mouse")

    def _start_global_listeners(self):
        def on_key_press(key):
            already_down = key in self.pressed_keys
            self.pressed_keys.add(key)

            if key == keyboard.Key.f5 and (keyboard.Key.shift in self.pressed_keys or keyboard.Key.shift_r in self.pressed_keys):
                self.after(0, self.trigger_killswitch)
                return

            if self.capturing_hotkey or time.time() < self.ignore_trigger_until:
                return

            # Handle mapped keys immediately. The poller remains a fallback,
            # but a quick release/repress must never be lost between ticks.
            if key == self.current_hotkey and self._keyboard_virtual_key(key) is not None:
                if self._keyboard_hotkey_down:
                    return
                self._keyboard_hotkey_down = True
                self._polled_keyboard_down = True
                if self.hold_hotkey_var.get():
                    self._hold_hotkey_source = "keyboard"
                    self.after(0, self.start_clicking)
                else:
                    self.after(0, self.toggle_clicking)
                return

            if already_down:
                return

            if key == self.current_hotkey:
                self.after(35, self._watch_keyboard_hotkey_release, key)
                if self.hold_hotkey_var.get():
                    self._hold_hotkey_source = "keyboard"
                    self.after(0, self._start_hold_from_hotkey, "keyboard")
                else:
                    self.after(0, self.toggle_clicking)

        def on_key_release(key):
            self.pressed_keys.discard(key)
            if key != self.current_hotkey:
                return
            self._keyboard_hotkey_down = False
            self._polled_keyboard_down = False
            if self.capturing_hotkey or time.time() < self.ignore_trigger_until:
                return
            if self._hold_hotkey_source == "keyboard":
                self.after(0, self._stop_hold_from_hotkey, "keyboard")

        def on_mouse_click(x, y, button, pressed):
            if button != self.current_hotkey:
                return
            if self.capturing_hotkey or time.time() < self.ignore_trigger_until:
                return

            # Generated clicks must not become hotkey edges. If the physical
            # button is actually down, however, this is a real user edge even
            # when it overlaps a generated click.
            physical_down = self._physical_mouse_down(button)
            if self.is_synthetic_click:
                if self._mouse_hotkey_down:
                    if not pressed:
                        self.after(10, self._reconcile_mouse_hotkey)
                    return
                if not physical_down:
                    return
            elif not physical_down and time.monotonic() - self._last_synthetic_mouse_click < 0.08:
                # pynput can deliver generated events just after the worker
                # clears is_synthetic_click; keep those from becoming toggles.
                if not pressed:
                    self.after(10, self._reconcile_mouse_hotkey)
                return

            if pressed:
                if self._mouse_hotkey_down:
                    return
                self._mouse_hotkey_down = True
                self._polled_mouse_down = True
                self._polled_mouse_button = button
                if self.hold_hotkey_var.get():
                    self._hold_hotkey_source = "mouse"
                    self.after(0, self._start_hold_from_hotkey, "mouse")
                else:
                    self.after(0, self.toggle_clicking)
            else:
                self._mouse_hotkey_down = False
                self._polled_mouse_down = False
                if self._hold_hotkey_source == "mouse":
                    self.after(0, self._stop_hold_from_hotkey, "mouse")

        self.kbd_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
        self.mouse_listener = mouse.Listener(on_click=on_mouse_click)
        self.kbd_listener.start()
        self.mouse_listener.start()

    def _listen_for_new_hotkey(self):
        if self.capturing_hotkey:
            return

        self._hold_hotkey_source = None
        self._keyboard_hotkey_down = False
        self._mouse_hotkey_down = False
        self._polled_keyboard_down = False
        self._polled_hotkey_key = None
        self._polled_mouse_down = False
        self._polled_mouse_button = None
        self.pressed_keys.clear()
        self.stop_clicking()
        self.capturing_hotkey = True
        self.hotkey_btn.configure(text="[PRESS INPUT]", text_color="#8C7A6B")

        def stop_capture():
            if self.cap_kbd:
                self.cap_kbd.stop()
            if self.cap_mouse:
                self.cap_mouse.stop()

            self.ignore_trigger_until = time.time() + 0.4
            self.capturing_hotkey = False

        def on_key_capture(key):
            self.current_hotkey = key
            try:
                self.hotkey_name = key.char.upper()
            except AttributeError:
                self.hotkey_name = key.name.upper()

            accent_col = THEMES[self.current_theme_name]["accent"]
            self.after(0, lambda: self.hotkey_btn.configure(text=f"[{self.hotkey_name}]", text_color=accent_col))
            stop_capture()
            return False

        def on_mouse_capture(x, y, button, pressed):
            if pressed:
                self.current_hotkey = button
                self.hotkey_name = format_button_name(button)
                accent_col = THEMES[self.current_theme_name]["accent"]
                self.after(0, lambda: self.hotkey_btn.configure(text=f"[{self.hotkey_name}]", text_color=accent_col))
                stop_capture()
                return False

        self.cap_kbd = keyboard.Listener(on_press=on_key_capture)
        self.cap_mouse = mouse.Listener(on_click=on_mouse_capture)
        self.cap_kbd.start()
        self.cap_mouse.start()

    def _on_close(self):
        if self._hotkey_poll_after is not None:
            try:
                self.after_cancel(self._hotkey_poll_after)
            except tk.TclError:
                pass
            self._hotkey_poll_after = None
        with self._click_state_lock:
            self.clicking = False
            self._stop_event.set()
        self._hold_hotkey_source = None
        self._keyboard_hotkey_down = False
        self._mouse_hotkey_down = False
        if self.kbd_listener:
            self.kbd_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    app = DarkClicker()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[!] Application interrupted by user (Ctrl+C). Exiting cleanly...")
        app._on_close()
