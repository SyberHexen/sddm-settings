# sddm-settings

**Login Window (SDDM)**: a settings app for the [SDDM](https://github.com/sddm/sddm)
login manager, laid out like Linux Mint's lightdm-settings, plus SDDM settings and
scripts for running the login screen on Wayland under KWin.

It works with any SDDM theme. With
[sddm-theme-slickgreeter](https://github.com/SyberHexen/sddm-theme-slickgreeter)
selected, it also shows that theme's options.

## What's here

| | |
|---|---|
| `sddm-settings/` | The Login Window (SDDM) app (Python, GTK 3) |
| `sddm.conf.d/10-sddm-settings.conf` | SDDM settings: the login screen on Wayland under KWin |
| `install.sh` | Installs the app and those settings (run as root) |
| `switch-to-sddm.sh`, `switch-to-lightdm.sh` | Choose the login manager for the next boot (run as root) |

## The app

Appearance, Users and Settings pages like lightdm-settings: theme, pointer; automatic
login (user, session, log in again after logging out); numlock, Wayland or X11 login
screen. With the Slick Greeter theme selected, also its background, picture aspect,
colour, font, alignment, monitor, HiDPI, top bar items, clock format, user list and
manual login. It asks for the administrator password (polkit) and saves each change as
it is made, to `/etc/sddm.conf.d/10-sddm-settings.conf` and the theme's
`theme.conf.user`.

A login screen on Wayland runs in KWin, which takes some settings from its own files in
the `sddm` user's home rather than from SDDM's. The app writes those too:

- **Numlock**: `kcminputrc` (SDDM's own `Numlock=on` only works on X11).
- **Monitor**: KWin's primary output in `kwinoutputconfig.json`, so the pointer starts
  on the login box's monitor.
- **HDR**, on monitors whose EDID offers it: HDR and wide colour gamut, with the HDR
  brightness the desktop uses for that monitor (read from Cinnamon/Muffin's
  `cinnamon-monitors-wayland.xml`), so the monitor stays in HDR with the same HDR
  metadata between the login screen and an HDR desktop.

`sddm-settings --sync` (run by `install.sh`) applies the saved numlock, monitor and HDR
settings there again.

## Requirements

- SDDM 0.21
- For the login screen on Wayland: KWin (`kwin_wayland`) and `layer-shell-qt`
- Python 3 with PyGObject, GTK 3, polkit

Written and tested on Arch Linux with Cinnamon on Wayland (SDDM 0.21, KWin 6.8).

## Install

```sh
sudo ./install.sh            # the app and SDDM's settings
sudo ./switch-to-sddm.sh     # SDDM from the next boot
```

Install a theme too, for example
[sddm-theme-slickgreeter](https://github.com/SyberHexen/sddm-theme-slickgreeter), and
choose it in the app (Appearance page). `install.sh` doesn't change which login
manager starts, and it keeps an existing `/etc/sddm.conf.d/10-sddm-settings.conf`.
Automatic login is left for you to set, on the Users page.

To go back: `sudo ./switch-to-lightdm.sh` (or your previous display manager's
`systemctl enable`), then reboot. If the login screen doesn't come up, switch to a text
console (Ctrl+Alt+F3) and run it from there.

## Known issues

- **KWin 6.8 can crash as the login screen starts** when the mouse moves while it
  starts (`InputRedirection::syncTabletWithMouse`), leaving no login screen. Fixed in
  [this KWin branch](https://github.com/SyberHexen/kwin/tree/6.8-sddm-fixes).
- **KWin sends no HDR brightness metadata** for monitors whose EDID has none, even with
  the overrides set. Also fixed in that branch; without it the HDR switch still works,
  but the monitor may re-sync at the handover.

## Credits and licence

An unofficial project, not affiliated with Linux Mint or the Cinnamon project. The
app's window and widgets are modelled on Linux Mint's lightdm-settings (GPL-3.0).

Licensed under the GNU GPL version 3 (GPL-3.0-only, see `LICENSE`).
