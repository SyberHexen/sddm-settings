#!/bin/sh
# Installs SDDM Settings (Login Window) and the SDDM settings in
# sddm.conf.d (run as root).  Does not change which login manager starts;
# see switch-to-sddm.sh.  Install a theme separately, for example
# https://github.com/SyberHexen/sddm-theme-slickgreeter, and choose it in the app.
set -e
here=$(dirname "$(readlink -f "$0")")

install -d /etc/sddm.conf.d
# Not over the settings made in SDDM Settings
[ -f /etc/sddm.conf.d/10-sddm-settings.conf ] ||
    install -m 644 "$here/sddm.conf.d/10-sddm-settings.conf" /etc/sddm.conf.d/
echo "Installed /etc/sddm.conf.d/10-sddm-settings.conf"

install -Dm755 "$here/sddm-settings/sddm-settings.py" /usr/lib/sddm-settings/sddm-settings.py
install -Dm755 "$here/sddm-settings/sddm-settings" /usr/bin/sddm-settings
install -Dm644 "$here/sddm-settings/sddm-settings.desktop" /usr/share/applications/sddm-settings.desktop
install -Dm644 "$here/sddm-settings/org.x.sddm-settings.policy" /usr/share/polkit-1/actions/org.x.sddm-settings.policy
echo "Installed SDDM Settings (Login Window)"

# KWin's settings for a Wayland login window (numlock, primary monitor, HDR)
# from the saved ones
/usr/lib/sddm-settings/sddm-settings.py --sync
