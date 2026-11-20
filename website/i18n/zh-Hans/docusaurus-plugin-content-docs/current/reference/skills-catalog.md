---
sidebar_position: 5
title: "内置技能目录"
description: "随 Hermes Agent 附带的内置技能目录"
---

# 内置技能目录

OMA Agent 附带以下三个内置技能，安装时会复制到 `~/.hermes/skills/`。下方每个技能均链接至专属页面，包含完整定义、配置和用法说明。

Hermes 在执行 `hermes update` 时也会同步内置技能，但同步清单会尊重本地删除和用户编辑。如果此处列出的某个技能在你的 `~/.hermes/skills/` 目录树中缺失，它仍随 Hermes 一同发布；可通过 `hermes skills reset <name> --restore` 恢复。

如果某个技能未出现在此列表中但存在于仓库中，目录由 `website/scripts/generate-skill-docs.py` 重新生成。

## autonomous-ai-agents

| 技能 | 描述 | 路径 |
|---|---|---|
| [`computer-use`](/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-computer-use) | 控制桌面应用。 | `autonomous-ai-agents/computer-use` |
| [`hermes-agent`](/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent) | 配置、扩展或贡献 Hermes Agent。 | `autonomous-ai-agents/hermes-agent` |

## oma

| 技能 | 描述 | 路径 |
|---|---|---|
| [`oma-agents`](/user-guide/skills/bundled/oma/oma-oma-agents) | 管理代理设置和供后续使用的文件。 | `oma/oma-agents` |
| [`oma-brand`](/user-guide/skills/bundled/oma/oma-oma-brand) | 管理品牌标识、素材和知识。 | `oma/oma-brand` |
| [`oma-campaigns`](/user-guide/skills/bundled/oma/oma-oma-campaigns) | 管理 OMA 剧本和代理。 | `oma/oma-campaigns` |
| [`oma-onboarding`](/user-guide/skills/bundled/oma/oma-oma-onboarding) | 通过一个网址设置品牌、活动和代理。 | `oma/oma-onboarding` |
| [`oma-playbook`](/user-guide/skills/bundled/oma/oma-oma-playbook) | 管理品牌的营销计划及策略。 | `oma/oma-playbook` |
