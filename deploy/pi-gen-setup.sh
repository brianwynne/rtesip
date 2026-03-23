#!/bin/bash -e
# Runs inside chroot on the Pi image during CI build
useradd -r -s /usr/sbin/nologin -d /opt/rtesip rtesip 2>/dev/null || true
mkdir -p /etc/rtesip /var/lib/rtesip /var/log/rtesip /run/rtesip
chown rtesip:rtesip /var/lib/rtesip /var/log/rtesip /run/rtesip
echo "d /run/rtesip 0755 rtesip rtesip -" > /etc/tmpfiles.d/rtesip.conf
python3 -m venv /opt/rtesip/.venv
/opt/rtesip/.venv/bin/pip install --upgrade pip
/opt/rtesip/.venv/bin/pip install -r /opt/rtesip/requirements.txt
chown -R root:root /opt/rtesip
chown rtesip:rtesip /var/lib/rtesip /var/log/rtesip
systemctl enable rtesip.service
echo "sip-reporter" > /etc/hostname
sed -i "s/raspberrypi/sip-reporter/g" /etc/hosts
systemctl disable dphys-swapfile 2>/dev/null || true
systemctl disable bluetooth 2>/dev/null || true
systemctl disable triggerhappy 2>/dev/null || true
