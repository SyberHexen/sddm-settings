#!/usr/bin/python3
#
# SDDM Settings: the login window's settings, laid out like Linux Mint's
# lightdm-settings, for SDDM and its Slick theme.  Each change is saved as
# it is made: SDDM's settings to CONF_PATH, the theme's to its
# theme.conf.user (which SDDM reads over the theme's theme.conf).
#
# The window and its settings widgets follow Linux Mint's lightdm-settings
# (Copyright (C) Linux Mint, GPL-3.0), which this is modelled on.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3 as published
# by the Free Software Foundation.

import configparser
import glob
import json
import os
import pwd
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

# Overridable for trying the window out without root
CONF_PATH = os.environ.get("SDDM_SETTINGS_CONF",
                           "/etc/sddm.conf.d/10-sddm-settings.conf")
THEMES_DIR = os.environ.get("SDDM_SETTINGS_THEMES", "/usr/share/sddm/themes")
SESSION_DIRS = ["/usr/share/wayland-sessions", "/usr/share/xsessions"]
KWIN_COMMAND = ("kwin_wayland --drm --no-lockscreen --no-global-shortcuts "
                "--locale1")


def _(text):
    return text


# ---- Storage ----------------------------------------------------------------

class IniFile:
    """An INI file whose keys are saved as soon as they are set"""

    def __init__(self, path, defaults_paths=()):
        self.path = path
        self.defaults = configparser.ConfigParser(interpolation=None)
        self.defaults.optionxform = str
        self.defaults.read(list(defaults_paths))
        self.parser = configparser.ConfigParser(interpolation=None)
        self.parser.optionxform = str
        self.parser.read(path)

    def get(self, section, key, default=""):
        for parser in (self.parser, self.defaults):
            if parser.has_option(section, key):
                return parser.get(section, key)
        return default

    def get_bool(self, section, key, default=False):
        value = self.get(section, key, None)
        if value is None or value == "":
            return default
        return value.strip().lower() in ("true", "on", "yes", "1")

    def set(self, section, key, value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            f.write("# Written by SDDM Settings\n")
            self.parser.write(f, space_around_delimiters=False)
        os.chmod(tmp, 0o644)
        os.replace(tmp, self.path)


class Store:
    """SDDM's settings and the current theme's"""

    def __init__(self):
        system = sorted(glob.glob("/usr/lib/sddm/sddm.conf.d/*.conf"))
        others = [p for p in sorted(glob.glob("/etc/sddm.conf.d/*.conf"))
                  if p != CONF_PATH]
        self.sddm = IniFile(CONF_PATH, system + others)
        self.load_theme()

    def load_theme(self):
        self.theme_name = self.sddm.get("Theme", "Current", "")
        self.theme_dir = os.path.join(THEMES_DIR, self.theme_name)
        self.theme = IniFile(os.path.join(self.theme_dir, "theme.conf.user"),
                             [os.path.join(self.theme_dir, "theme.conf")])


# ---- Widgets (laid out as lightdm-settings lays them out) --------------------

class SettingsPage(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.set_margin_start(80)
        self.set_margin_end(80)
        self.set_margin_top(15)
        self.set_margin_bottom(15)

    def add_section(self, title=None):
        section = SettingsSection(title)
        self.pack_start(section, False, False, 0)
        return section


class SettingsSection(Gtk.Box):
    def __init__(self, title=None):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=10)
        if title:
            label = Gtk.Label(xalign=0)
            label.set_markup("<b>%s</b>" % GLib.markup_escape_text(title))
            self.add(label)
        self.frame = Gtk.Frame()
        self.frame.set_shadow_type(Gtk.ShadowType.IN)
        self.frame.get_style_context().add_class("view")
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.frame.add(self.box)
        self.add(self.frame)
        self.need_separator = False

    def add_row(self, row):
        if self.need_separator:
            self.box.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.add(row)
        self.box.add(list_box)
        self.need_separator = True
        return row


class SettingsRow(Gtk.ListBoxRow):
    def __init__(self, label, widget, tooltip=None):
        Gtk.ListBoxRow.__init__(self)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        hbox.set_border_width(5)
        hbox.set_margin_start(20)
        hbox.set_margin_end(20)
        self.label = Gtk.Label(label=label, xalign=0)
        self.label.set_line_wrap(True)
        hbox.pack_start(self.label, True, True, 0)
        widget.set_valign(Gtk.Align.CENTER)
        hbox.pack_end(widget, False, False, 0)
        self.add(hbox)
        if tooltip:
            self.set_tooltip_text(tooltip)


def make_switch(get, set_):
    switch = Gtk.Switch()
    switch.set_active(get())
    switch.connect("notify::active", lambda w, p: set_(w.get_active()))
    return switch


def make_combo(options, get, set_, size_group=None):
    """options: [(value, label)]"""
    combo = Gtk.ComboBoxText()
    current = get()
    ids = [value for value, label in options]
    for value, label in options:
        combo.append(value, label)
    if current not in ids and current != "":
        combo.append(current, current)
    combo.set_active_id(current if current != "" else (ids[0] if ids else None))
    combo.connect("changed", lambda w: set_(w.get_active_id()))
    if size_group:
        size_group.add_widget(combo)
    return combo


def make_entry(get, set_, width=20):
    entry = Gtk.Entry()
    entry.set_width_chars(width)
    entry.set_text(get())
    entry.connect("changed", lambda w: set_(w.get_text()))
    return entry


def make_spin(get, set_, minimum, maximum, step=1):
    spin = Gtk.SpinButton.new_with_range(minimum, maximum, step)
    spin.set_value(get())
    spin.connect("value-changed", lambda w: set_(int(w.get_value())))
    return spin


class PictureChooser(Gtk.Box):
    """A picture with a preview, chosen in a file dialog; can be cleared"""

    def __init__(self, get, set_):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.set_ = set_
        self.button = Gtk.Button()
        self.image = Gtk.Image()
        self.button.add(self.image)
        self.button.connect("clicked", self.on_choose)
        clear = Gtk.Button.new_from_icon_name("edit-clear-symbolic",
                                              Gtk.IconSize.BUTTON)
        clear.set_tooltip_text(_("No picture"))
        clear.connect("clicked", lambda w: self.choose(""))
        self.pack_start(self.button, False, False, 0)
        self.pack_start(clear, False, False, 0)
        self.show_picture(get())

    def show_picture(self, path):
        pixbuf = None
        if path and os.path.exists(path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 128, 72)
            except GLib.Error:
                pixbuf = None
        if pixbuf:
            self.image.set_from_pixbuf(pixbuf)
        else:
            self.image.set_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
        self.button.set_tooltip_text(path or _("No picture"))

    def choose(self, path):
        self.show_picture(path)
        self.set_(path)

    def on_choose(self, button):
        dialog = Gtk.FileChooserDialog(title=_("Choose a picture"),
                                       transient_for=self.get_toplevel(),
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL,
                           _("Open"), Gtk.ResponseType.ACCEPT)
        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("Pictures"))
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        if os.path.isdir("/usr/share/backgrounds"):
            dialog.set_current_folder("/usr/share/backgrounds")
        preview = Gtk.Image()
        dialog.set_preview_widget(preview)

        def update_preview(chooser):
            path = chooser.get_preview_filename()
            try:
                preview.set_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_size(path, 256, 256))
                chooser.set_preview_widget_active(True)
            except (GLib.Error, TypeError):
                chooser.set_preview_widget_active(False)

        dialog.connect("update-preview", update_preview)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.choose(dialog.get_filename())
        dialog.destroy()


