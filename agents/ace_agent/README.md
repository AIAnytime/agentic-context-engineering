# ACE Agent 内部仕様 (Agentic Context Engineering)

## 概要

ACE は `StateInitializer→Generator→Reflector→Curator` を 1 周期として、生成・内省・キュレーション結果を `app:playbook` に反映する反復学習エージェントです。各サブエージェントは Pydantic スキーマで入出力を厳格管理し、`Playbook` はタグ統計とデルタ適用で継続改善します。起動/セットアップの手順はリポジトリ直下の `README.md` を参照してください。

---

## アーキテクチャ

- `StateInitializer`（`BaseAgent`）
  - 入力: `user_content`
  - 出力: `state_delta`（`user_query`, `app:playbook` 初期化, `ground_truth=None` 明示）
- `Generator`（`Agent`）
  - モデル: `Config.generator_model`
  - 出力スキーマ: `GeneratorOutput(reasoning: list[str], bullet_ids: list[str], final_answer: str)`
  - 状態反映: `session.state['generator_output']`
- `Reflector`（`SequentialAgent` = `reflector_` + `tag_bullet`）
  - モデル: `Config.reflector_model`
  - 出力スキーマ: `Reflection(...)` と `bullet_tags: list[BulletTag]`
  - `tag_bullet` が `Playbook.update_bullet_tag` を呼び、タグ統計を加算
  - 状態反映: `session.state['reflector_output']`, 更新済 `app:playbook`
- `Curator`（`SequentialAgent` = `curator_` + `playbook_updater`）
  - モデル: `Config.curator_model`
  - 出力スキーマ: `DeltaBatch(reasoning, operations: DeltaOperation[])`
  - `playbook_updater` が `Playbook.apply_delta` を適用
  - 状態反映: 更新済 `app:playbook`, `session.state['curator_output']`

実行フロー:

```text
StateInitializer → Generator → Reflector(reflector_→tag_bullet) → Curator(curator_→playbook_updater)
```

エクスポート:

- `agents/ace_agent/__init__.py` で `root_agent` を公開（実体は `ace_iteration`）。

---

## 状態キー（session.state）

- `user_query`: 最新ユーザー入力
- `app:playbook`: `Playbook` の辞書表現（セクション/ID 管理とタグ統計を含む）
- `generator_output`: `GeneratorOutput`
- `reflector_output`: `Reflection`（`bullet_tags` 含む）
- `curator_output`: `DeltaBatch`
- `ground_truth`（任意）: 期待解

---

## データモデル（抜粋）

- `schemas/playbook.py`
  - `Bullet(id, section, content, helpful, harmful, neutral, created_at, updated_at)`
  - `Playbook`
    - 主要操作: `add_bullet`, `update_bullet`, `remove_bullet`, `update_bullet_tag`, `apply_delta`
    - 直列化: `to_dict`/`from_dict`/`dumps`/`loads`
    - 提示用: `as_prompt()`, `stats()`
- `schemas/delta.py`
  - `DeltaOperation(type: "ADD"|"UPDATE"|"REMOVE", section, content?, bullet_id?)`
  - `DeltaBatch(reasoning: str, operations: List[DeltaOperation])`

---

## 設定 / 実行（詳細はルート `README.md` 参照）

- `config.py`
  - `agent_dir`: エージェントディレクトリ（既定: 本リポの `agents`）
  - `serve_web_interface`/`reload_agents`: Web UI 提供とエージェント自動リロード
  - `generator_model`/`reflector_model`/`curator_model`: 既定は `gemini-2.5-flash`
- `main.py`
  - FastAPI アプリを生成（詳細な起動コマンドや依存解決はルート `README.md` のクイックスタートを参照）

---

## インタラクションと出力の例（概念）

1) ユーザーがクエリを送信すると `user_query` が設定され、`app:playbook` が未定義なら初期化
2) `Generator` が `GeneratorOutput` を生成（reasoning/bullet_ids/final_answer）
3) `Reflector` が `Reflection` を生成し、`tag_bullet` により bullet にタグ加算
4) `Curator` が `DeltaBatch` を返し、`playbook_updater` が ADD/UPDATE/REMOVE を適用

---

## 変更容易性のポイント

- モデル切替: `config.py` の各モデル名を変更
- 収集強化: `Playbook.as_prompt()` をプロンプトに注入する設計へ拡張可能
- 自動整理: `Playbook.stats()` とタグ統計に基づくメンテナンスジョブの追加

---

## 既知の制約

- ADK の依存関係と実行環境が前提
- 外部 API 認証は本リポでは最小限（必要に応じて `.env`/環境変数で拡張）
