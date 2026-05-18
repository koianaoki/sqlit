# sqlit コードデザイン

sqlit は、Textual ベースの SQL データベース TUI です。中心は `SSMSTUI` アプリで、接続、Explorer、クエリエディタ、結果表示、ナビゲーションを mixin と状態機械で合成します。DB ごとの差分は provider/adapter/schema に閉じ込め、UI とクエリ実行は共通の抽象を使います。

## 1. 全体アーキテクチャ

```text
CLI / 起動引数
  ↓
sqlit.cli
  ↓ RuntimeConfig / AppServices
sqlit.domains.shell.app.main.SSMSTUI
  ├─ core: キーマップ、状態、入力ルーティング
  ├─ shared: 共通 store、process、UI widget、protocol
  └─ domains
      ├─ connections: 接続設定、認証情報、driver、DB adapter
      ├─ explorer: DB オブジェクトツリーとスキーマ取得
      ├─ query: SQL 編集、補完、実行、履歴
      ├─ results: 結果テーブル、フィルタ、値表示、保存
      ├─ shell: アプリ本体、画面遷移、テーマ、コマンド
      └─ process_worker: driver import / 重い処理の別プロセス化
```

### 設計の分割方針

- `core/`: 「キー入力をどの状態でどの action にするか」を司る純粋な制御層。
- `shared/`: 特定ドメインに依存しない共通部品。設定 store、process runner、Textual widget、Protocol を置く。
- `domains/*/domain`: そのドメインのデータ構造、値オブジェクト、純粋ロジック。
- `domains/*/app`: UI から呼ばれるアプリケーションサービス。副作用、永続化、外部 CLI、DB 実行を扱う。
- `domains/*/ui`: Textual の画面、mixin、widget バインディング。ユーザー操作を action として実装する。
- `domains/*/state`: UIStateMachine が参照する状態別の action 許可、help 表示、binding 定義。
- `domains/*/store`: JSON ファイルや履歴など、永続化の具象実装。
- `domains/connections/providers/<db>`: DB 種別ごとの差分。`provider.py` が設定 schema と接続生成、`adapter.py` が DB-API 差分、`schema.py` がメタデータ取得を担当する。

## 2. 俯瞰的なディレクトリ構成

```text
.
├── sqlit/
│   ├── cli.py                         # argparse、CLI サブコマンド、Textual app 起動
│   ├── core/                          # キーマップ、入力コンテキスト、状態基盤
│   ├── shared/                        # 共通 services、store、process、UI widget、Protocol
│   └── domains/
│       ├── shell/                     # Textual app 本体、テーマ、画面遷移、トップレベル状態
│       ├── connections/               # 接続定義、認証情報、driver、provider、接続 UI
│       ├── explorer/                  # DB ツリー、スキーマロード、ツリーフィルタ
│       ├── query/                     # SQL エディタ、補完、実行、履歴、Vim 編集
│       ├── results/                   # 結果表示、結果フィルタ、値ビュー、保存
│       └── process_worker/            # 別プロセス worker と client
├── tests/                             # 単体、統合、UI、provider 別テスト
├── config/                            # 設定テンプレート、mock 設定
├── assets/                            # ロゴなど静的アセット
├── infra/                             # テスト用 Docker / Terraform 補助
└── docs/                              # デモ画像と設計ドキュメント
```

## 3. 主要な実行フロー

### 3.1 TUI 起動

1. `sqlit.cli` が引数、URL、mock、profile、driver install 設定を解釈する。
2. `RuntimeConfig` と `AppServices` を組み立てる。
3. `SSMSTUI` を生成し、`Textual.App.run()` で開始する。
4. `startup_flow.run_on_mount()` が設定読込、mock 適用、起動時接続、接続 picker 復元を行う。
5. 以後のキー入力は `SSMSTUI.on_key()` → `core.key_router.resolve_action()` → `action_*` メソッドに流れる。

### 3.2 接続

1. CLI または connection picker/form が `ConnectionConfig` を作る。
2. `ConnectionManager` / `ConnectionFlow` が provider を選び、必要なら driver install と SSH tunnel を準備する。
3. `DatabaseProvider.connect()` で接続し、`ConnectionSession` に config/provider/connection/tunnel を保持する。
4. Explorer の root を構築し、schema service が DB オブジェクトを遅延ロードする。

### 3.3 クエリ実行

1. Query pane の SQL を `QueryMixin.action_execute_query()` 系が取得する。
2. `multi_statement` が statement を分割し、`query_service` / `query_runner` が timeout/cancel/transaction を考慮して実行する。
3. 結果 rows/columns は results mixin と widget に渡される。
4. 履歴 store に保存し、autocomplete 用 schema cache も必要に応じて更新される。

### 3.4 キー入力と状態

