# 项目状态 / Project status

> 本页记录此公开快照的源码范围和可确认的验证边界，不是实时开发看板。  
> This page describes the scope and evidence boundaries of this source snapshot; it is not a live development tracker.

## 项目范围 / Project scope

源码组织成逐阶段的地图更新工具：Python 工具从原地图提取受控成员，再按步骤更新布局、玩家槽位、英雄/选择 UI、物件、战斗、平台接口、免费内容、玩法、第五人技能、终局与环形区域等内容；JASS 源码与 JSON 基线描述目标逻辑和结构化输入。

The source is organized as staged map-update tooling. Python tools extract controlled members from the source map and apply steps for layout, player slots, hero/selection UI, objects, combat, platform interfaces, free content, gameplay, fifth-player skills, endgame, and radial regions. JASS modules and JSON baselines describe target logic and structured inputs.

该阶段化流水线主要用于可重复的离线改动和防止归档中未授权内容被意外替换。它本身不等于地图已通过游戏内验证。

The staged pipeline supports repeatable offline changes and checks against accidental replacement of protected archive content. It does not mean the map has passed in-game validation.

## 验证边界 / Validation boundary

仓库构建报告把地图状态定义为离线候选或不完整开发检查点，并显式保留 `runtime_verified=false`、`playable_verified=false`、`multiplayer_verified=false`。在没有目标客户端证据前，本项目不宣称：

The build tooling describes its output as an offline candidate or incomplete development checkpoint and explicitly records `runtime_verified=false`, `playable_verified=false`, and `multiplayer_verified=false`. Without target-client evidence, this project does not claim:

- Warcraft III 或 KK 环境中的运行时兼容性；
- 玩法、UI、技能、物件拾取/升级或阶段事件已在客户端完成验收；
- 五人真人联机、等待时序或多客户端状态同步已验证；
- 本公开快照可以直接启动为完整地图。

- Runtime compatibility in Warcraft III or KK environments;
- In-client acceptance of gameplay, UI, skills, object pickup/upgrades, or timed events;
- Validation of five-human multiplayer, timing, or cross-client synchronization;
- The ability to launch this public snapshot directly as a complete map.

查看 [构建指南](BUILD_GUIDE.md) 了解外部素材、工具和离线命令要求。路线阶段的计划项是开发目标，不是已完成事项。

See the [build guide](BUILD_GUIDE.md) for external asset/tool prerequisites and offline commands. Planned roadmap stages are goals, not completed work.

## 快照来源 / Snapshot provenance

- 私有源分支 / Private source branch: `feat/five-player`
- 源提交 / Source revision: `c34e8c4` (2026-10-18)
- 本仓库保留源码和 MIT 许可，但未保留私有 Git 历史 / This repository retains source and the MIT license, not private Git history
- 未包含原始/编译 `.w3x`、`inputs/`、`vendor/`、证据截图、运行日志或会话记录 / Original/compiled `.w3x`, `inputs/`, `vendor/`, evidence screenshots, runtime logs, and session records are excluded
