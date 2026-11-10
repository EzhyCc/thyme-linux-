# rootfs

本仓库**不提供** rootfs 二进制（版权与体积原因）。你需要自己准备一份 ARM64 Debian/Armbian rootfs。

## 两种可用形式

| 形式 | 优点 | 缺点 |
|---|---|---|
| raw ext4 镜像（`.img`） | 一条 `wget` 直写，最稳 | 需要预先做好镜像（例如 6.4G） |
| tar 包（`.tar.gz`） | 体积小 | 需要先有已格式化的 ext4，且解包慢 |

## 写入流程（在 initramfs 救援 shell 里）

```bash
# 电脑侧
python -m http.server 8000        # 在 rootfs 所在目录

# 手机侧
bash rootfs/install-rootfs.sh http://192.168.1.x:8000/rootfs.img
```

脚本会：写盘 → sync → 挂载校验 → `resize2fs` 扩到整块 UFS → 修 `machine-id`。

## 首次启动前必须确认

1. `/etc/fstab` 的根不是原机器的 UUID（改成 `/dev/sda35`）
2. `/etc/machine-id` 非空（空的会导致 journald 不写日志，排错极其困难）
3. rootfs 里包含 `systemd`（`/usr/lib/systemd/systemd` 或 `/sbin/init`）
