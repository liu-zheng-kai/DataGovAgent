# DataGovAgent

[English](./README.md) | [中文](./README.zh.md) | 日本語

DataGovAgent は、FastAPI、SQLAlchemy、MySQL、SQLite フォールバック、および OpenAI 互換ツール呼び出しを使って構築されたローカル向けメタデータガバナンス / 追跡プロトタイプです。

## 概要

DataGovAgent の基本方針:

- 各データシステムがメタデータを共通スキーマへ書き込む
- サービス層とツール層は canonical schema のみを参照する
- LLM は DB に直接触れず、ツール経由でガバナンス質問に答える
- プロンプト戦略、管理 UI、監査、運用拡張を独立して進化させやすい

## アーキテクチャ

![Architecture Diagram](./docs/images/architecture_flow.png)

### 画面例

#### 1. 管理コンソール
![Admin Console Home](./docs/images/admin_overview.png)

#### 2. チャット体験
![Chat Experience](./docs/images/chat_effect.png)

#### 3. プロンプトテンプレート管理
![Prompt Template Management](./docs/images/prompt_template_effect.png)

### 主要モジュール

#### 1. Agent オーケストレーション
- コンポーネント: `MetadataAgent`
- ファイル: `app/agent/llm_agent.py`
- 役割: 1 回の質問応答フローを制御し、DB を直接参照しない

#### 2. Tools レイヤー
- コンポーネント: `TOOL_DEFINITIONS`、`MetadataToolRegistry`
- ファイル: `app/agent/tooling.py`、`app/tools/registry.py`
- 役割: モデル呼び出しを標準化された業務関数へ変換し、サービス層へ渡す

#### 3. Metadata Store
- コンポーネント: DB と `app/models/*`
- 役割: アセット、系譜、実行状態、SLA、影響分析、レポート、管理データの single source of truth

#### 4. Prompt 管理
- コンポーネント: `PromptTemplateRecord`、`ToolPromptBindingRecord`、`/api/admin/prompt-templates*`
- 役割: プロンプトをコードから分離し、シーン別デフォルト、版管理、プレビュー、調整を可能にする

## クイックスタート

### 1. 前提条件

- Python `3.11+`
- MySQL `8+`
- 任意: OpenAI 互換 API Key

### 2. 仮想環境作成

```bash
cd D:\codexAIcode\metadata_governance_poc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数設定

`.env.example` を `.env` にコピーし、次を確認します。

```env
app_name=DataGovAgent
app_public_base_url=http://127.0.0.1:8000
database_url=mysql+pymysql://root:root@localhost:3306/metadata_governance
database_fallback_url=sqlite:///./metadata_governance.db
openai_auth_mode=api_key
openai_api_key=your_openai_key
```

### 4. 初期化と起動

```bash
python -m app.seed.seed_data
uvicorn app.main:app --reload --port 8000
```

起動後:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Admin: `http://127.0.0.1:8000/admin`

## よく使う API 例

```bash
curl http://127.0.0.1:8000/assets/customer_profile
curl "http://127.0.0.1:8000/runtime/failed?domain=Customer"
curl http://127.0.0.1:8000/sla/risks
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"Which teams are impacted by silver.customer_contact failure?\"}"
```

## 補足

- 既定のメイン README は英語版です: [README.md](./README.md)
- API 一覧、トラブルシュート、VS Code 開発フローの完全版は英語版を参照してください
- 既存コードとの整合性のため、ワークスペース上のディレクトリ名は `metadata_governance_poc` のままです
