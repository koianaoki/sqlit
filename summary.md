# diff.txt（`origin/main..origin/codex/fix-filter-issue-in-tree-view`）で `origin/main` に対して追加された機能サマリー

以下は `diff.txt` の差分を、**機能単位で一つずつ**整理したものです。

## 1) 結果テーブル: `yi` で INSERT 文をコピー
- 追加キー: `yi`（results コンテキスト）。
- 目的: 選択中の結果行を、再投入可能な `INSERT INTO ... VALUES (...)` 形式の SQL としてクリップボードへコピーできるようにする。
- 影響範囲:
  - `README.md` に操作説明を追加。
  - `sqlit/core/keymap.py` でキーバインド追加。
  - `sqlit/domains/results/ui/mixins/results.py` にアクション実装追加。
  - `sqlit/shared/ui/protocols/results.py` に必要プロトコル拡張。
  - MySQL 向けの値エスケープ/型処理（`mysql/base.py`）や結果整形連携が強化。
  - テスト追加: `tests/unit/test_results_yank_insert.py`、`tests/unit/test_vim_visual_mode.py`（視覚選択との整合）など。

## 2) Explorer: Table Filter（テーブル配下スコープ検索）の追加
- 追加アクション: `table_filter`。
- 追加キー: tree コンテキストで `t`。
- 目的: 通常のツリー全体フィルタとは別に、テーブル配下に対象を絞ったフィルタ導線を提供。
- 挙動の要点:
  - テーブル/フォルダ/DB ノードから `table_filter` を開始可能。
  - スコープ情報（起点ノード/パス）を持ち、該当サブツリー中心に検索。
  - フィルタ中にマッチノードへジャンプ、ハイライト、可視制御。
- 影響範囲:
  - `sqlit/core/keymap.py`。
  - `sqlit/domains/explorer/state/tree_on_database.py`。
  - `sqlit/domains/explorer/state/tree_on_folder.py`。
  - `sqlit/domains/explorer/state/tree_on_table.py`。
  - `sqlit/domains/explorer/ui/mixins/tree_filter.py`（主要ロジック）。
  - `sqlit/shared/ui/protocols/explorer.py`（ホスト要件拡張）。
  - テスト追加: `tests/ui/test_tree_filter_tables_scope.py`、`tests/unit/test_tree_filter.py`、keybinding/state machine テスト。

## 3) Explorer Filter 基盤: フィルタ中の復元・可視制御・ハイライト強化
- 目的: フィルタ入力ごとの再計算時に、前回の絞り込み結果へ破壊的に依存しないようにする。
- 主な追加/変更:
  - ツリースナップショット化と復元（入力ごとにベース状態を再構築）。
  - マッチノードのラベルハイライト。
  - ノード可視制御（非マッチ除去、祖先保持）。
  - マッチ移動（next/prev）や accept 時のカーソル復帰調整。
- 影響範囲:
  - `sqlit/domains/explorer/ui/mixins/tree_filter.py`。
  - 関連テスト: `tests/unit/test_tree_filter.py`、`tests/ui/keybindings/test_state_machine.py` など。

## 4) Explorer: テーブル/ビュー展開時の「事前読み込み」系強化
- 目的: table/view ノード展開時に、列情報表示を待たせない・欠損させない方向に寄せる。
- 主な追加/変更:
  - `tree.py` 側で table/view 展開時に列ロード処理へ入る導線追加。
  - 必要時に DB 接続を確保してから列ロード（接続状態との整合改善）。
  - `schema_service.py` / `tree/loaders.py` / `schema_render.py` でロード・描画連携調整。
- 影響範囲:
  - `sqlit/domains/explorer/ui/mixins/tree.py`。
  - `sqlit/domains/explorer/app/schema_service.py`。
  - `sqlit/domains/explorer/ui/tree/loaders.py`。
  - `sqlit/domains/explorer/ui/tree/schema_render.py`。
  - テスト: `tests/ui/explorer/test_tree_expansion.py`、`test_refresh_expanded_loads.py`、`test_multidb_refresh.py`、`test_tree_schema_grouping.py`。

## 5) Explorer: Columns/Indexes ショートカットと状態遷移の整備
- 目的: tree 上のテーブル系ノードから列/索引表示へ素早く遷移。
- 追加/変更:
  - `c` = show_table_columns。
  - `i` = show_table_indexes。
  - 各 state（database/folder/table）で action 許可・表示を調整。
- 影響範囲:
  - `sqlit/domains/explorer/state/tree_on_database.py`。
  - `sqlit/domains/explorer/state/tree_on_folder.py`。
  - `sqlit/domains/explorer/state/tree_on_table.py`。
  - テスト: `tests/ui/explorer/test_table_metadata_shortcuts.py`、`tests/ui/keybindings/test_keymap_provider.py`。

## 6) Explorer: マークアップエスケープ・表示安定化
- 目的: ノードラベルの強調表示や特殊文字表示時の崩れ防止。
- 主な追加/変更:
  - ハイライト時にマークアップを適切にエスケープ。
  - ラベル再構成処理の安定化。
- 影響範囲:
  - `sqlit/domains/explorer/ui/mixins/tree_filter.py`。
  - `tests/ui/explorer/test_markup_escaping.py`。

## 7) Query Autocomplete: 補完位置/文脈判定の改善
- 目的: SQL 入力中のカーソル位置に応じた補完精度の改善。
- 影響範囲:
  - `sqlit/domains/query/ui/mixins/autocomplete.py`。
  - `tests/unit/test_autocomplete_location.py`。

## 8) Shell/InputContext/StateMachine 側の連携拡張
- 目的: tree filter・results 操作追加に合わせて、入力文脈と action 解決を破綻なく拡張。
- 影響範囲:
  - `sqlit/core/input_context.py`。
  - `sqlit/domains/shell/app/main.py`。
  - `sqlit/domains/shell/state/machine.py`。
  - `tests/ui/keybindings/test_state_machine.py`。

## 9) MySQL provider 側の補助強化（INSERT コピー支援）
- 目的: `yi` で生成する INSERT 文の値表現を DB 方言に合わせる。
- 追加/変更:
  - 文字列/NULL/日付等の値エンコードやエスケープ調整。
- 影響範囲:
  - `sqlit/domains/connections/providers/mysql/base.py`。
  - `tests/unit/test_mysql_indexes.py`（関連周辺の既存仕様も検証）。

## 10) ドキュメント追加: `docs/design.md`
- 新規追加（大規模）:
  - アーキテクチャ全体像。
  - ディレクトリ責務。
  - 実行フロー（起動、接続、クエリ実行、キー入力状態機械）。
  - 主要ファイルの役割一覧。
- 目的: 開発者向け設計知識の明文化。

---

## 補足（差分全体の傾向）
- 機能追加の中心は以下の3本柱。
  1. **Results の `yi`（INSERT コピー）**
  2. **Explorer の Table Filter + フィルタ処理高度化**
  3. **Explorer 展開時の列ロード事前化（読み込み連携強化）**
- これに伴い、UI 操作（keymap/state）、プロトコル、loader、テストが横断的に拡張されている。
