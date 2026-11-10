---
name: "craft-anything"
description: "Inspects websites, apps, games and files with the open-source Craft Anything engine (clean-room, 320 tools). Invoke when the user wants to study how software is built, analyze a file/binary, or rebuild a target."
---

# Craft Anything

开源净室逆向与重建引擎（storytold/craft-anything，MIT/Apache-2.0）。已安装 v0.6.0 到本工作区，通过 CLI 使用。

## 位置

- CLI 入口：`/workspace/tools/craft-anything/craft-anything-cli`（符号链接）
- 实际二进制：`/workspace/tools/craft-anything/squashfs-root/usr/bin/craft-anything-cli`
- 原始 AppImage：`/workspace/tools/craft-anything/craft-anything-0.6.0-linux-x86_64.AppImage`（沙箱无 FUSE，已解包使用）

## 常用命令

```bash
CA=/workspace/tools/craft-anything/craft-anything-cli

$CA doctor                 # 检查安装、引擎、AI 后端与 MCP 自检
$CA capabilities           # 本安装可用工具集与引擎清单
$CA commands               # 列出全部 320 个工具（每个工具也是子命令）
$CA triage <file>          # 打开文件并做初步分析
$CA report                 # 从调查证据生成 Markdown/HTML 报告
$CA mcp                    # 以 MCP server 方式在 stdio 上提供全部工具
$CA rebuild <target> "<需求>"   # 研究目标并让编程代理重建（需 AI 后端）
```

- 每个工具都是子命令：`$CA <tool> --help` 查看参数。
- 全局输出格式：`--format json|jsonl|md|text|csv|tsv`（放在工具名之前）。
- `--project <folder>` 把证据/日志存入项目目录；`--deep` 单次开启深度模式（可读取目标内部代码），默认净室模式只看外部可见内容。

## 当前环境限制（doctor 结果）

- **AI 后端未配置**：`rebuild`、`chat` 需要编程代理（首选 Claude Code，也支持 ACP 系代理）。配置方式：`$CA ai detect` 后 `$CA ai add`。
- **无 Chromium**：网站实时研究（浏览器截图/测量）暂不可用；静态文件分析不受影响。
- 可选引擎未装：Ghidra、adb、JADX、Apktool、Frida、mitmproxy、binwalk、unblob、ilspycmd、tshark、rizin、vineflower。
- 已可用引擎：内置反汇编/反编译器、GDB、LLDB、Java、objdump。MCP 自检通过（30 个核心工具）。

## 使用原则

- 仅用于用户拥有或有权检查的软件；不绕过 DRM、登录或反作弊。
- 净室模式为默认；涉及读取目标内部内容时先与用户确认再加 `--deep`。
- 工具执行外部命令前需用户批准（除非用户明确加 `--allow-run`）。
