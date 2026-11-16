#!/bin/sh
# Makes SDDM the login manager from the next boot (run as root)
set -e
systemctl disable lightdm.service
systemctl enable sddm.service
echo "SDDM starts at the next boot. Back to LightDM: switch-to-lightdm.sh"
