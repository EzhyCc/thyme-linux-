# NOTICE —— 第三方来源与致谢

本项目站在很多人的肩膀上。以下列出思路、工具与组件的来源。

## 思路与方案来源

- **[umi-linux](https://github.com/misaka-link/umi-linux)** —— 小米 10（`umi`）刷 Debian 的完整方案。
  本项目的 boot 构建思路（v2 boot + 保留原厂 dtbo/vendor_boot、headless 设计、USB NCM+ACM）来自该项目。
  本项目只移植到 `thyme` 并补充踩坑记录，**未复制其镜像或 rootfs**。

## 内核与 rootfs

- **内核**：Armbian `linux-current`（SM8250）社区构建。
- **rootfs**：Debian 13 / Armbian（用户自行准备，本仓库不含任何 rootfs 二进制）。

## 工具

- **avbtool / boot image 格式**：AOSP `system/tools/mkbootimg`（Apache-2.0）格式说明。
- **DTB 处理**：`dtc`（Device Tree Compiler，GPL-2.0）与 `libfdt`。
- **mihomo**：<https://github.com/MetaCubeX/mihomo>（GPL-3.0）
- **cloudflared**：Cloudflare Tunnel 客户端（Apache-2.0）
- **Beszel**：<https://github.com/henrygd/beszel>（MIT）

## 法律声明

- 本仓库**不包含**任何小米、高通、第三方的闭源固件、内核二进制、厂商 rootfs 或密钥。
- 使用者必须自行从自己拥有的设备/官方固件中获取 `boot.img`、`dtbo.img`、`vendor_boot.img` 等文件。
- 设备保修、数据安全、法规合规由使用者自行负责。