- `InputContext` が現在 focus、vim mode、modal、leader pending、実行中などを表す。
- `UIStateMachine` が `State` 群から active state を選び、action の許可と help/footer 表示を決める。
- `keymap` は key → action の候補を持ち、`key_router` が状態と validation を見て最終 action を選ぶ。

## 4. ディレクトリごとの責務

| ディレクトリ | 責務 |
|---|---|
| `sqlit/` | パッケージ root。CLI entrypoint、version、mock helper。 |
| `sqlit/core/` | UI ドメイン横断の入力制御。状態基盤、keymap、leader command、Vim mode、action validation。 |
| `sqlit/shared/app/` | DI 的な runtime/services 構築、startup profiling。 |
| `sqlit/shared/core/` | JSON store、process runner、debug event、terminal/system probe、汎用 util。 |
| `sqlit/shared/ui/` | 共有 Textual widget、modal screen、Protocol、clipboard、lifecycle。 |
| `sqlit/domains/shell/` | Textual app 本体、トップレベル状態、テーマ、leader/help 画面、コマンド router。 |
| `sqlit/domains/connections/` | 接続設定、認証情報、保存、driver install、SSH tunnel、provider 群、接続 UI、cloud/docker discovery。 |
| `sqlit/domains/explorer/` | DB オブジェクト Explorer。tree node、schema service、非同期ロード、展開状態、フィルタ。 |
| `sqlit/domains/query/` | SQL editor。補完、Vim 風編集、履歴/starred、実行サービス、CLI query。 |
| `sqlit/domains/results/` | クエリ結果のテーブル表示、format、フィルタ、値詳細表示、ファイル保存。 |
| `sqlit/domains/process_worker/` | DB driver import や接続テストなどを別プロセスで扱う worker。 |
| `tests/` | DB provider、CLI、UI、単体、統合、性能テスト。 |
| `config/` | 設定テンプレートと mock 起動設定。 |
| `infra/` | 統合テスト用 Docker compose / cloud infra。 |

## 5. ファイルごとの処理

### 5.1 パッケージ root

| ファイル | 処理 |
|---|---|
| `sqlit/__init__.py` | パッケージ初期化。 |
| `sqlit/_version.py` | パッケージ version を保持する。 |
| `sqlit/cli.py` | CLI entrypoint。接続 URL 抽出、argparse、runtime/services 構築、TUI 起動、`connections` / `query` サブコマンド委譲を行う。 |
| `sqlit/mock_settings.py` | mock docker container 情報をプロセス内で設定・参照するテスト/デモ補助。 |

### 5.2 `sqlit/core/`

| ファイル | 処理 |
|---|---|
| `action_validation.py` | keymap に登録された action が app に実装されているか検証する。 |
| `binding_contexts.py` | footer/help に出す binding context を現在状態から組み立てる。 |
| `connection_manager.py` | 接続テスト、接続開始、再接続、セッション差し替えをまとめる facade。 |
| `input_context.py` | focus、vim mode、modal、leader pending、query executing など入力判断に必要なスナップショット。 |
| `key_router.py` | 押された key と `InputContext` から許可済み action を解決する。 |
| `keymap.py` | default keymap、leader key、表示用 key formatting、debug snapshot 出力。 |
| `leader_commands.py` | leader menu のコマンド定義と action 一覧を提供する。 |
| `state_base.py` | `State` / `BlockingState` / `ActionSpec` / help 表示など状態機械の基底。 |
| `vim.py` | `NORMAL` / `INSERT` / `VISUAL` など Vim mode enum。 |
| `__init__.py` | core package 初期化。 |

### 5.3 `sqlit/shared/app/`

| ファイル | 処理 |
|---|---|
| `runtime.py` | 環境変数・CLI 由来の `RuntimeConfig` と mock 設定値を保持する。 |
| `services.py` | settings store、connection store、provider factory、driver resolver、process runner、cloud discovery などを組み立てる。 |
| `startup_profiler.py` | 起動時間と import timing をログに出す profiler。 |
| `__init__.py` | shared app の public export。 |

### 5.4 `sqlit/shared/core/`

| ファイル | 処理 |
|---|---|
| `debug_events.py` | debug event bus、payload 正規化、serialize、global emitter を提供する。 |
| `processes.py` | 同期/非同期 subprocess runner とテスト用 fixed runner。 |
| `protocols.py` | executor、provider factory、history/store/tunnel など core 側 Protocol。 |
| `store.py` | config directory 解決と JSON file store の共通実装。 |
| `system_probe.py` | OS、Python、site-packages、stdlib など runtime 環境を調べる。 |
| `system_probe_fake.py` | test/mock 用の fake system probe。 |
| `terminal.py` | terminal 種別検出と別 terminal 起動補助。 |
| `utils.py` | fuzzy match、match highlight、duration formatting。 |
| `__init__.py` | shared core package 初期化。 |

### 5.5 `sqlit/shared/ui/`

