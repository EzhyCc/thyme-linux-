# 01 · 快速开始：从 Android 到 Debian

> 预计耗时：刷机 20 分钟（不含下载）。破坏性：**userdata 会被清空**。

## 0. 确认三件事

| # | 检查 | 方法 |
|---|---|---|
| 1 | BootLoader 已解锁 | `fastboot getvar unlocked` → `yes` |
| 2 | 手上有原厂固件 | 至少要有 `dtbo.img`、`vendor_boot.img`、`boot.img` 用于比对/回滚 |
| 3 | 平台工具可用 | 用较新的 `fastboot`（旧版有 sparse 截断 bug） |

## 1. 备份不能丢的东西

```bash
fastboot getvar all > getvar-all.txt
# 永远不要 erase/format：
# modemst1 modemst2 fsg fsc persist mdm1m9kefs1 mdm1m9kefs2 mdm1m9kefs3
```

## 2. 刷 boot（只刷 boot_a）

```bash
fastboot flash boot_a out/boot-thyme.img
fastboot --set-active=a
fastboot reboot
```

> **不要动** `vendor_boot_a`、`dtbo_a`、`vbmeta_a`。本方案要求它们保持原厂状态。

**预期现象**（约 40 秒）：
- 电脑出现 **USB 串口**（115200）→ 打开就是 shell
- 电脑出现 **USB 网卡（NCM）** → 手机侧 172.16.42.1
- 屏幕黑（正常，headless）

## 3. 写入 rootfs

拿到串口 shell 后：

```bash
# 3.1 配置 USB 网络，把 rootfs 从电脑拉进来（不需要电脑装任何东西）
ip link set usb0 up
ip addr add 172.16.42.1/24 dev usb0      # initramfs 通常已配好
# 电脑侧开一个 HTTP 服务（Windows: python -m http.server 8000）
wget -O /dev/sda35 http://<电脑IP>:8000/rootfs.img    # 约 6 分钟 / 6.4GB

# 3.2 校验并把分区扩到整块 UFS
sync
mount /dev/sda35 /mnt
head -1 /mnt/etc/os-release        # 应显示 Debian/Armbian
resize2fs /dev/sda35               # → 222 GB（在 chroot 或切根后执行均可）

# 3.3 切根
mount --move /dev  /mnt/dev
mount --move /proc /mnt/proc
mount --move /sys  /mnt/sys
mount --move /run  /mnt/run
exec switch_root /mnt /sbin/init
```

> `switch_root` 必须由 **PID 1** 执行。如果当前 shell 不是 PID 1（多数情况），
> 请使用 `boot-build/initramfs/init` 的方式：让 initramfs 自己挂载并切根。

## 4. 首启必做（4 步）

```bash
# ① 改 root 密码（默认密码是公开的）
passwd

# ② 锁掉第二个 root 钥匙
passwd -l armbian

# ③ 唯一化 SSH 主机密钥
rm -f /etc/ssh/ssh_host_* && ssh-keygen -A && systemctl restart ssh

# ④ 配 WiFi
bash scripts/wifi-connect.sh "你的SSID" "你的密码"
```

## 5. 验收清单

```bash
uname -r                      # 6.18.x-current-sm8250
df -h /                       # 222G
systemctl is-system-running   # running / degraded
ls /dev/video*                # video0/1/10
ip -br addr show wlp1s0       # 192.168.x.x
ssh root@<WiFi-IP>            # 从电脑能连
```

失败项对照 [05-troubleshooting.md](05-troubleshooting.md)。
