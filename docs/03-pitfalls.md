# 03 · 踩坑记录（25 条）

按阶段分组。每条都注明**现象 → 根因 → 解法**，按此顺序可以直接复用。

---

## A. 引导链（ABL）

### 1. 只有 boot header v2 能刷入启动
- 现象：刷 v3 镜像后黑屏、无 USB，长按电源才能回 fastboot。
- 根因：本机 ABL 只接受 v2。
- 解法：用 `tools/pack_v2_dtb.py` 打包，且 **DTB 段放在 v2 扩展头之后**。

### 2. `fastboot boot` 每个 bootloader 会话只能用一次
- 现象：第二次报 `Failed to load/authenticate boot image: Load Error`。
- 解法：调试时先 `fastboot flash boot_a`，不要指望连续 `fastboot boot`。

### 3. vendor_boot 有完整性校验，一个字节都不能改
- 现象：哪怕只在原厂 vendor_boot 的 DTB 里加一个 compatible 字符串，也直接挂起。
- 解法：**vendor_boot / dtbo 保持原厂**，所有定制塞进 boot.img 的 DTB 段。

### 4. DTB 缺 `__symbols__` → ABL 静默回 fastboot
- 现象：没有任何报错，直接进 fastboot，极难排查。
- 根因：原厂 dtbo 的 29 个 fragment 全部按 phandle 引用，ABL 需要 237 个 label 解析。
- 解法：
  ```bash
  python3 tools/extract_dtbo_labels.py stock/dtbo.img > labels.txt
  python3 tools/gen_stubs.py labels.txt > thyme-dtbo-stubs.dtsi   # include 进 dts
  # Makefile: DTC_FLAGS_<dtb基名> := -@   （不是 DTC_FLAGS_dtb！）
  ```
  验证：`python3 tools/fdt_symbols.py x.dtb | wc -l` ≥ 237。

### 5. 大 initramfs 不启动
- 现象：initramfs > 20MB 时设备不引导。
- 解法：initramfs 控制在 1MB 级；rootfs 用网络传（USB NCM 实测 ~30MB/s）。

### 6. cmdline 里 `root=` 会让内核跳过 initramfs 的 `/init`
- 现象：系统"启动"了但没串口、没网卡，等于失联。
- 解法：**不要在 cmdline 写 root=**，让 initramfs 自己 mount + switch_root。

### 7. `switch_root` 只能 PID 1 执行
- 现象：`switch_root` 只打印 usage，不切换。
- 解法：让 init（PID 1）做；或 init `exec sh` 落到救援 shell 后（此时 PID 已变成 shell）再切。

### 8. rootfs 缺 `/dev /proc /sys /run` 目录
- 现象：`mount --move /dev /root/dev` 失败 → 掉进救援 shell。
- 根因：tar 解包的 rootfs 常缺这些空目录；且在 mount 之前 mkdir 会被挂载覆盖。
- 解法：**先 mount 根，再 mkdir `/root/{dev,proc,sys,run}`**，最后 move。

### 9. 项目 rootfs 的 fstab 是原机 UUID、machine-id 为空
- 现象：systemd 起不来；`journalctl` 显示 `No journal files were found`（查不到原因）。
- 解法：
  ```bash
  sed -i 's|^UUID=.*|/dev/sda35|' /mnt/etc/fstab
  echo $(tr -d '-' < /proc/sys/kernel/random/uuid) > /mnt/etc/machine-id
  ```

---

## B. 存储

### 10. 6.4GB 镜像 ≠ 225GB 分区
- 现象：`df -h` 只有 6.4G。
- 根因：写进去的是一个 6.4GB 的文件系统镜像，后面空间未分配。
- 解法：`resize2fs /dev/sda35`（ext4 在线扩容）→ 222G。

---

## C. USB gadget / 串口

### 11. ACM 与 NCM 必须在同一个 config 里建好再写 UDC
- 现象：先绑 UDC 再加功能 → 没有 ttyGS0；重复写 UDC → 已有 ACM shell 被杀掉。