| ファイル | 処理 |
|---|---|
| `clipboard.py` | pyperclip または OS native command で clipboard read/write を行う。 |
| `lifecycle.py` | Textual lifecycle hook を mixin として共通化する。 |
| `spinner.py` | 長時間処理表示用 spinner。 |
| `widgets.py` | 共有 widget の再 export。 |
| `widgets_autocomplete.py` | autocomplete dropdown widget。 |
| `widgets_dialogs.py` | dialog container widget。 |
| `widgets_filter.py` | Explorer/results 用 filter input。 |
| `widgets_flash.py` | widget の一時的な visual feedback。 |
| `widgets_footer.py` | 状態別 keybinding footer。 |
| `widgets_json_tree.py` | JSON 値を展開表示する tree widget。 |
| `widgets_stacked_results.py` | 複数 statement 結果、エラー、非 query 結果を縦に積む container。 |
| `widgets_tables.py` | 大量行向け results table と container。 |
| `widgets_text_area.py` | SQL query editor 用 text area。 |
| `widgets_value_view.py` | cell 値の inline/detail 表示。 |
| `__init__.py` | shared UI package 初期化。 |

#### `sqlit/shared/ui/screens/`

| ファイル | 処理 |
|---|---|
| `confirm.py` | Yes/No 確認 modal。 |
| `error.py` | エラー表示 screen。 |
| `file_picker.py` | ファイル/ディレクトリ選択 modal。 |
| `loading.py` | loading modal。 |
| `message.py` | メッセージ表示 modal。 |
| `__init__.py` | screen package 初期化。 |

#### `sqlit/shared/ui/protocols/`

| ファイル | 処理 |
|---|---|
| `__init__.py` | app 全体 Protocol の export。 |
| `autocomplete.py` | autocomplete state/action Protocol。 |
| `connections.py` | connection state/action Protocol。 |
| `core.py` | Textual app 最小 Protocol。 |
| `explorer.py` | Explorer state/action Protocol。 |
| `lifecycle.py` | lifecycle hook Protocol。 |
| `metadata.py` | table metadata helper Protocol。 |
| `mixins.py` | 各 mixin が想定する host Protocol。 |
| `query.py` | query state/action Protocol。 |
| `results.py` | results state/action Protocol。 |
| `screens.py` | theme screen など screen 用 Protocol。 |
| `startup.py` | startup flow が使う app Protocol。 |
| `ui_navigation.py` | UI navigation state/action Protocol。 |
| `vim.py` | Vim mode 参照 Protocol。 |
| `widgets.py` | widget accessor Protocol。 |

### 5.6 `sqlit/domains/shell/`

#### `app/`

| ファイル | 処理 |
|---|---|
| `main.py` | `SSMSTUI` 本体。Textual app と各 domain mixin を合成し、compose、key routing、debug、spinner、command mode、状態 machine を管理する。 |
| `startup_flow.py` | on_mount 時の接続一覧読込、mock 適用、起動時接続、restart 復元、startup log を処理する。 |
| `idle_scheduler.py` | UI idle 時に後回し処理を実行する scheduler。 |
| `theme_manager.py` | 現在テーマの適用、保存、override を管理する。 |
| `themes.py` | theme 定義と mode 色の default 補正。 |
| `omarchy.py` | Omarchy/terminal theme 連携と default theme。 |
| `__init__.py` | shell app package 初期化。 |

#### `app/commands/`

| ファイル | 処理 |
|---|---|
| `router.py` | shell command string を command handler に dispatch する。 |
| `alert.py` | alert/notification 系 command。 |
| `credentials.py` | credential 診断・操作 command。 |
| `debug.py` | debug event、keybinding、state など診断 command。 |
| `watchdog.py` | UI stall watchdog command。 |
| `worker.py` | process worker 関連 command。 |
| `__init__.py` | `dispatch_command` を export。 |

#### `state/`

| ファイル | 処理 |
|---|---|
| `machine.py` | 現在 context から active state を選び、action 許可を判定する `UIStateMachine`。 |
| `root.py` | 全状態共通の root action/help。 |
| `main_screen.py` | 通常画面の action/help。 |
| `modal_active.py` | modal 表示中に許す action。 |
| `query_executing.py` | クエリ実行中の blocking/allowed action。 |
| `leader_pending.py` | leader key 入力待ち状態。 |
| `__init__.py` | state export。 |

#### `ui/`

| ファイル | 処理 |
|---|---|
| `mixins/ui_leader.py` | leader menu 表示、leader pending の開始/終了。 |
| `mixins/ui_navigation.py` | pane 移動、focus 切替、fullscreen、modal 操作。 |
| `mixins/ui_status.py` | status bar、通知、接続状態表示の更新。 |
| `mixins/__init__.py` | shell UI mixin export。 |
| `screens/help.py` | context-aware help screen。 |
| `screens/leader_menu.py` | leader command menu。 |
| `screens/theme.py` | theme 選択・custom theme screen。 |
| `screens/__init__.py` | screen package 初期化。 |
| `__init__.py` | shell UI package 初期化。 |

