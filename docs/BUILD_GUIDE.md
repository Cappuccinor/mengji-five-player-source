# 构建指南 / Build guide

## 公开快照的前置条件 / Snapshot prerequisites

此仓库只发布源码、工具和数据。自动构建流程依赖完整的私有地图素材，因此发布快照不会开箱即用。

This repository publishes only source, tools, and data. The automated build depends on the complete source-map assets, so the public snapshot is not turnkey.

构建前需自行准备：

Before building, provide:

1. Windows 环境（脚本调用 `vendor/pjass.exe` 与 `vendor/stormlib/x64/StormLib.dll`）。
2. Python 3。
3. 与 `tools/archive.py` 中固定 SHA-256 **完全匹配**的授权源地图，放在 `inputs/original.w3x`。任意其他地图都会被基线检查拒绝。
4. `data/tool-manifest.json` 列出的工具、头文件和 Python 模块；按其许可证和来源合法取得，放入对应的 `vendor/` 路径，并核对清单中的摘要。

1. Windows (the scripts call `vendor/pjass.exe` and `vendor/stormlib/x64/StormLib.dll`).
2. Python 3.
3. An authorized source map whose SHA-256 **exactly matches** the baseline pinned in `tools/archive.py`, placed at `inputs/original.w3x`. Other maps are rejected by the baseline check.
4. The tools, headers, and Python module listed in `data/tool-manifest.json`, lawfully obtained under their respective licenses, placed under the declared `vendor/` paths, and checked against the manifest hashes.

不要把这些私有或第三方资源提交到公开仓库。

Do not commit these private or third-party resources to the public repository.

## 执行顺序 / Workflow

从仓库根目录执行。所有派生内容写入本地忽略目录 `scratch/` 和 `dist/`：

Run from the repository root. Derived files are written to local ignored `scratch/` and `dist/` directories:

```powershell
python tools/prepare_workspace.py --source inputs/original.w3x
python -m unittest discover -s tests -v
python tools/build.py --source inputs/original.w3x --out dist
```

`prepare_workspace.py` 会核对源地图摘要，再提取编译/分析所需成员；若已有派生文件内容不同会停止，不会覆盖。`build.py` 会建立独立候选文件、运行 JASS 静态检查和归档资源校验，并输出 JSON 报告。脚本的存在不表示缺失工具已打包，也不表示本页面流程已经实际运行。

`prepare_workspace.py` checks the map hash before extracting members required for compilation/analysis. It stops if an existing derived file differs instead of overwriting it. `build.py` creates an independent candidate, runs JASS static checks and archive resource checks, and writes a JSON report. The presence of these scripts does not mean their missing tools are packaged or that this workflow has been run here.

## 结果解释 / Interpreting results

- 离线候选不是最终地图发布，也不证明地图可玩。
- 构建报告会明确记录未验证的运行时、可玩性和多人同步状态。
- Warcraft III/KK 客户端运行、UI 实际效果、英雄/技能升级、等待事件以及五客户端同步需要独立的目标环境验收。
- 某些测试读取 `scratch/baseline/`、`scratch/extracted/` 和 `vendor/`；未完成前置步骤时，测试失败或跳过的结果不能用作客户端验收证据。

- An offline candidate is not a final map release and does not prove playability.
- The build report explicitly records runtime, playability, and multiplayer synchronization as unverified.
- Warcraft III/KK runtime behavior, in-game UI, hero/skill upgrades, timed events, and synchronization across five clients require separate validation in the target environment.
- Some tests read `scratch/baseline/`, `scratch/extracted/`, and `vendor/`. Failures or skips caused by missing prerequisites are not client acceptance evidence.

## 相关文件 / Related files

- `tools/build.py`：候选构建入口 / candidate build entry point
- `tools/prepare_workspace.py`：基线校验和素材提取 / baseline check and extraction
- `tools/verify_release.py`：离线归档检查 / offline archive checks
- `data/tool-manifest.json`：外部工具清单与 SHA-256 / external tool manifest and SHA-256 values
