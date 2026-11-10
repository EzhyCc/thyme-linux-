# tools

纯 Python，无第三方依赖（仅标准库）。用于解析/打包 boot.img 与处理 DTB。

| 工具 | 作用 |
|---|---|
| `bootimg2.py` | 解析/提取/校验 boot.img（v0–v4、vendor_boot、dtbo），`info` / `extract` 子命令 |
| `pack_v2_dtb.py` | 生成带 DTB 段的 **v2** boot.img（本机唯一可用的格式） |
| `fdt_symbols.py` | 列出 DTB 的 `__symbols__` label（ABL 需要 ≥237） |
| `extract_dtbo_labels.py` | 从原厂 `dtbo.img` 里提取所有 overlay 引用的 label |
| `gen_stubs.py` | 根据 label 列表生成 `*-stubs.dtsi`（补齐 ABL 需要的节点） |
| `dtbo_targets.py` | 分析 dtbo 的 fragment target（phandle/path） |
| `split_dtbo.py` | 拆分 dtbo.img 内嵌的多个 DTB |

## 常用命令

```bash
# 看 boot.img 结构
python3 tools/bootimg2.py info boot.img

# 提取各段
python3 tools/bootimg2.py extract boot.img out/

# DTB symbols 数量（判断为什么回 fastboot）
python3 tools/fdt_symbols.py out/dtb.bin | wc -l

# 从原厂 dtbo 提取 label
python3 tools/extract_dtbo_labels.py stock/dtbo.img
```