#### `store/`

| ファイル | 処理 |
|---|---|
| `settings.py` | settings JSON の path 解決、読込、保存。 |
| `__init__.py` | store package 初期化。 |

### 5.7 `sqlit/domains/connections/`

#### `domain/`

| ファイル | 処理 |
|---|---|
| `config.py` | `ConnectionConfig`、SSH 設定、TLS/extra options、schema field 定義。 |
| `password_command.py` | 外部 command で password/token を取得する。 |
| `passwords.py` | password フィールドの検出、mask、merge など credential helper。 |
| `__init__.py` | domain package 初期化。 |

#### `app/`

| ファイル | 処理 |
|---|---|
| `cloud_actions.py` | cloud picker からの接続/refresh/firewall などの action service。 |
| `connection_flow.py` | 接続 form/prompt から config を完成させ、接続開始までを orchestrate する。 |
| `credentials.py` | keyring/plaintext/file credential store の抽象と実装。 |
| `executor.py` | connection/cursor を使う query/schema 実行の共通 executor。 |
| `install_strategy.py` | pipx/uv/pip/system package など driver install 方法の検出と候補生成。 |
| `installer.py` | missing driver の install UI/app service。 |
| `mock_adapter_core.py` | mock DB connection/cursor/adapter。 |
| `mock_data.py` | demo 用 fake rows の生成。 |
| `mock_default_adapters.py` | sqlite/postgresql/mysql/supabase など default mock adapter 生成。 |
| `mock_profiles.py` | `--mock` profile 定義。 |
| `mock_provider.py` | mock provider factory。 |
| `mock_settings.py` | JSON mock settings を profile/adapter/container に変換する。 |
| `mocks.py` | mock 関連の共通 export。 |
| `persist_utils.py` | 保存対象 connection config を password 方針込みで組み立てる。 |
| `save_connection.py` | connection name 重複回避と保存処理。 |
| `session.py` | 現在接続の connection/config/provider/tunnel をまとめる。 |
| `tunnel.py` | SSH tunnel 作成と no-op tunnel。 |
| `url_parser.py` | `postgres://...` など URL から `ConnectionConfig` を生成する。 |
| `__init__.py` | app package 初期化。 |

#### `cli/`

| ファイル | 処理 |
|---|---|
| `commands.py` | `sqlit connections list/add/edit/delete` と docker list の実装。 |
| `helpers.py` | provider schema から argparse 引数を生成し、args から config を作る。 |
| `prompts.py` | CLI で不足 password/SSH password を尋ねる補助。 |
| `__init__.py` | CLI package 初期化。 |

#### `store/`

| ファイル | 処理 |
|---|---|
| `connections.py` | saved connections JSON の読込/保存。 |
| `memory.py` | test/mock 用 in-memory connection store。 |
| `__init__.py` | store package 初期化。 |

#### `discovery/`

| ファイル | 処理 |
|---|---|
| `docker_detector.py` | Docker container から DB 種別、host/port、credential 候補を検出する。 |
| `__init__.py` | discovery package 初期化。 |

##### `discovery/cloud/`

| ファイル | 処理 |
|---|---|
| `base.py` | cloud provider 共通 Protocol/data model。 |
| `registry.py` | AWS/Azure/GCP/mock cloud provider 登録。 |
| `mock.py` | mock cloud discovery provider。 |
| `__init__.py` | cloud package 初期化。 |
| `aws/cache.py` | AWS discovery cache 読込/保存/削除。 |
| `aws/provider.py` | AWS CLI/RDS/Redshift discovery と connection config 化。 |
| `aws/__init__.py` | AWS package 初期化。 |
| `azure/cache.py` | Azure subscription/server/database cache。 |
| `azure/cli.py` | `az` CLI 実行、login/account/subscription 取得。 |
| `azure/discovery.py` | Azure SQL server/database discovery と config 化。 |
| `azure/firewall.py` | Azure SQL firewall error 解析と rule 追加。 |
| `azure/models.py` | Azure discovery 用 dataclass/model。 |
| `azure/provider.py` | Azure cloud provider 実装。 |
| `azure/__init__.py` | Azure package 初期化。 |
| `gcp/cache.py` | GCP discovery cache。 |
| `gcp/provider.py` | GCP Cloud SQL discovery と config 化。 |
| `gcp/__init__.py` | GCP package 初期化。 |

#### `providers/` 共通ファイル

