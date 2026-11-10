# thyme-linux —— 把小米 10S 变成 Debian 服务器

> 目标设备：**Xiaomi Mi 10S**（代号 `thyme`，型号 `M2102J2SC`，SoC `SM8250-AC`）
> 结果：运行 **Debian 13 (trixie)**，可用 WiFi / SSH / Docker，**222 GB** 存储，屏幕保持熄灭（headless）。

本项目是把 `umi-linux`（小米 10 / umi）的整套思路移植到 **thyme** 上，并记录了完整踩坑过程。
所有脚本只做两件事：**打包 boot 镜像**、**准备 rootfs**。不含任何原厂闭源镜像。

---

## 本项目与 umi-linux 的关系

本项目的**方案、思路与流程全部来自 [misaka-link/umi-linux](https://github.com/misaka-link/umi-linux)**
（小米 10 / `umi` 的 Debian 移植项目），我们做的是**移植到 thyme 并补充踩坑记录**：

| 环节 | 来源 |
|---|---|
| 保留原厂 `vendor_boot` / `dtbo`、只改 `boot` 分区的思路 | umi-linux |
| boot 镜像结构（v2 header + 内核 + initramfs + DTB 段） | umi-linux |
| **headless 设计**（主动给面板断电，不做显示） | umi-linux |
| **USB NCM + ACM** 双通道（网卡 + 串口 root shell） | umi-linux |
| rootfs 直接铺满 `userdata` + `resize2fs` | umi-linux |
| 默认账号 `root` / 密码策略、`armbian` 账号需锁定 | umi-linux 文档 |
| **thyme 的设备树、DTB symbols、v2 打包参数、25 条踩坑** | 本项目新增 |

> 如果你在 `umi`（小米 10）上操作，**请直接使用上游项目**，它的发布包更完整（含内核、rootfs、GPU/WiFi 已调通）。
> 本项目面向 **`thyme`（小米 10S）**，并且**不附带**任何内核/rootfs 二进制。

上游项目：<https://github.com/misaka-link/umi-linux>

---

## 能力矩阵

| 能力 | 状态 | 说明 |
|---|---|---|
| 启动 Debian 13 | ✅ | 项目内核 6.18.52 + 我们的 initramfs |
| UFS 全盘可用 | ✅ | `resize2fs` 后 222 GB |
| USB 串口（ttyGS0 → COMx） | ✅ | initramfs 内建 ACM+NCM gadget |
| USB 网卡（NCM） | ✅ | 172.16.42.1 + 内置 DHCP |
| WiFi | ✅ | `ath11k`（QCA6390），WPA2 + PMF |
| SSH | ✅ | 局域网 / WiFi 均可 |
| Docker | ✅ | 已配国内镜像加速 |
| 视频编解码 `/dev/video*` | ✅ | Venus |
| GPU `/dev/dri` | ❌ | 需把 thyme DTB 的 GPU/显示节点按项目 DTS 移植 |
| 屏幕显示 | ❌（设计如此） | 面板主动断电，headless |
| 充电上限 / 电池策略 | ✅ | 项目自带 `battery-charge-limit` |

---

## 快速开始

前置条件：
- BootLoader 已解锁
- 手上有**原厂固件包**（只要里面的 `boot.img` / `dtbo.img` 用于比对与回滚）
- 会 `fastboot`

```bash
# 0) 备份（强烈建议）
fastboot getvar all > getvar-all.txt
# modemst1/modemst2/fsg/fsc/persist 永远不要 erase

# 1) 构建 boot 镜像（需要 Linux 环境，见 docs/02-build-boot-image.md）
bash boot-build/make-boot-image.sh \
  --kernel   kernel/Image.gz \
  --initramfs initramfs.cpio.gz \
  --dtb      dts/thyme-dtb-abl.dtb \
  --out      out/boot-thyme.img

# 2) 刷入（只动 boot_a）
fastboot flash boot_a out/boot-thyme.img
fastboot --set-active=a
fastboot reboot

# 3) 首次启动会落到串口 shell，按 docs/01-quick-start.md 安装 rootfs
```

**首次启动预期**：电脑出现一个 USB 串口（COMx，115200）和一张 NCM 网卡；串口里是 root shell。

---

## 仓库结构

```
boot-build/     打包 v2 boot 镜像、initramfs 的 init、DTB symbols 处理
rootfs/         把 rootfs 解包到 userdata 并扩容
scripts/        USB gadget、DHCP 客户端/服务端、WiFi 连接
systemd/        监控 / 隧道 / 代理 的服务单元
tools/          boot.img 解析与重打包、DTB symbols 提取等纯 Python 工具
docs/           快速开始、构建、踩坑、服务、排错
```

---

## 关键事实（血泪版）

1. **只有 boot header v2 能被本机 ABL 接受**；v3 刷进去必挂。
2. **vendor_boot 一个字节都不能改**（改了直接挂起）→ 所有定制放进 boot.img 的 DTB 段。
3. **DTB 必须带 `__symbols__`**（237 个 label），否则 ABL **静默回 fastboot**，没有任何报错。
4. **cmdline 里写 `root=` 会让内核跳过 initramfs 的 `/init`** → 没有 USB gadget → 失联。
5. **`switch_root` 只能 PID 1 执行**，从交互 shell 调只会打印 usage。
6. **rootfs 里要先 mount 再 mkdir `/dev /proc /sys /run`**，否则 `mount --move` 必失败。
7. 项目 rootfs 的 `/etc/fstab` 是**原机器 UUID**、`/etc/machine-id` 为空 → 必须改，否则 systemd 起不来且无日志。

完整 25 条见 [docs/03-pitfalls.md](docs/03-pitfalls.md)。

---

## 免责与许可

- 本项目只包含**我们自己写的脚本与文档**，不包含任何小米/高通闭源二进制、也不包含内核源码或厂商 rootfs。
- 刷机会**清空 userdata**，并可能让设备无法回到 Android。风险自负。
- 代码：**MIT**。第三方组件与思路来源见 [NOTICE.md](NOTICE.md)。

---

## English TL;DR

Port of the [`umi-linux`](https://github.com/misaka-link/umi-linux) approach to **Xiaomi Mi 10S (thyme)**:
build an Android **boot header v2** image (kernel + our initramfs + thyme DTB with `__symbols__`),
flash it to `boot_a` only, unpack a Debian rootfs to `userdata`, then `resize2fs`.
Result: headless Debian 13 server with WiFi, USB serial/Ethernet, Docker.
See `docs/` for the build guide and the 25 pitfalls we hit.
