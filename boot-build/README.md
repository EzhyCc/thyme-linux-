# boot-build

构建能被 Xiaomi 10S（thyme）ABL 接受的启动镜像。

## 组成

| 文件 | 作用 |
|---|---|
| `make-boot-image.sh` | 打包 v2 boot（kernel + initramfs + DTB） |
| `initramfs/init` | initramfs 的 init：建 gadget → 挂 rootfs → switch_root |
| `../tools/pack_v2_dtb.py` | 纯 Python 打包器（无依赖） |
| `../tools/bootimg2.py` | 解析/校验 boot.img |

## 为什么必须是 v2

本机 ABL 实测：**v3 刷入必挂**，v2 正常。
v2 的扩展头（1660 字节）后面才放 DTB，这也是为什么 DTB 段必须由打包器写入，而不是塞进 vendor_boot。

## 为什么 DTB 要有 `__symbols__`

原厂 `dtbo` 有 29 个 overlay fragment，全部按 phandle 引用主 DTB 的节点；
ABL 在合并前会查 DTB 的 `__symbols__`（本项目实测需要 237 个 label）。
缺了不会报错，而是**静默回到 fastboot**。

生成方式（见 `docs/02-build-boot-image.md`）：

```bash
python3 ../tools/extract_dtbo_labels.py stock/dtbo.img > labels.txt
python3 ../tools/gen_stubs.py labels.txt > thyme-dtbo-stubs.dtsi
# dts 里 #include "thyme-dtbo-stubs.dtsi"，Makefile 里 DTC_FLAGS_<dtb基名> := -@
```

## initramfs 的要求

见 `init` 顶部注释；要点：
- 基础挂载失败 → 立刻救援 shell
- ACM+NCM 一次建好再写 UDC（重复写会踢掉已有串口）
- **mount 根之后再 mkdir `/root/{dev,proc,sys,run}`**
- 四个 `mount --move` 任一失败 → 不 switch_root，进救援
