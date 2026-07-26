# 開発フロー

## ブランチ運用

```
master
 └── develop
       └── review/KTN-<番号>
             └── feature/KTN-<番号>
```

- **master**: 常にリリース可能な安定版。
- **develop**: 開発中の内容を集約する統合ブランチ。`master` から作成する。
- **review/KTN-\<番号\>**: `develop` から作成する、1チケット単位のレビュー用ブランチ。
- **feature/KTN-\<番号\>**: `review/KTN-\<番号\>` から作成する作業ブランチ。実際の修正はここで行う。

`<番号>` は対応するGitHub Issueの番号（例: Issue #1 → `KTN-1`）。

## 作業の流れ

1. `develop` から `review/KTN-<番号>` を作成する。
2. `review/KTN-<番号>` から `feature/KTN-<番号>` を作成し、そこで修正する。
3. 修正が終わったらPull Requestを作成する: `feature/KTN-<番号>` → `review/KTN-<番号>`。
   - タイトルは `feature/KTN-<番号> → review/KTN-<番号>` とする。
   - 本文に対応するissueを `Closes #<番号>` の形式で書く。
4. レビューが通ったら `review/KTN-<番号>` → `develop` にマージする。
5. リリースするタイミングで `develop` → `master` にマージする。

## コミットメッセージ

- 1コミット1変更を基本とする。
- 「何を変えたか」ではなく「なぜ変えたか」を書く（差分自体が「何を」を示すため）。
- 対応するissueがあれば末尾に `(#<番号>)` を付ける。
