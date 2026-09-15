---
name: commit-push-merge
description: 在 AlphaEdge 專案中執行「commit + push + merge」時使用。當使用者要求「commit + push + merge」、「merge 進 main」、「合併到 main 並同步分支」時觸發；只要求 commit + push 而沒提到 merge 時不要使用。
---

# AlphaEdge Commit + Push + Merge

`.claude/skills/commit-push-merge/SKILL.md` 是本專案 merge 流程的**唯一權威文件**，完整定義了：
前置檢查、依 `CLAUDE.md` §4 commit + push、以 `--no-ff` merge 進 `main`、
將本地與遠端所有落後 `main` 的分支同步到 `main`（有 `main` 沒有的 commit 則跳過並列出）、
遇到衝突或無法 fast-forward 時的停止條件，以及回覆使用者的格式。

本檔只是指標，**不重複任何規則內容**——規範一旦兩邊各存一份就會漂移。

## 執行步驟

1. 一律先完整讀取 [`.claude/skills/commit-push-merge/SKILL.md`](../../../.claude/skills/commit-push-merge/SKILL.md)
   與 [`CLAUDE.md`](../../../CLAUDE.md) §4，再開始執行任何 git 指令，不要只憑記憶操作。
2. 依該文件的步驟逐一執行；遇到文件列出的停止條件時，停下來回報，不自行決定解法。

> 規則需要修改時，改 `.claude/skills/commit-push-merge/SKILL.md`，不要改本檔。
> 本檔僅在指標失效（例如權威文件搬家）時才需要更新。