# ---- Lists of things to choose from -----------------------------------------

def get_sddm_themes():
    themes = []
    for path in sorted(glob.glob(os.path.join(THEMES_DIR, "*", "metadata.desktop"))):
        meta = configparser.ConfigParser(interpolation=None)
        meta.optionxform = str
        try:
            meta.read(path)
            name = meta.get("SddmGreeterTheme", "Name", fallback=None)
        except configparser.Error:
            name = None
        directory = os.path.basename(os.path.dirname(path))
        themes.append((directory, name or directory))
    return themes


def get_cursor_themes():
    names = set()
    for base in ["/usr/share/icons", "/usr/local/share/icons"]:
        for path in glob.glob(os.path.join(base, "*", "cursors")):
            names.add(os.path.basename(os.path.dirname(path)))
    return [(name, name) for name in sorted(names, key=str.lower)]


def get_sessions():
    sessions = []
    for directory in SESSION_DIRS:
        wayland = "wayland" in directory
        for path in sorted(glob.glob(os.path.join(directory, "*.desktop"))):
            info = configparser.ConfigParser(interpolation=None)
            info.optionxform = str
            try:
                info.read(path)
                name = info.get("Desktop Entry", "Name", fallback=None)
                hidden = info.get("Desktop Entry", "NoDisplay", fallback="false")
            except configparser.Error:
                continue
            if hidden.lower() == "true":
                continue
            label = name or os.path.basename(path)
            if not wayland and "x11" not in label.lower():
                label = "%s (X11)" % label
            sessions.append((os.path.basename(path), label))
    return sessions


