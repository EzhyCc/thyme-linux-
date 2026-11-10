# 05 · 排错手册

## 刷完 boot 后直接进 fastboot

按可能性排序：

1. **DTB 缺 `__symbols__`**（最常见）
   ```bash
   python3 tools/fdt_symbols.py out/dtb.bin | wc -l    # 应 ≥ 237
   ```
2. boot header 不是 v2 → `python3 tools/bootimg2.py info out.img`
3. 改了 `vendor_boot` / `dtbo` → 刷回原厂
4. DTB 与内核版本不匹配（例如用 7.2 的 DTB 配 6.18 内核）→ 用同一内核树编出的 DTB

## 能进系统但没串口 / 没网卡

- cmdline 里有 `root=` → 内核跳过 initramfs 的 `/init`。移除 `root=`。
- gadget 没建成功：`ls /sys/class/udc` 为空则无 UDC；检查内核 DWC3 是否 probe。
- 排查顺序：`dmesg | grep -iE 'dwc3|gadget|udc'`。

## 串口有输出但切根失败（掉进救援 shell）

- rootfs 里缺 `/dev /proc /sys /run` → **mount 之后再 mkdir**。
- fstab UUID 不对 → 改成 `/dev/sda35`。
- `switch_root` 打印 usage → 调用者不是 PID 1。

## systemd 起不来 / 没有任何日志

```bash
# 从 initramfs 挂上 rootfs 后检查
mount /dev/sda35 /mnt
cat /mnt/etc/fstab        # 是否是 /dev/sda35
cat /mnt/etc/machine-id   # 是否为空
ls /mnt/sbin/init /mnt/lib/systemd/systemd
```

## SSH 连不上（但 ping 通）

1. `ss -ltnp | grep :22` 是否监听
2. `ufw status` 是否拦截（`ufw disable`）
3. 走的是 USB 网卡？Windows 多张 169.254 网卡会选错出口 → 改用 WiFi IP
4. `journalctl -u ssh -n 50` 看密钥/权限问题

## WiFi 连不上

```bash
wpa_supplicant -i wlp1s0 -c /etc/wpa_supplicant/wpa_supplicant-wlp1s0.conf -f /tmp/wpa.log &
tail -f /tmp/wpa.log
```

| 日志 | 含义 | 处理 |
|---|---|---|
| `WRONG_KEY` | 密码错 / 需要 PMF | 核对密码；加 `ieee80211w=1` |
| `reason=2 DISCONNECTED` | 通常 PMF 或密钥协商失败 | 同上 |
| `failed to power up -110` | 内核/固件不支持（7.2 内核） | 换 6.18 内核 |
| 连上但没 IP | 缺 DHCP 客户端 | `scripts/dhcp-client.py` |

## Docker 拉不动镜像

```bash
cat /etc/docker/daemon.json     # 需要 registry-mirrors
systemctl restart docker
docker pull hello-world         # 验证
```

## mihomo 起不来

```bash
journalctl -u mihomo -n 50 | tail -30
```
出现 `Can't find MMDB, start download` 且卡住 → 见 [03-pitfalls.md](03-pitfalls.md) 第 20 条。

## 需要回滚到 Android

```bash
fastboot --set-active=b          # 切回 B 槽
# 注意：userdata 已被改成 Debian，Android 侧数据不保
```
若之前改过 `vbmeta_a`（`--disable-verification`），先刷回原厂 `vbmeta_a`。