| ファイル | 処理 |
|---|---|
| `adapter_provider.py` | adapter と schema helper を組み合わせる provider 基底/補助。 |
| `adapters/base.py` | DB adapter の共通 interface、cursor/row 正規化、metadata API。 |
| `adapters/__init__.py` | adapter package 初期化。 |
| `catalog.py` | 利用可能 DB provider の一覧情報。 |
| `config_service.py` | provider schema と saved config の補完/検証。 |
| `docker.py` | Docker detected config と provider 情報の対応。 |
| `driver.py` | driver import 可否、missing driver、install hint の解決。 |
| `exceptions.py` | provider/driver/connection 関連例外。 |
| `explorer_nodes.py` | provider が Explorer に出す node 種別定義。 |
| `metadata.py` | DB metadata model。 |
| `model.py` | `DatabaseProvider`、schema field、capability の中心 model。 |
| `registry.py` | provider registry と db type 解決。 |
| `schema_catalog.py` | schema capability と object folder 定義。 |
| `schema_helpers.py` | schema SQL 実行、identifier quoting、folder item 整形の共通 helper。 |
| `tls.py` | TLS/SSL option の provider 別変換。 |
| `validation.py` | connection config/schema validation。 |
| `__init__.py` | provider package 初期化。 |

#### DB 別 provider ディレクトリ

各 `sqlit/domains/connections/providers/<db>/` は同じ責務分割です。

| ファイル | 処理 |
|---|---|
| `<db>/provider.py` | DB 種別の表示名、schema fields、default port、driver 名、connection config から adapter を作る処理。 |
| `<db>/adapter.py` | DB-API/driver 固有の connect、execute、cursor、autocommit、database override、例外変換。 |
| `<db>/schema.py` | database/schema/table/view/index/procedure/column など metadata を DB 固有 SQL で取得する。 |
| `<db>/base.py` | 一部 DB family（例: MySQL 系、PostgreSQL 系）で provider 間共有する基底 adapter/schema helper。 |
| `<db>/__init__.py` | DB provider package 初期化。 |

対象 DB は `athena`, `bigquery`, `clickhouse`, `cockroachdb`, `d1`, `db2`, `duckdb`, `firebird`, `flight`, `hana`, `impala`, `mariadb`, `motherduck`, `mssql`, `mysql`, `oracle`, `oracle_legacy`, `osquery`, `postgresql`, `presto`, `redshift`, `snowflake`, `spanner`, `sqlite`, `supabase`, `surrealdb`, `teradata`, `trino`, `turso` です。

#### `ui/`

| ファイル | 処理 |
|---|---|
| `connection_error_handlers.py` | 接続エラーを driver install、firewall、認証失敗などに分類して UI 応答する。 |
| `connection_focus.py` | 接続 form の focus 移動。 |
| `connection_form.py` | provider schema から connection form を構築する。 |
| `connection_test_controller.py` | form 上の接続テスト実行と結果表示。 |
| `driver_status.py` | driver install 済み/不足の状態 model。 |
| `driver_status_controller.py` | driver status の更新、install flow 起動。 |
| `field_widgets.py` | schema field 種別から Textual input/select を作る。 |
| `fields.py` | 接続 form field の表示/値変換 helper。 |
| `mixins/connection.py` | 接続 picker/form 起動、接続/切断/再接続 action、current session 更新。 |
| `mixins/__init__.py` | connection mixin export。 |
| `restart_cache.py` | driver install 後 restart 用に screen/config 状態を保存・復元する。 |
| `validation.py` | UI 入力値の validation。 |
| `validation_ui_binder.py` | validation 結果を field widget 表示に反映する。 |
| `__init__.py` | connection UI package 初期化。 |

##### `ui/screens/`

| ファイル | 処理 |
|---|---|
| `azure_firewall.py` | Azure firewall rule 追加確認/実行 screen。 |
| `connection.py` | connection form screen。 |
| `connection_styles.py` | connection UI 用 style 定数。 |
| `folder_input.py` | folder path 入力 screen。 |
| `install_progress.py` | driver install progress screen。 |
| `package_setup.py` | missing package setup screen。 |
| `password_input.py` | password 入力 modal。 |
| `__init__.py` | screens package 初期化。 |

##### `ui/screens/connection_picker/`

| ファイル | 処理 |
|---|---|
| `screen.py` | saved/docker/cloud 接続を選ぶ connection picker screen。 |
| `state.py` | picker の selected tab、loading、filter、選択状態。 |
| `view.py` | picker の Textual widget 構築と描画更新。 |
| `constants.py` | tab 名、表示文言など定数。 |
| `shortcuts.py` | picker 内 shortcut と action。 |
| `cloud_nodes.py` | cloud discovery 結果を tree/list node に変換する。 |
| `controllers/cloud.py` | cloud tab の refresh、load、connect action。 |
| `controllers/docker.py` | docker tab の refresh、connect action。 |
| `controllers/__init__.py` | controller package 初期化。 |
| `tabs/cloud.py` | cloud tab view/model。 |
| `tabs/connections.py` | saved connections tab view/model。 |
| `tabs/docker.py` | docker tab view/model。 |
| `tabs/__init__.py` | tabs package 初期化。 |
| `cloud_providers/base.py` | picker 用 cloud provider UI adapter 基底。 |
| `cloud_providers/aws.py` | AWS picker 表示・操作。 |
| `cloud_providers/azure.py` | Azure picker 表示・操作。 |
| `cloud_providers/gcp.py` | GCP picker 表示・操作。 |
| `cloud_providers/utils.py` | cloud provider UI 共通 helper。 |
| `cloud_providers/__init__.py` | cloud provider UI package 初期化。 |
| `__init__.py` | picker package 初期化。 |