def get_users():
    users = []
    for entry in pwd.getpwall():
        if entry.pw_uid < 1000 or entry.pw_uid >= 60000:
            continue
        if entry.pw_shell.endswith(("nologin", "false")):
            continue
        real_name = entry.pw_gecos.split(",")[0]
        users.append((entry.pw_name, "%s (%s)" % (real_name, entry.pw_name)
                      if real_name else entry.pw_name))
    return users


def edid_monitor_name(edid):
    """The monitor name descriptor of an EDID"""
    for offset in (54, 72, 90, 108):
        block = edid[offset:offset + 18]
        if len(block) == 18 and block[0:3] == b"\0\0\0" and block[3] == 0xfc:
            return block[5:18].split(b"\n")[0].decode("ascii", "replace").strip()
    return ""


def get_monitors():
    """Connected monitors, by connector name as KWin and Muffin name them"""
    monitors = []
    for path in sorted(glob.glob("/sys/class/drm/card*-*")):
        try:
            with open(os.path.join(path, "status")) as f:
                if f.read().strip() != "connected":
                    continue
            with open(os.path.join(path, "edid"), "rb") as f:
                name = edid_monitor_name(f.read())
        except OSError:
            continue
        connector = os.path.basename(path).split("-", 1)[1]
        monitors.append((connector, "%s (%s)" % (connector, name) if name else connector))
    return monitors


# A login window on Wayland runs in KWin, which sets numlock from its own
# settings in the sddm user's home rather than from SDDM's Numlock
SDDM_HOME = os.environ.get("SDDM_SETTINGS_SDDM_HOME", "/var/lib/sddm")


KWIN_OUTPUTS = os.path.join(SDDM_HOME, ".config", "kwinoutputconfig.json")


def load_kwin_outputs():
    """KWin's monitor settings for the login window: (whole file, outputs,
    setups), or None if KWin has not written them yet"""
    try:
        with open(KWIN_OUTPUTS) as f:
            config = json.load(f)
    except (OSError, ValueError) as e:
        print("No KWin monitor settings yet (%s)" % e)
        return None
    outputs, setups = [], []
    for entry in config if isinstance(config, list) else []:
        if entry.get("name") == "outputs":
            outputs = entry.get("data", [])
        elif entry.get("name") == "setups":
            setups = entry.get("data", [])
    return config, outputs, setups


def save_kwin_outputs(config):
    tmp = KWIN_OUTPUTS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(config, f, indent=4)
    os.chmod(tmp, 0o644)
    if os.getuid() == 0:
        sddm = pwd.getpwnam("sddm")
        os.chown(tmp, sddm.pw_uid, sddm.pw_gid)
    os.replace(tmp, KWIN_OUTPUTS)


