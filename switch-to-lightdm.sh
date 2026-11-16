#!/bin/sh
# Makes LightDM the login manager again from the next boot (run as root)
set -e
systemctl disable sddm.service
systemctl enable lightdm.service
echo "LightDM starts at the next boot"