### 5.8 `sqlit/domains/explorer/`

| ファイル | 処理 |
|---|---|
| `app/schema_service.py` | provider schema API を呼び、database/table/view/index/procedure/column を Explorer 向けに取得する。 |
| `domain/tree_nodes.py` | Explorer tree node の path、kind、metadata、表示名を定義する。 |
| `state/tree_focused.py` | Explorer focus 時の基本 action。 |
| `state/tree_filter_active.py` | tree filter 入力中の action。 |
| `state/tree_multi_select.py` | 複数接続選択状態の action。 |
| `state/tree_on_connection.py` | connection node 選択時の action。 |
| `state/tree_on_database.py` | database node 選択時の action。 |
| `state/tree_on_folder.py` | Tables/Views など folder node 選択時の action。 |
| `state/tree_on_object.py` | generic object node 選択時の action。 |
| `state/tree_on_table.py` | table/view node 選択時の action。 |
| `state/tree_visual_mode.py` | Explorer visual selection 状態。 |
| `state/__init__.py` | explorer state export。 |
| `ui/mixins/tree.py` | tree focus、node action、expand/collapse、refresh、metadata shortcut。 |
| `ui/mixins/tree_filter.py` | table/tree filter、regex/fuzzy、未ロード folder のロード連携。 |
| `ui/mixins/tree_labels.py` | node label と markup escape。 |
| `ui/mixins/tree_schema.py` | schema load worker、cache、ロード完了反映。 |
| `ui/mixins/__init__.py` | tree mixin export。 |
| `ui/tree/builder.py` | connection/database/schema tree の初期構築。 |
| `ui/tree/db_switching.py` | database override / current database 切替。 |
| `ui/tree/expansion_state.py` | 展開済み path と cursor 復元。 |
| `ui/tree/loaders.py` | folder/database/table children の非同期ロード。 |
| `ui/tree/object_info.py` | table columns/indexes など object info を results に表示する。 |
| `ui/tree/schema_render.py` | schema metadata を Tree node に描画する。 |
| `ui/tree/__init__.py` | tree helper package 初期化。 |
| `__init__.py` | explorer package 初期化。 |

### 5.9 `sqlit/domains/query/`

#### `app/`

| ファイル | 処理 |
|---|---|
| `alerts.py` | destructive SQL など query 実行前 alert 判定。 |
| `cancellable.py` | cancel 可能 query handle の抽象。 |
| `multi_statement.py` | SQL script を statement 単位に分割し、制限を適用する。 |
| `query_runner.py` | executor を使って statement を実行し、rows/columns/error を返す。 |
| `query_service.py` | query 実行の orchestration。履歴、transaction、cancel、複数 statement を扱う。 |
| `transaction.py` | autocommit/transaction state と commit/rollback 実行。 |
| `__init__.py` | query app package 初期化。 |

#### `cli/`

| ファイル | 処理 |
|---|---|
| `commands.py` | `sqlit query` の実装。接続、SQL/file 入力、CSV/JSON/table 出力。 |
| `__init__.py` | query CLI package 初期化。 |

#### `completion/`

| ファイル | 処理 |
|---|---|
| `completion.py` | SQL 文脈から補完候補をまとめる facade。 |
| `core.py` | token 解析、alias/table/column 候補の基本ロジック。 |
| `keywords.py` | SQL keyword 候補。 |
| `alter_table.py` | `ALTER TABLE` 用補完。 |
| `create_index.py` | `CREATE INDEX` 用補完。 |
| `create_table.py` | `CREATE TABLE` 用補完。 |
| `create_view.py` | `CREATE VIEW` 用補完。 |
| `delete.py` | `DELETE` 用補完。 |
| `drop.py` | `DROP` 用補完。 |
| `insert.py` | `INSERT` 用補完。 |
| `truncate.py` | `TRUNCATE` 用補完。 |
| `update.py` | `UPDATE` 用補完。 |
| `__init__.py` | completion package 初期化。 |

#### `editing/`

