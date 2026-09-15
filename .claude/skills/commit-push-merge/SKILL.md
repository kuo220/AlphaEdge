---
name: commit-push-merge
description: 在 AlphaEdge 專案中執行「commit + push + merge」時使用。先依 CLAUDE.md §4 commit 並 push 目前分支，再以 --no-ff merge 進 main 並 push，最後把本地與遠端所有落後 main 的分支 fast-forward 到 main。
when_to_use: 使用者明確要求「commit + push + merge」、「merge 進 main」、「合併到 main 並同步分支」時。只要求 commit + push 而沒提到 merge 時不要載入，照 CLAUDE.md §4 執行即可。
---

# AlphaEdge Commit + Push + Merge

**本檔是 merge 流程的唯一來源**，對應 `CLAUDE.md` §4 的指標。
commit message 格式與基本回覆欄位仍以 `CLAUDE.md` §4 為準，本檔不重複那些規則。
其他工具的同名 skill（`.cursor/skills/commit-push-merge/`）一律只放指標，內容不得複製一份。

merge 會改動 `main` 並推上遠端，事後難以撤回。因此流程中凡是**無法以 fast-forward
或無衝突方式完成**的情況，一律停下來回報，不自行決定解法。

## 1. 前置檢查

1. 記下目前分支為 `<branch>`。若 `<branch>` 就是 `main`，跳過第 3 節，只做第 2、4 節。
2. 確認工作目錄沒有與本次變更無關的未提交內容；有的話先問使用者哪些要進 commit。
3. 執行 `git fetch origin --prune`，讓後續比對以遠端最新狀態為準。

## 2. Commit + Push

依 `CLAUDE.md` §4 在 `<branch>` 上 commit，再執行 `git push origin <branch>`。
沒有可 commit 的變更時跳過 commit，但仍要確認 `<branch>` 已經 push。

## 3. Merge 進 main

```bash
git checkout main
git merge --ff-only origin/main   # 本地 main 先追上遠端
git merge --no-ff <branch>        # 保留 merge commit
git push origin main
```

- `--ff-only` 失敗（本地 `main` 有遠端沒有的 commit）：停下來回報，不要自行 merge 或 rebase。
- `--no-ff` 發生衝突：執行 `git merge --abort` 還原，列出衝突檔案後停下來回報，**不自動解衝突**。
- merge commit 訊息使用 git 預設的 `Merge branch '<branch>' into main`，與既有歷史一致。

## 4. 同步所有分支到 main

**對象**：本地分支與 `origin/*` 遠端分支，排除 `main`、`origin/main` 與 `origin/HEAD`。
本地與遠端**分開判斷**：同名分支兩邊的狀態可能不同。

對每個 ref（本地為 `<name>`，遠端為 `origin/<name>`）判斷：

```bash
git rev-list --count main..<ref>   # ref 有幾個 main 沒有的 commit
git rev-parse <ref> main           # 兩者相同代表已是最新
```

| 狀態 | 本地分支 | 遠端分支 |
|------|----------|----------|
| 與 `main` 相同 | 不動，記為「已是最新」 | 不動，記為「已是最新」 |
| 落後 `main`（count = 0） | `git branch -f <name> main` | `git push origin main:<name>` |
| 有 `main` 沒有的 commit（count > 0） | 跳過並列出 | 跳過並列出 |

規則：

1. **只更新已存在的分支**：不為只在遠端的分支建立本地分支，也不把只在本地的分支推上遠端。
2. 遠端一律用一般 push，**禁止 `--force`**。非 fast-forward 的更新會被 git 拒絕，當作第二道防線；被拒絕時記為跳過並列出原因。
3. `git branch -f` 若因分支在其他 worktree 被 checkout 而失敗，記為跳過並列出原因。
4. 不刪除任何分支，也不對跳過的分支做 merge 或 rebase。

## 5. 收尾

執行 `git checkout <branch>` 回到原本的分支（此時已與 `main` 相同）。

## 6. 回覆使用者

除了 `CLAUDE.md` §4 要求的欄位（分支名稱、commit hash、push 目標、變更檔案清單），另外列出：

1. merge commit hash（`main` 的新 HEAD）。
2. 分支同步結果表：

   | 分支 | 本地 | 遠端 |
   |------|------|------|
   | `dev` | ✅ 已更新 `abc1234 → def5678` | ✅ 已更新 `abc1234 → def5678` |
   | `feature/x` | ⏭ 跳過：有 3 個 `main` 沒有的 commit | — 不存在 |
   | `feature/y` | ✅ 已是最新 | ✅ 已是最新 |

中途停止時，說明停在哪一步、原因、目前 repo 狀態（位於哪個分支、`main` 是否已 push），以及恢復時的下一步。
