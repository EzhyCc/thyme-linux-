# 02 · 构建 boot 镜像

本机 ABL 的硬性要求（缺一不可）：

1. **boot header v2**（不是 v3）
2. boot.img 内自带 **DTB 段**，且 DTB 含完整 `__symbols__`
3. `vendor_boot` 保持原厂
4. 不要用 `root=` 让内核跳过 initramfs

## 1. 准备三样东西

| 文件 | 来源 | 说明 |
|---|---|---|
| `Image.gz` | 自行编译或社区内核 | 6.18 `sm8250`，建议 gzip 压缩 |
| `initramfs.cpio.gz` | `boot-build/initramfs/` | 我们的 init：建 gadget → 挂 rootfs → switch_root |
| `thyme-dtb-abl.dtb` | 见下 | 必须带 `__symbols__` |

## 2. 生成带 symbols 的 DTB

```bash
# 关键：DTC_FLAGS 的名字是「dtb 文件名去掉 .dtb」
# 例如 sm8250-xiaomi-thyme.dtb → DTC_FLAGS_sm8250-xiaomi-thyme := -@
echo 'DTC_FLAGS_sm8250-xiaomi-thyme := -@' >> arch/arm64/boot/dts/qcom/Makefile

# dtbo 的 fragment 用的是 phandle 引用，ABL 需要这些 label 存在
python3 tools/extract_dtbo_labels.py stock/dtbo.img > /tmp/labels.txt
python3 tools/gen_stubs.py /tmp/labels.txt > arch/arm64/boot/dts/qcom/thyme-dtbo-stubs.dtsi
# 然后在 thyme.dts 里：#include "thyme-dtbo-stubs.dtsi"

make ARCH=arm64 qcom/sm8250-xiaomi-thyme.dtb
python3 tools/fdt_symbols.py arch/arm64/boot/dts/qcom/sm8250-xiaomi-thyme.dtb | wc -l
# 期望 ≥ 237（本项目实测 873）
```

## 3. 打包

```bash
bash boot-build/make-boot-image.sh \
  --kernel    kernel/Image.gz \
  --initramfs boot-build/initramfs.cpio.gz \
  --dtb       dts/thyme-dtb-abl.dtb \
  --cmdline   "console=ttyMSM0,115200n8 console=tty0 loglevel=7 ignore_loglevel clk_ignore_unused pd_ignore_unused regulator_ignore_unused" \
  --out       out/boot-thyme.img
```

脚本内部调用 `tools/pack_v2_dtb.py`（纯 Python，无依赖）。

## 4. 验证（重要）

```bash
python3 tools/bootimg2.py info out/boot-thyme.img
# header_version 必须是 2
# 确认 kernel_size / ramdisk_size / dtb_size 与输入一致

python3 tools/bootimg2.py extract out/boot-thyme.img /tmp/x
python3 tools/fdt_symbols.py /tmp/x/dtb.bin | wc -l
```

## 5. initramfs 的 init 必须做到

1. 挂 devtmpfs / proc / sysfs / **tmpfs /run**
2. 建 USB gadget（**ACM + NCM 在同一个 config**，最后一次性写 UDC）
3. 等 `/dev/ttyGS0` 出现
4. 等 `/dev/sda35`（最多 30 秒）
5. mount 根 → **再 mkdir `/root/dev /root/proc /root/sys /root/run`**
6. `mount --move` 四个挂载点，任一失败 → 救援 shell
7. `exec switch_root /root /sbin/init`

参考实现：`boot-build/initramfs/init`。