| ファイル | 処理 |
|---|---|
| `clipboard.py` | query editor 内 clipboard/yank/paste 操作。 |
| `comments.py` | line/block comment toggle。 |
| `deletion.py` | Vim 風 delete/change 処理。 |
| `operators.py` | Vim operator pending、operator + motion の適用。 |
| `text_objects.py` | quote/bracket/word/line など text object 選択。 |
| `types.py` | edit range、motion result など型定義。 |
| `undo_history.py` | query text の undo/redo stack。 |
| `__init__.py` | editing package 初期化。 |
| `motions/basic.py` | h/j/k/l、行頭/行末など基本 motion。 |
| `motions/brackets.py` | bracket 対応移動。 |
| `motions/common.py` | motion 共通 helper。 |
| `motions/lines.py` | 行単位 motion。 |
| `motions/registry.py` | key から motion handler を引く registry。 |
| `motions/search.py` | 文字検索 motion。 |
| `motions/words.py` | word forward/backward/end motion。 |
| `motions/__init__.py` | motions package 初期化。 |

#### `state/`

| ファイル | 処理 |
|---|---|
| `autocomplete_active.py` | autocomplete dropdown 表示中の action。 |
| `query_focused.py` | query pane focus 時の action。 |
| `query_insert.py` | Vim insert mode の action。 |
| `query_normal.py` | Vim normal mode の action。 |
| `query_visual.py` | Vim visual char mode の action。 |
| `query_visual_line.py` | Vim visual line mode の action。 |
| `__init__.py` | query state export。 |

#### `store/`

| ファイル | 処理 |
|---|---|
| `history.py` | 接続別 query history の保存/検索。 |
| `memory.py` | test/mock 用 in-memory history。 |
| `starred.py` | starred query の保存/削除/一覧。 |
| `__init__.py` | query store package 初期化。 |

#### `ui/`

| ファイル | 処理 |
|---|---|
| `mixins/query.py` | query editor の基本 action、mode 切替、入力処理。 |
| `mixins/query_execution.py` | execute/cancel/transaction action と worker 連携。 |
| `mixins/query_results.py` | results pane への反映、last result 更新。 |
| `mixins/query_constants.py` | query UI 定数。 |
| `mixins/query_editing_common.py` | editor 共通編集 helper。 |
| `mixins/query_editing_cursor.py` | cursor 移動と selection 更新。 |
| `mixins/query_editing_clipboard.py` | yank/paste/copy action。 |
| `mixins/query_editing_comments.py` | comment toggle action。 |
| `mixins/query_editing_operators.py` | Vim operator action。 |
| `mixins/query_editing_selection.py` | selection helper。 |
| `mixins/query_editing_undo.py` | undo/redo action。 |
| `mixins/query_editing_visual.py` | visual mode action。 |
| `mixins/query_editing_visual_line.py` | visual line mode action。 |
| `mixins/autocomplete.py` | autocomplete 表示/非表示、候補選択、適用。 |
| `mixins/autocomplete_schema.py` | schema cache indexing と補完用 table/column 収集。 |
| `mixins/autocomplete_suggestions.py` | 入力文脈から suggestion list を生成する。 |
| `mixins/__init__.py` | query mixin export。 |
| `screens/char_pending_menu.py` | Vim の `f`/`t` など文字待ちメニュー。 |
| `screens/query_history.py` | query history 検索・選択 screen。 |
| `screens/text_object_menu.py` | text object 選択 menu。 |
| `screens/__init__.py` | query screen package 初期化。 |
| `__init__.py` | query UI package 初期化。 |

### 5.10 `sqlit/domains/results/`

| ファイル | 処理 |
|---|---|
| `formatters.py` | CLI/TUI で使う result の CSV/JSON/table 形式変換。 |
| `state/results_focused.py` | results pane focus 時の action。 |
| `state/results_filter_active.py` | results filter 入力中の action。 |
| `state/value_view_active.py` | value view 表示中の action。 |
| `state/__init__.py` | results state export。 |
| `ui/mixins/results.py` | results table navigation、cell copy/yank、column picker、save、value view。 |
| `ui/mixins/results_filter.py` | results row filter、fuzzy search、filter input の表示制御。 |
| `ui/mixins/__init__.py` | results mixin export。 |
| `ui/screens/column_picker.py` | 表示 column 選択 screen。 |
| `ui/screens/save_file.py` | results 保存先選択 screen。 |
| `ui/screens/value_view.py` | cell 値の詳細表示 screen。 |
| `ui/screens/__init__.py` | results screen package 初期化。 |
| `__init__.py` | results package 初期化。 |

### 5.11 `sqlit/domains/process_worker/`

| ファイル | 処理 |
|---|---|
| `app/process_worker.py` | 別プロセス側の worker main loop。要求を受け、driver/import/接続系処理を実行する。 |
| `app/process_worker_client.py` | 親プロセス側 client。worker 起動、要求送信、応答受信、終了処理。 |
| `app/support.py` | worker protocol、pickle safety、message 型などの補助。 |
| `app/__init__.py` | process worker app package 初期化。 |
| `ui/mixins/process_worker_lifecycle.py` | Textual app lifecycle に worker 起動/終了を結びつける。 |
| `ui/mixins/__init__.py` | process worker UI mixin export。 |
| `ui/__init__.py` | process worker UI package 初期化。 |
| `__init__.py` | process worker package 初期化。 |

