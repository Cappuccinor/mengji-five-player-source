# 梦迹沙河2 · 五人地图源码 / Mengji Shahe 2 · Five-player map source

**Warcraft III 自定义地图的 JASS 游戏逻辑与离线构建工具链。**

**JASS gameplay source and offline build tooling for a Warcraft III custom map.**

本仓库是从私有开发分支 `feat/five-player`（源提交 `c34e8c4`，2026-10-18）整理的脱敏源码快照。它适合阅读、审查和继续开发地图逻辑；**这是源码项目，不是可直接游玩的地图发行包**。

This sanitized source snapshot comes from private branch `feat/five-player` (source revision `c34e8c4`, 2026-10-18). It is intended for studying, reviewing, and continuing the map logic. **It is a source project, not a ready-to-play map release.**

## 项目做什么 / Project overview

项目围绕《梦迹沙河2》五人地图开发，包含 JASS 玩法/UI 源码、以 Python 编写的分阶段资源与脚本处理工具，以及英雄、地图布局、平台调用、免费内容和阶段基线等 JSON 数据。脚本将改动集中在声明的成员与阶段中，并对地图归档中的不透明资源做校验。

The project develops the five-player Mengji Shahe 2 map. It includes JASS gameplay/UI source, Python tools for staged script and archive processing, and JSON data for heroes, map layout, platform calls, free content, and stage baselines. The tooling applies changes to declared members and stages, with checks for opaque archive resources.

## 源码地图 / Source map

| 路径 | 职责 |
|---|---|
| `src/` | JASS 游戏逻辑：玩家与英雄选择、名册/UI、对战、免费内容、进度、胜负与布局相关模块 / JASS gameplay modules for player/hero selection, roster/UI, combat, free content, progress, endgame, and layout |
| `tools/` | Python 静态检查、阶段变换、工作区准备、归档处理、候选构建与验证 / Python static checks, staged transformations, workspace preparation, archive handling, candidate build and verification |
| `data/` | 英雄、布局、原生调用契约、阶段基线、工具清单等结构化数据 / Structured hero, layout, native contract, stage baseline, and tool-manifest data |
| `tests/` | Python 单元测试及 JASS 运行时测试素材 / Python unit tests and JASS runtime test fixtures |

## 构建与测试 / Build and tests

公开快照刻意不含 `inputs/original.w3x`、`vendor/`、构建中间目录 `scratch/`、生成地图和第三方二进制。`tools/build.py` 默认要求 `inputs/original.w3x`，并校验它与仓库内固定的源地图 SHA-256 基线完全一致；工具清单列出的依赖也须由使用者自行合法取得。构建工具使用 Windows 专用的 `pjass.exe` 和 StormLib DLL。

The public snapshot intentionally excludes `inputs/original.w3x`, `vendor/`, generated workspace files under `scratch/`, compiled maps, and third-party binaries. `tools/build.py` expects `inputs/original.w3x` and checks its SHA-256 against the pinned source-map baseline. Dependencies listed in `data/tool-manifest.json` must be obtained lawfully by the user. The build tooling uses Windows-specific `pjass.exe` and a StormLib DLL.

在 Windows 上准备好**匹配基线的源地图**、清单要求的工具和 Python 3 环境后，可从仓库根目录执行：

After setting up Windows, a source map that matches the pinned baseline, the manifest-listed tools, and Python 3, run from the repository root:

```powershell
python tools/prepare_workspace.py --source inputs/original.w3x
python -m unittest discover -s tests -v
python tools/build.py --source inputs/original.w3x --out dist
```

这些命令描述的是工具接口，不代表本公开快照已具备缺失资源或本次已运行验证。未准备输入和依赖时，测试或构建会因缺失文件而无法完成。即使离线候选构建成功，构建报告也明确将 `runtime_verified`、`playable_verified` 和 `multiplayer_verified` 设为 `false`。

These commands document the tooling interface; they do not mean the missing assets are present in this snapshot or that verification was run as part of this documentation update. Tests or builds cannot complete without the required inputs and dependencies. Even a successful offline candidate build marks `runtime_verified`, `playable_verified`, and `multiplayer_verified` as `false` in its report.

详细前置条件见 [构建指南](docs/BUILD_GUIDE.md)，项目边界与进度见 [项目状态](docs/PROJECT_STATUS.md)。

See the [build guide](docs/BUILD_GUIDE.md) for prerequisites and [project status](docs/PROJECT_STATUS.md) for scope and validation boundaries.

## 公开快照边界 / Public snapshot boundary

此仓库不包含原始或编译后的 `.w3x` 地图、私有 Git 历史、第三方工具/二进制、证据截图、运行日志或会话材料。源码审查与离线脚本验证不能替代正式 Warcraft III 客户端、KK 环境或五名真人联机验证。请勿提交地图原件、账户资料或未获授权的素材。

This repository excludes original or compiled `.w3x` maps, private Git history, third-party tools/binaries, evidence screenshots, runtime logs, and session materials. Source review and offline script checks do not substitute for validation in the Warcraft III client, a KK environment, or a five-human multiplayer session. Do not commit map originals, account data, or assets you are not authorized to redistribute.

## 许可 / License

源码依 [MIT License](LICENSE) 发布。第三方地图、工具、素材及服务仍受其各自条款约束。

The source is released under the [MIT License](LICENSE). Third-party maps, tools, assets, and services remain subject to their own terms.