def edid_supports_hdr(edid):
    """Whether an EDID's CTA-861 HDR static metadata block offers PQ or HLG"""
    for block in range(1, len(edid) // 128):
        ext = edid[block * 128:(block + 1) * 128]
        if len(ext) < 4 or ext[0] != 0x02:
            continue
        end = ext[2] if 4 <= ext[2] <= 127 else 4
        i = 4
        while i < end:
            tag, length = ext[i] >> 5, ext[i] & 0x1f
            # Extended tag 6: HDR static metadata; its first byte the EOTFs
            if tag == 7 and length >= 2 and ext[i + 1] == 0x06:
                return bool(ext[i + 2] & 0x0c)  # bit 2 PQ, bit 3 HLG
            i += 1 + length
    return False


def get_hdr_monitors():
    """Connected monitors whose EDID offers HDR, by connector name"""
    names = []
    for path in sorted(glob.glob("/sys/class/drm/card*-*")):
        try:
            with open(os.path.join(path, "status")) as f:
                if f.read().strip() != "connected":
                    continue
            with open(os.path.join(path, "edid"), "rb") as f:
                if edid_supports_hdr(f.read()):
                    names.append(os.path.basename(path).split("-", 1)[1])
        except OSError:
            continue
    return names


def get_kwin_hdr():
    loaded = load_kwin_outputs()
    if not loaded:
        return False
    hdr = set(get_hdr_monitors())
    return any(o.get("highDynamicRange") for o in loaded[1]
               if o.get("connectorName") in hdr)


def get_session_user_home(store=None):
    """The home of the user whose desktop settings to follow: the one who
    opened this (through pkexec or sudo), else the automatic login user"""
    for var in ("PKEXEC_UID", "SUDO_UID"):
        uid = os.environ.get(var)
        if uid and uid.isdigit():
            try:
                return pwd.getpwuid(int(uid)).pw_dir
            except KeyError:
                pass
    if store:
        user = store.sddm.get("Autologin", "User", "")
        if user:
            try:
                return pwd.getpwnam(user).pw_dir
            except KeyError:
                pass
    return None


def get_muffin_hdr_luminance(home):
    """{connector: (peak, average, minimum)} in cd/m2, for the monitors in
    the BT.2100 color mode in the desktop's monitor settings, as Muffin puts
    them in its HDR metadata: the peak the user set for peak and average,
    0.005 minimum; without one, 1000 and 400 (when the EDID gives none)"""
    import xml.etree.ElementTree as ET
    result = {}
    if not home:
        return result
    path = os.path.join(home, ".config", "cinnamon-monitors-wayland.xml")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return result
    # The first configuration is the one in use (Muffin writes it first)
    configuration = root.find("configuration")
    if configuration is None:
        return result
    for monitor in configuration.iter("monitor"):
        connector = monitor.findtext("monitorspec/connector")
        if not connector or monitor.findtext("colormode") != "bt2100":
            continue
        try:
            peak = int(monitor.findtext("hdrpeakluminance") or 0)
        except ValueError:
            peak = 0
        result[connector] = (peak, peak, 0.005) if peak > 0 else (1000, 400, 0.005)
    return result


def set_kwin_hdr(on, store=None):
    """Runs the login window's HDR monitors in HDR (as KWin's own display
    settings do: HDR and wide colour gamut), so they stay in HDR from the
    login window into an HDR session instead of switching to SDR and back"""
    loaded = load_kwin_outputs()
    if not loaded:
        return
    config, outputs, setups = loaded
    hdr = set(get_hdr_monitors())
    # The desktop's HDR brightness, so the login window sends the display
    # the same HDR metadata and it need not re-sync between them
    luminance = get_muffin_hdr_luminance(get_session_user_home(store)) if on else {}
    changed = False
    for output in outputs:
        connector = output.get("connectorName")
        want = bool(on) and connector in hdr
        for key in ("highDynamicRange", "wideColorGamut"):
            if output.get(key) != want:
                output[key] = want
                changed = True
        if want and connector in luminance:
            peak, average, minimum = luminance[connector]
            for key, value in (("maxPeakBrightnessOverride", peak),
                               ("maxAverageBrightnessOverride", average),
                               ("minBrightnessOverride", minimum)):
                if output.get(key) != value:
                    output[key] = value
                    changed = True
    if changed:
        save_kwin_outputs(config)
        print("HDR in the login window %s" % ("on: " + ", ".join(sorted(hdr)) if on else "off"))


def set_kwin_primary(connector):
    """Makes @connector KWin's primary monitor in the login window: where the
    mouse starts and SDDM's primary screen.  KWin keeps its monitor setups
    in kwinoutputconfig.json (written when it first sees them); priority 0
    is the primary.  "auto" leaves KWin's choice."""
    if not connector or connector == "auto":
        return
    loaded = load_kwin_outputs()
    if not loaded:
        return
    config, outputs, setups = loaded

    changed = False
    for setup in setups:
        members = setup.get("outputs", [])
        chosen = [m for m in members
                  if 0 <= m.get("outputIndex", -1) < len(outputs) and
                  outputs[m["outputIndex"]].get("connectorName") == connector and
                  m.get("enabled", True)]
        if not chosen:
            continue
        # The chosen one first, the others in their order after it
        others = sorted((m for m in members if m is not chosen[0] and m.get("enabled", True)),
                        key=lambda m: m.get("priority", 0))
        for priority, member in enumerate([chosen[0]] + others):
            if member.get("priority") != priority:
                member["priority"] = priority
                changed = True

    if not changed:
        return
    save_kwin_outputs(config)
    print("%s is now the login window's primary monitor" % connector)


def sync_kwin(store):
    """KWin's settings for the login window from the saved ones (for the
    installer)"""
    set_kwin_numlock(store.sddm.get("General", "Numlock", "none") == "on")
    set_kwin_primary(store.theme.get("General", "monitor", "auto"))
    # Refresh the HDR brightness from the desktop's, if HDR is on
    if get_kwin_hdr():
        set_kwin_hdr(True, store)


def set_kwin_numlock(on):
    path = os.path.join(SDDM_HOME, ".config", "kcminputrc")
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read(path)
    if not config.has_section("Keyboard"):
        config.add_section("Keyboard")
    # 0: turn on, 1: turn off, 2: leave as it is
    config.set("Keyboard", "NumLock", "0" if on else "2")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            config.write(f, space_around_delimiters=False)
        if os.getuid() == 0:
            sddm = pwd.getpwnam("sddm")
            os.chown(os.path.dirname(path), sddm.pw_uid, sddm.pw_gid)
            os.chown(path, sddm.pw_uid, sddm.pw_gid)
    except (OSError, KeyError) as e:
        print("Could not set the numlock of the login window: %s" % e)


def get_screen_fonts():
    context = Gtk.Label().get_pango_context()
    return sorted({family.get_name() for family in context.list_families()},
                  key=str.lower)


# ---- The window ------------------------------------------------------------

class Application(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self, application_id="org.x.sddm-settings",
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        windows = self.get_windows()
        if windows:
            windows[0].present()
            return
        self.store = Store()
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title(_("Login Window (SDDM)"))
        self.window.set_icon_name("preferences-system-login")
        self.window.set_default_size(800, 640)
        self.build()
        self.window.show_all()

    def build(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(main_box)

        toolbar = Gtk.Toolbar()
        toolbar.get_style_context().add_class("primary-toolbar")
        main_box.pack_start(toolbar, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(150)
        main_box.pack_start(self.stack, True, True, 0)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.stack)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.set_homogeneous(True)
        holder = Gtk.Box()
        holder.set_border_width(1)
        holder.pack_start(switcher, True, True, 0)
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(True)
        tool_item.get_style_context().add_class("raised")
        tool_item.add(holder)
        toolbar.insert(tool_item, 0)

        self.build_pages()

    def build_pages(self):
        for child in self.stack.get_children():
            self.stack.remove(child)
        self.add_appearance_page()
        self.add_users_page()
        self.add_settings_page()
        self.stack.show_all()

    def add_page(self, name, title):
        page = SettingsPage()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(page)
        self.stack.add_titled(scrolled, name, title)
        return page

    # Shortcuts for the two files
    def sddm_get(self, section, key, default=""):
        return lambda: self.store.sddm.get(section, key, default)

    def sddm_set(self, section, key):
        return lambda value: self.store.sddm.set(section, key, value)

    def theme_get(self, key, default=""):
        return lambda: self.store.theme.get("General", key, default)

    def theme_get_bool(self, key, default=True):
        return lambda: self.store.theme.get_bool("General", key, default)

    def theme_set(self, key):
        return lambda value: self.store.theme.set(
            "General", key, ("true" if value else "false")
            if isinstance(value, bool) else value)

    def is_slick(self):
        return os.path.exists(os.path.join(self.store.theme_dir, "Main.qml")) \
            and self.store.theme_name == "slick"

    def add_appearance_page(self):
        page = self.add_page("appearance", _("Appearance"))
        sizes = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        section = page.add_section(_("General"))

        def set_theme(value):
            self.store.sddm.set("Theme", "Current", value)
            self.store.load_theme()
            # The theme's own settings change with it
            GLib.idle_add(self.rebuild_keep_page)

        section.add_row(SettingsRow(
            _("Theme"),
            make_combo(get_sddm_themes(), self.sddm_get("Theme", "Current"),
                       set_theme, sizes),
            _("The look of the login window")))

        if not self.is_slick():
            label = Gtk.Label(label=_("The other appearance settings are for the Slick theme."))
            label.set_line_wrap(True)
            page.pack_start(label, False, False, 0)
        else:
            section.add_row(SettingsRow(
                _("Alignment"),
                make_combo([("left", _("Left")), ("center", _("Center")),
                            ("right", _("Right"))],
                           self.theme_get("contentAlign", "left"),
                           self.theme_set("contentAlign"), sizes),
                _("Alignment of the login box")))

            section = page.add_section(_("Background"))
            section.add_row(SettingsRow(
                _("Background"),
                PictureChooser(self.theme_get("background"),
                               self.theme_set("background")),
                _("Note: Don't select a background from your home directory "
                  "if it's encrypted or if its permissions are restricted: "
                  "the login window can't read it.")))

            section.add_row(SettingsRow(
                _("Picture aspect"),
                make_combo([("zoom", _("Zoom")), ("scaled", _("Scaled")),
                            ("stretched", _("Stretched")),
                            ("centered", _("Centered"))],
                           self.theme_get("backgroundFill", "zoom"),
                           self.theme_set("backgroundFill"), sizes),
                _("Zoom fills the screen and crops the picture; Scaled shows "
                  "all of it, with the background color around it; Stretched "
                  "fills the screen and distorts it; Centered shows it at its "
                  "own size.")))

            color = Gtk.ColorButton()
            rgba = Gdk.RGBA()
            rgba.parse(self.store.theme.get("General", "backgroundColor", "#000000"))
            color.set_rgba(rgba)

            def color_set(button):
                c = button.get_rgba()
                self.store.theme.set("General", "backgroundColor", "#%02x%02x%02x" % (
                    round(c.red * 255), round(c.green * 255), round(c.blue * 255)))

            color.connect("color-set", color_set)
            section.add_row(SettingsRow(_("Background color"), color,
                                        _("Shown when there is no background picture")))
            section.add_row(SettingsRow(
                _("Stretch background across multiple monitors"),
                make_switch(self.theme_get_bool("stretchBackgroundAcrossMonitors"),
                            self.theme_set("stretchBackgroundAcrossMonitors"))))

            section = page.add_section(_("Text"))
            fonts = [(name, name) for name in get_screen_fonts()]
            section.add_row(SettingsRow(
                _("Font"),
                make_combo(fonts, self.theme_get("font", "Ubuntu"),
                           self.theme_set("font"), sizes)))

        section = page.add_section(_("Mouse pointer"))
        section.add_row(SettingsRow(
            _("Mouse pointer"),
            make_combo(get_cursor_themes(), self.sddm_get("Theme", "CursorTheme"),
                       self.set_cursor_theme, sizes)))
        section.add_row(SettingsRow(
            _("Mouse pointer size"),
            make_spin(lambda: int(self.store.sddm.get("Theme", "CursorSize", "24") or 24),
                      self.set_cursor_size, 8, 96)))

    # The Wayland login window takes the pointer from its environment too
    def set_cursor_theme(self, value):
        self.store.sddm.set("Theme", "CursorTheme", value)
        self.update_greeter_environment()

    def set_cursor_size(self, value):
        self.store.sddm.set("Theme", "CursorSize", value)
        self.update_greeter_environment()

    def update_greeter_environment(self):
        sddm = self.store.sddm
        env = []
        if sddm.get("General", "DisplayServer", "x11") == "wayland":
            env.append("QT_WAYLAND_SHELL_INTEGRATION=layer-shell")
        theme = sddm.get("Theme", "CursorTheme", "")
        size = sddm.get("Theme", "CursorSize", "")
        if theme:
            env.append("XCURSOR_THEME=%s" % theme)
        if size:
            env.append("XCURSOR_SIZE=%s" % size)
        sddm.set("General", "GreeterEnvironment", ",".join(env))

    def add_users_page(self):
        page = self.add_page("users", _("Users"))
        sizes = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        if self.is_slick():
            section = page.add_section(_("User list"))
            section.add_row(SettingsRow(
                _("Allow manual login"),
                make_switch(self.theme_get_bool("showManualLogin"),
                            self.theme_set("showManualLogin")),
                _("Add an option in the login window to enter a username.")))
            section.add_row(SettingsRow(
                _("Hide the user list"),
                make_switch(lambda: not self.store.theme.get_bool("General", "showUserList", True),
                            lambda v: self.store.theme.set("General", "showUserList",
                                                           "false" if v else "true")),
                _("Hide the list of users in the login window.")))
            section.add_row(SettingsRow(
                _("Users not to list"),
                make_entry(self.theme_get("hiddenUsers"), self.theme_set("hiddenUsers")),
                _("User names, separated by commas")))

        section = page.add_section(_("Automatic login"))
        users = [("", _("None"))] + get_users()
        section.add_row(SettingsRow(
            _("Username"),
            make_combo(users, self.sddm_get("Autologin", "User"),
                       self.sddm_set("Autologin", "User"), sizes),
            _("Log this user in at boot without asking for the password. "
              "Warning: Automatic login will fail if the user's home "
              "directory is encrypted.")))
        section.add_row(SettingsRow(
            _("Session"),
            make_combo(get_sessions(), self.sddm_get("Autologin", "Session"),
                       self.sddm_set("Autologin", "Session"), sizes)))
        section.add_row(SettingsRow(
            _("Log in again automatically after logging out"),
            make_switch(lambda: self.store.sddm.get_bool("Autologin", "Relogin", False),
                        lambda v: self.store.sddm.set("Autologin", "Relogin",
                                                      "true" if v else "false")),
            _("Off: the login window is shown after logging out.")))

        label = Gtk.Label(label="* " + _("These settings take effect at the next boot."))
        label.set_xalign(0)
        page.pack_start(label, False, False, 0)

    def add_settings_page(self):
        page = self.add_page("settings", _("Settings"))
        sizes = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)

        section = page.add_section(_("Settings"))
        section.add_row(SettingsRow(
            _("Activate numlock"),
            make_switch(lambda: self.store.sddm.get("General", "Numlock", "none") == "on",
                        self.set_numlock),
            _("Activate numlock in the login window.")))

        def set_display_server(value):
            self.store.sddm.set("General", "DisplayServer", value)
            if value == "wayland" and not self.store.sddm.parser.has_option(
                    "Wayland", "CompositorCommand"):
                self.store.sddm.set("Wayland", "CompositorCommand", KWIN_COMMAND)
            self.update_greeter_environment()

        section.add_row(SettingsRow(
            _("Login window runs on") + " *",
            make_combo([("wayland", _("Wayland")), ("x11", _("X11"))],
                       self.sddm_get("General", "DisplayServer", "x11"),
                       set_display_server, sizes),
            _("The display server of the login window itself. Sessions use "
              "their own, whichever this is.")))

        if get_hdr_monitors():
            section.add_row(SettingsRow(
                _("HDR"),
                make_switch(get_kwin_hdr, lambda on: set_kwin_hdr(on, self.store)),
                _("Show the login window in HDR on monitors that support it "
                  "(%s), so they do not switch to SDR and back around an HDR "
                  "session. Needs the login window on Wayland.")
                % ", ".join(get_hdr_monitors())))

        if self.is_slick():
            section.add_row(SettingsRow(
                _("Monitor"),
                make_combo([("auto", _("Auto"))] + get_monitors(),
                           self.theme_get("monitor", "auto"),
                           self.set_monitor, sizes),
                _("Choose which monitor shows the login box, or 'Auto' for "
                  "the primary one.")))
            section.add_row(SettingsRow(
                _("HiDPI support"),
                make_combo([("auto", _("Auto")), ("1", _("Disable")),
                            ("1.5", "150%"), ("2", _("Enable"))],
                           self.theme_get("scale", "auto"), self.theme_set("scale"),
                           sizes),
                _("Support for high pixel density and Retina displays.")))

            section = page.add_section(_("Panel indicators"))
            section.add_row(SettingsRow(
                _("Hostname"),
                make_switch(self.theme_get_bool("showHostname"),
                            self.theme_set("showHostname")),
                _("Show the computer hostname in the panel.")))
            section.add_row(SettingsRow(
                _("Quit menu"),
                make_switch(self.theme_get_bool("showPower"),
                            self.theme_set("showPower")),
                _("Show the quit menu in the panel.")))
            section.add_row(SettingsRow(
                _("Clock"),
                make_switch(self.theme_get_bool("showClock"),
                            self.theme_set("showClock")),
                _("Show a clock in the panel.")))
            section.add_row(SettingsRow(
                _("Clock format"),
                make_entry(self.theme_get("clockFormat", "HH:mm"),
                           self.theme_set("clockFormat"), 12),
                _("Qt time format, for example HH:mm (24 hour) or h:mm AP "
                  "(12 hour).")))

        label = Gtk.Label(label="* " + _("These settings take effect at the next boot."))
        label.set_xalign(0)
        page.pack_start(label, False, False, 0)

    def set_monitor(self, connector):
        self.store.theme.set("General", "monitor", connector)
        set_kwin_primary(connector)

    def set_numlock(self, on):
        self.store.sddm.set("General", "Numlock", "on" if on else "none")
        set_kwin_numlock(on)

    def rebuild_keep_page(self):
        name = self.stack.get_visible_child_name()
        self.build_pages()
        if name:
            self.stack.set_visible_child_name(name)
        return False


if __name__ == "__main__":
    if os.getuid() != 0 and "SDDM_SETTINGS_CONF" not in os.environ:
        print("sddm-settings needs to be run as root.")
        sys.exit(1)
    if "--sync" in sys.argv:
        sync_kwin(Store())
        sys.exit(0)
    app = Application()
    sys.exit(app.run(sys.argv))