### 12. Windows 侧 COM 编号会变
- 每次重新枚举可能 COM3→COM4→COM5→COM6，脚本要动态取端口名。

### 13. Windows 上多个 169.254/16 网卡导致路由错乱
- 现象：手机→电脑通（能拉大文件），电脑→手机 `Destination host unreachable`（包发去了 Wi-Fi Direct 网卡）。
- 解法：别去改电脑网络；改手机侧跑 DHCP 让 Windows 拿到 172.16.42.x，或干脆走 WiFi + 局域网 IP。

### 14. UFW 默认拦截 usb0
- 现象：sshd 在监听但连不上。`ufw disable` 后仍需解决第 13 条。

### 15. 手机 rootfs 里没有 dhclient / dhcpcd / nmcli
- 解法：用 `scripts/dhcp-client.py`（极简 DHCP 客户端，纯 Python），或 `scripts/usb-dhcp.py`（给 Windows 发地址）。

---

## D. WiFi

### 16. ath11k 在 7.2 内核下 probe 失败
- 现象：`ath11k_pci ... failed to power up :-110`。
- 结论：WiFi/GPU 必须用 6.18 项目内核。

### 17. WPA 四次握手失败 `WRONG_KEY`
- 原因 1：密码抄错（末尾多了一个 `*`）。
- 原因 2：AP 要求 **PMF(802.11w)**，缺 `ieee80211w=1` 会一直 `reason=2` 断开。
- 可用配置：
  ```ini
  network={
    ssid="YourSSID"
    psk="YourPass"
    key_mgmt=WPA-PSK
    ieee80211w=1
  }
  ```
- 另外：`iw dev wlp1s0 set power_save off` 可减少掉线。

---

## E. 网络环境（被墙）

### 18. Docker Hub 不可达
- 解法：`/etc/docker/daemon.json` → `registry-mirrors: ["https://docker.m.daocloud.io"]`。

### 19. GitHub 下载被截断
- `ghproxy.net` 可用但会截断（19.7MB 只下到 3.9MB，`dpkg` 报 `unexpected end of file`）。
- 最稳：**用电脑代理下载再 scp**：
  ```bash
  curl --proxy http://127.0.0.1:7897 -L -o mihomo.deb <url>
  scp mihomo.deb root@phone:/tmp/
  ```

### 20. mihomo 启动卡死（在下载 geoip）
- 死循环：没代理→下不了 geo→起不来代理。
- 解法：拷 `Country.mmdb` / `geoip.dat` / `geosite.dat` 到 `/etc/mihomo/`，并加：
  ```yaml
  geodata-mode: true
  geo-auto-update: false
  ```

### 21. cloudflared quick tunnel 在 TUN 下掉线
- 现象：`Connection terminated` / `no more connections active and exiting`。
- 解法：systemd 托管 + `--protocol http2`（QUIC 在 TUN 下不稳）。

---

## F. 监控（Beszel）

### 22. agent 的两种连接方式
- Hub 主动连 agent（45876）在本机环境没成功。
- 改用 **agent 主动 WebSocket**：`HUB_URL=http://<hub-ip>:8090` + `TOKEN=<令牌>`，一次成功。
- 重启会残留同名旧容器，记得 `docker ps -a` 清理。

---

## G. 工具链

### 23. PowerShell → WSL → SSH 的引号地狱
- 多层嵌套的 heredoc / 引号会被吞掉，表现为"命令没执行/输出错乱"。
- 解法：**本地写脚本 → scp 过去 → `bash /tmp/x.sh`**。

### 24. 串口粘贴长命令会被截断
- 解法：base64 分块 + here-doc；或直接改走 SSH。

### 25. Python `http.server` 在本机主机名非 UTF8 时崩溃
- 现象：`UnicodeDecodeError` in `socket.getfqdn`。
- 解法：`socket.getfqdn = lambda *a, **k: "localhost"`。