## 6. 機能からみたコードの逆引き

| やりたいこと / 機能 | 主に見る場所 |
|---|---|
| CLI 引数や entrypoint を変える | `sqlit/cli.py`, `sqlit/domains/connections/cli/`, `sqlit/domains/query/cli/` |
| Textual app の全体構成を変える | `sqlit/domains/shell/app/main.py` |
| 起動時の自動接続や mock 適用を変える | `sqlit/domains/shell/app/startup_flow.py`, `sqlit/shared/app/runtime.py` |
| 新しい keybinding を追加する | `sqlit/core/keymap.py`, `sqlit/core/leader_commands.py`, 関連 `domains/*/state/*.py`, 対応 `action_*` mixin |
| action が効く状態を変える | `sqlit/domains/shell/state/machine.py`, `sqlit/core/state_base.py`, `sqlit/domains/*/state/*.py` |
| 新しい DB provider を追加する | `sqlit/domains/connections/providers/<db>/provider.py`, `adapter.py`, `schema.py`, `registry.py`, `catalog.py`, tests |
| DB 接続 form の項目を変える | `sqlit/domains/connections/providers/<db>/provider.py`, `sqlit/domains/connections/domain/config.py`, `sqlit/domains/connections/ui/connection_form.py` |
| driver install の挙動を変える | `sqlit/domains/connections/app/install_strategy.py`, `installer.py`, `ui/screens/install_progress.py` |
| 認証情報保存を変える | `sqlit/domains/connections/app/credentials.py`, `domain/passwords.py`, `store/connections.py` |
| SSH tunnel を変える | `sqlit/domains/connections/app/tunnel.py`, `domain/config.py` |
| Docker 自動検出を変える | `sqlit/domains/connections/discovery/docker_detector.py`, `providers/docker.py`, `ui/screens/connection_picker/controllers/docker.py` |
| Cloud discovery を変える | `sqlit/domains/connections/discovery/cloud/`, `app/cloud_actions.py`, `ui/screens/connection_picker/cloud_providers/` |
| Explorer tree の構造を変える | `sqlit/domains/explorer/domain/tree_nodes.py`, `ui/tree/builder.py`, `ui/tree/schema_render.py` |
| Explorer の遅延ロードを変える | `sqlit/domains/explorer/ui/tree/loaders.py`, `ui/mixins/tree_schema.py`, `app/schema_service.py` |
| Table filter / tree filter を変える | `sqlit/domains/explorer/ui/mixins/tree_filter.py`, `state/tree_filter_active.py`, `shared/ui/widgets_filter.py` |
| table columns/indexes 表示を変える | `sqlit/domains/explorer/ui/tree/object_info.py`, provider の `schema.py` |
| SQL 補完を変える | `sqlit/domains/query/completion/`, `ui/mixins/autocomplete*.py` |
| Vim 風編集を変える | `sqlit/domains/query/editing/`, `ui/mixins/query_editing_*.py`, `state/query_*.py` |
| query history/starred を変える | `sqlit/domains/query/store/history.py`, `starred.py`, `ui/screens/query_history.py` |
| クエリ分割や実行を変える | `sqlit/domains/query/app/multi_statement.py`, `query_service.py`, `query_runner.py`, `transaction.py` |
| 結果テーブル表示を変える | `sqlit/domains/results/ui/mixins/results.py`, `shared/ui/widgets_tables.py`, `widgets_stacked_results.py` |
| 結果フィルタを変える | `sqlit/domains/results/ui/mixins/results_filter.py`, `shared/ui/widgets_filter.py` |
| CSV/JSON 出力を変える | `sqlit/domains/results/formatters.py`, `sqlit/domains/query/cli/commands.py` |
| テーマを追加/変更する | `sqlit/domains/shell/app/themes.py`, `theme_manager.py`, `ui/screens/theme.py` |
| debug / watchdog を見る | `sqlit/shared/core/debug_events.py`, `sqlit/domains/shell/app/commands/debug.py`, `watchdog.py` |
| process worker を変える | `sqlit/domains/process_worker/app/`, `sqlit/domains/shell/app/commands/worker.py` |
| 共通 widget を追加する | `sqlit/shared/ui/widgets_*.py`, 必要な Protocol/mixin |

## 7. 変更時の目安

- UI 操作を追加する場合は、`action_*` メソッド、`keymap`、対象 state、footer/help の順で考える。
- DB 種別差分は provider 配下に閉じ込める。UI 側に DB 名分岐を増やす前に、provider/schema capability で表現できないか確認する。
- Textual widget が host app の属性に触る場合は、`shared/ui/protocols/` に Protocol を追加して依存を明示する。
- 永続化は `shared/core/store.JSONFileStore` を通す。テストしやすいよう memory store も必要に応じて用意する。
- 長い DB 処理や driver import は UI thread に置かず、Textual worker または `process_worker` を使う。
