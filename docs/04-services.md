# 04 · 服务栈：监控 / 内网穿透 / 代理

以下都是在**手机系统内部**跑的服务，全部用 systemd 或 Docker 托管，开机自启。

## 1. Beszel 监控

```bash
docker run -d --name beszel --restart unless-stopped \
  -p 8090:8090 -v /opt/beszel/data:/beszel_data \
  henrygd/beszel:latest

# 浏览器打开 http://<手机IP>:8090 → 建管理员 → 添加系统 → 拿到 KEY/TOKEN
docker run -d --name beszel-agent --restart unless-stopped \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /:/host:ro \
  -e LISTEN=45876 \
  -e "KEY=<公钥>" \
  -e "TOKEN=<令牌>" \
  -e "HUB_URL=http://<手机IP>:8090" \
  henrygd/beszel-agent:latest
```

验证：`docker logs beszel-agent | grep WebSocket` 应出现 `WebSocket connected`。

## 2. Cloudflare 隧道（内网穿透）

```bash
# 安装（国内建议用代理下载 deb）
curl -fL -o /tmp/cf.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
dpkg -i /tmp/cf.deb

# 快速隧道（临时域名）
cp systemd/cloudflared-quick.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now cloudflared-quick
journalctl -u cloudflared-quick | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1
```

固定域名（需自己的域名托管在 Cloudflare）：

```bash
cloudflared tunnel login
cloudflared tunnel create beszel
cloudflared tunnel route dns beszel beszel.example.com
cat > /etc/cloudflared/config.yml <<EOF
tunnel: beszel
credentials-file: /root/.cloudflared/<UUID>.json
ingress:
  - hostname: beszel.example.com
    service: http://127.0.0.1:8090
  - service: http_status:404
EOF
systemctl enable --now cloudflared   # 用官方 service
```

## 3. mihomo 全局代理（TUN）

```bash
# 安装二进制（deb 或 gz，arm64）
dpkg -i mihomo-linux-arm64-*.deb

# 配置：Clash 订阅 + TUN
mkdir -p /etc/mihomo
cp your-sub.yaml /etc/mihomo/config.yaml
cat >> /etc/mihomo/config.yaml <<EOF

tun:
  enable: true
  stack: gvisor
  auto-route: true
  auto-detect-interface: true
  dns-hijack:
    - any:53
geodata-mode: true
geo-auto-update: false
EOF

# 离线地理库（避免被墙卡启动）
cp Country.mmdb geoip.dat geosite.dat /etc/mihomo/

cp systemd/mihomo.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now mihomo
```

验证：
```bash
curl -s https://ifconfig.me        # 应为节点出口 IP
curl -s -o /dev/null -w '%{http_code}\n' https://github.com   # 200
```

## 4. WiFi + DHCP

```bash
bash scripts/wifi-connect.sh "SSID" "密码"
```

脚本会：写 `/etc/wpa_supplicant/wpa_supplicant-wlp1s0.conf`（WPA2+PMF）→ 启动 `wpa_supplicant@wlp1s0` →
用 `scripts/dhcp-client.py` 拿地址 → 装 `systemd/wlan-dhcp.service` 保证开机自动获取。

## 5. USB 串口 / 网卡（gadget）

initramfs 阶段自动建立；进入系统后如需重建：

```bash
bash scripts/usb-gadget.sh      # 建 ACM + NCM 并绑 UDC
```

Windows 侧：设备管理器会出现一个串口（COMx，115200）与一张 NCM 网卡。
