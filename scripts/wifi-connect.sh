#!/usr/bin/env bash
# wifi-connect.sh —— 连接 WiFi（WPA2 + PMF），并获取 DHCP 地址
#
# 用法: wifi-connect.sh "<SSID>" "<密码>" [接口, 默认 wlp1s0]
set -euo pipefail

SSID="${1:?用法: wifi-connect.sh <SSID> <密码> [接口]}"
PASS="${2:?用法: wifi-connect.sh <SSID> <密码> [接口]}"
IFACE="${3:-wlp1s0}"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /etc/wpa_supplicant
cat > "/etc/wpa_supplicant/wpa_supplicant-${IFACE}.conf" <<EOF
network={
	ssid="${SSID}"
	psk="${PASS}"
	key_mgmt=WPA-PSK
	ieee80211w=1
}
EOF

systemctl disable --now "wpa_supplicant@${IFACE}.service" 2>/dev/null || true
pkill -f "wpa_supplicant -i ${IFACE}" 2>/dev/null || true
sleep 1

ip link set "$IFACE" up
iw dev "$IFACE" set power_save off 2>/dev/null || true
wpa_supplicant -B -i "$IFACE" -c "/etc/wpa_supplicant/wpa_supplicant-${IFACE}.conf" -f /tmp/wpa.log
sleep 8

if iw dev "$IFACE" link | grep -q "Not connected"; then
	echo "未连上，日志："
	tail -20 /tmp/wpa.log
	exit 1
fi

echo "[*] 已连上 $(iw dev "$IFACE" link | awk '/SSID/{print $2}')"

# 拿 DHCP（手机通常没有 dhclient）
install -m 755 "$HERE/dhcp-client.py" /usr/local/bin/dhcp-client.py
cp "$HERE/../systemd/wlan-dhcp.service" /etc/systemd/system/wlan-dhcp.service
systemctl daemon-reload
systemctl enable "wpa_supplicant@${IFACE}.service" wlan-dhcp.service
systemctl start wlan-dhcp.service || true

python3 /usr/local/bin/dhcp-client.py || true
ip -br addr show "$IFACE"
