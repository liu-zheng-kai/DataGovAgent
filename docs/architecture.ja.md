# DataGovAgent アーキテクチャ設計

[English](./architecture.md) | [中文](./architecture.zh.md) | 日本語

このドキュメントは、DataGovAgent をローカルなメタデータガバナンス PoC から Azure 指向のガバナンスエンジンへ拡張していく際の目標アーキテクチャを説明します。現在の実装を補足し、Metadata、Runtime、Business Context をどのように一体でモデル化するかを整理したものです。

## 目次

- [1. 目的](#1-目的)
- [2. 中核となる設計思想](#2-中核となる設計思想)
- [2.1 三層モデル](#21-三層モデル)
- [3. Metadata 取得戦略](#3-metadata-取得戦略)
- [4. Runtime データ戦略](#4-runtime-データ戦略)
- [5. 中核データモデル](#5-中核データモデル)
- [6. Lineage モデリング](#6-lineage-モデリング)
- [7. SLA 設計](#7-sla-設計)
- [8. Synapse モデリング原則](#8-synapse-モデリング原則)
- [9. Business Context の取り込み](#9-business-context-の取り込み)
- [10. システム全体アーキテクチャ](#10-システム全体アーキテクチャ)
- [11. 目指す最終形](#11-目指す最終形)
- [12. 推奨ロードマップ](#12-推奨ロードマップ)
- [13. 一文で言うと](#13-一文で言うと)

## 1. 目的

Azure Data Factory（ADF）、Azure Synapse、Cosmos DB を中心とした Azure データ基盤向けのデータガバナンスプラットフォームを構築すること。

主要な機能:

- 統一メタデータ管理
- 準リアルタイムの実行監視
- クロスプラットフォームのリネージ分析
- SLA とデータ健全性の評価
- ビジネスコンテキストの関連付け
- Agent / LLM から扱いやすい問い合わせと意思決定支援

## 2. 中核となる設計思想

### 2.1 三層モデル

このシステムで最も重要な抽象は三層モデルです。

#### 1. Metadata Layer

リソースが何であるかを表します。

主なソース:

- ADF、Synapse、Cosmos の REST API
- JSON、ARM、Bicep、Terraform などのリポジトリ定義

主な内容:

- pipeline、dataset、dataflow
- notebook、table、container
- 構造依存関係とリネージ定義

#### 2. Runtime Layer

リソースが実際にどう動いているかを表します。

主なソース:

- 近リアルタイム取得用の ADF Query Runs API
- 履歴運用データ用の Log Analytics

主な内容:

- pipeline run、activity run
- status、duration、retry、error
- parameters、input、output、execution context

#### 3. Business Context Layer

そのリソースがビジネス上何を意味するかを表します。

主なソース:

- 共有 Excel やスプレッドシートのマッピング
- Azure DevOps の PBI / work item
- チームが管理する ownership カタログ

主な内容:

- business domain
- owner と responsible team
- 業務目的と criticality
- 変更起点と関連する配信・開発項目

## 3. Metadata 取得戦略

### 3.1 二つの取り込み経路

DataGovAgent は、相補的な二つの経路でメタデータを取得するべきです。

#### 経路 A: Repo-Based

設計時の desired state を表します。

ソース:

- GitHub または Azure DevOps repository
- JSON、ARM、Bicep、Terraform

特徴:

- バージョン管理できる
- 差分確認しやすい
- あるべき状態を示す

#### 経路 B: API-Based

デプロイ済み状態と運用状態を表します。

ソース:

- Azure REST API
- Azure SDK

特徴:

- Azure 上の現在の実態を反映する
- 実行時関連の属性も含められる
- 今どうなっているかを示す

### 3.2 必須の三状態モデル

desired、deployed、runtime の違いは明確に保持する必要があります。

| 状態 | 意味 |
| --- | --- |
| `desired` | ソース管理に定義された状態 |
| `deployed` | Azure に実際にデプロイされた状態 |
| `runtime` | 実行中に観測された状態 |

この分離は、ドリフト検知、運用デバッグ、監査にとって重要です。

## 4. Runtime データ戦略

### 4.1 二系統の実行データ収集

#### Hot チャネル: 準リアルタイム

ソース:

- ADF Query Runs API

頻度:

- 規模と SLA 感度に応じて 1 分から 5 分ごとにポーリング

保存先の例:

- `pipeline_runs_hot`
- `activity_runs_hot`

主な用途:

- ダッシュボード
- Agent によるリアルタイム問い合わせ
- インシデント分析

#### Cold チャネル: 履歴

ソース:

- Log Analytics

主な用途:

- SLA 統計
- 傾向分析
- パラメータと実行監査

## 5. 中核データモデル

### 5.1 統一 Asset モデル

すべての技術オブジェクトは、共通の `asset` 抽象へ正規化すべきです。

例:

- pipeline
- dataset
- dataflow
- notebook
- table
- cosmos container

これにより、将来 Azure サービスが増えてもガバナンスモデルを安定して保てます。

### 5.2 推奨コアテーブル

#### Metadata

- `assets`
- `asset_properties`
- `asset_versions`
- `asset_dependencies`

#### Runtime

- `pipeline_runs_hot`
- `pipeline_runs_history`
- `activity_runs_hot`
- `activity_runs_history`
- `asset_runtime_status`
- `runtime_events`

#### Governance

- `sla_definitions`
- `sla_evaluations`
- `business_impacts`

#### Ingestion

- `ingestion_jobs`
- `raw_metadata_snapshots`
- `source_sync_state`

## 6. Lineage モデリング

リネージは次のようなクロスプラットフォーム依存を表現できる必要があります。

```text
ADF Pipeline
   ↓ calls
Synapse Notebook
   ↓ produces
Synapse Table
   ↓ publishes
Cosmos Container
```

推奨 dependency type:

- `calls`
- `reads_from`
- `writes_to`
- `publishes_to`
- `triggers`

このモデルは、技術的な実行順序とビジネス影響の両方を保持すべきです。

## 7. SLA 設計

### 7.1 重要な前提

ADF にはネイティブなビジネス SLA モデルがありません。

そのため SLA は複数ソースから段階的に導出する必要があります。

#### 優先度 1: Manual SLA

ビジネス側で明示的に定義された期待値を最優先とします。

#### 優先度 2: Trigger-Derived SLA

スケジュールトリガーから期待実行時間帯を推定できます。

#### 優先度 3: Historical SLA

平均値、パーセンタイル、過去の運用パターンをフォールバックとして使います。

推奨優先順位:

```text
manual SLA > trigger SLA > historical SLA
```

### 7.2 SLA を紐付ける場所

SLA は pipeline のみに付与するのではなく、table や container などのデータ資産へ優先的に紐付けるべきです。

その方がビジネス影響分析に適しています。

## 8. Synapse モデリング原則

通常、Synapse をオーケストレーション層として扱うべきではありません。

推奨される考え方:

- ADF は主要な orchestration layer
- Synapse は呼び出される compute / transformation layer

例:

```text
ADF Pipeline → Synapse Notebook → Table → Cosmos
```

## 9. Business Context の取り込み

### 9.1 Spreadsheet / Excel Mapping

役割:

- ビジネス概念と技術資産の対応付け
- domain、owner、criticality の付加

### 9.2 Azure DevOps PBI 連携

役割:

- 変更起点の把握
- ownership と作業管理コンテキストの補強
- 技術変更を feature、bug、計画作業に結び付ける

### 9.3 この層の価値

この層によって次のような問いに答えられます。

- どの業務ドメインに影響があるか
- 誰が責任を持つか
- なぜ変更されたのか
- どの優先度で対応すべきか

## 10. システム全体アーキテクチャ

```text
[ Business Layer ]
   Excel / PBI / Ownership Mapping
        ↓
[ Metadata Layer ]
   Assets / Properties / Lineage
        ↓
[ Runtime Layer ]
   Runs / Events / SLA Evaluations
        ↓
[ Agent Layer ]
   Tools / Retrieval / Reasoning / Decision Support
```

## 11. 目指す最終形

このシステムの最終形は単なる metadata catalog ではありません。

次のことができるガバナンスエンジンです。

- リアルタイム運用問い合わせへの回答
- 自動リネージ分析
- SLA リスク監視
- ビジネス影響の説明
- 適切な owner へのルーティング
- 信頼できる構造化データに基づく LLM 推論支援

## 12. 推奨ロードマップ

### Phase 1

- ADF metadata と run API の接続
- runtime polling の実装
- 最小限の canonical metadata layer の構築

### Phase 2

- lineage モデルと dependency graph の構築
- SLA 定義と評価ロジックの追加

### Phase 3

- 表計算ベースの business mapping 連携

### Phase 4

- Azure DevOps PBI と ownership context の連携

### Phase 5

- agent 推論と意思決定ワークフローの強化

## 13. 一文で言うと

DataGovAgent は、Azure データシステムの定義、実行、ビジネス上の意味を単一のガバナンスモデルに統合し、自動分析と意思決定支援を可能にすることを目指します。
