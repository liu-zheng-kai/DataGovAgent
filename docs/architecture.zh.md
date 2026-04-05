# DataGovAgent 架构设计文档

[English](./architecture.md) | 中文 | [日本語](./architecture.ja.md)

本文档描述 DataGovAgent 从本地元数据治理 PoC 演进为面向 Azure 生态的数据治理引擎时的目标架构方向。它补充当前实现，并明确 Metadata、Runtime 与 Business Context 三类信息如何统一建模。

## 导航目录

- [1. 项目目标](#1-项目目标)
- [2. 核心设计思想](#2-核心设计思想)
- [2.1 三层模型](#21-三层模型)
- [3. Metadata 获取策略](#3-metadata-获取策略)
- [4. Runtime 数据策略](#4-runtime-数据策略)
- [5. 核心数据模型](#5-核心数据模型)
- [6. Lineage 建模](#6-lineage-建模)
- [7. SLA 设计](#7-sla-设计)
- [8. Synapse 建模原则](#8-synapse-建模原则)
- [9. Business Context 接入](#9-business-context-接入)
- [10. 系统整体架构](#10-系统整体架构)
- [11. 最终定位](#11-最终定位)
- [12. 建议 Roadmap](#12-建议-roadmap)
- [13. 一句话总结](#13-一句话总结)

## 1. 项目目标

构建一个面向 Azure 数据生态的数据治理平台，重点支持 Azure Data Factory（ADF）、Azure Synapse 和 Cosmos DB。

核心能力包括：

- 统一元数据管理
- 近实时运行状态监控
- 跨平台数据血缘分析
- SLA 与数据健康度评估
- 业务语义与上下文关联
- 支持 Agent / LLM 查询与辅助决策

## 2. 核心设计思想

### 2.1 三层模型

系统最关键的抽象是三层模型。

#### 1. Metadata Layer

描述资源“是什么”。

典型来源：

- ADF、Synapse、Cosmos 的 REST API
- Repo 中的 JSON、ARM、Bicep、Terraform 定义

典型内容：

- pipeline、dataset、dataflow
- notebook、table、container
- 结构依赖与血缘定义

#### 2. Runtime Layer

描述资源“实际跑成什么样”。

典型来源：

- ADF Query Runs API，用于近实时轮询
- Log Analytics，用于历史运行数据

典型内容：

- pipeline run、activity run
- status、duration、retry、error
- parameters、input、output、execution context

#### 3. Business Context Layer

描述资源“对业务意味着什么”。

典型来源：

- 共享 Excel 或其他表格映射
- Azure DevOps PBI / work item
- 团队维护的 owner 目录

典型内容：

- business domain
- owner 与 responsible team
- 业务用途与 criticality
- 变更来源与关联交付项

## 3. Metadata 获取策略

### 3.1 双路径采集

DataGovAgent 应通过两条互补路径采集元数据。

#### 路径 A：Repo-Based

表示设计态或目标态。

来源：

- GitHub 或 Azure DevOps repo
- JSON、ARM、Bicep、Terraform

特点：

- 有版本、可审查
- 易于 diff
- 表示“应该是什么”

#### 路径 B：API-Based

表示已部署态与运行态。

来源：

- Azure REST API
- Azure SDK

特点：

- 反映 Azure 当前真实状态
- 可包含运行相关属性
- 表示“现在是什么”

### 3.2 必须支持三态模型

平台必须保留 desired、deployed、runtime 三种状态的区别。

| 状态 | 含义 |
| --- | --- |
| `desired` | 源码库中定义的状态 |
| `deployed` | Azure 中实际部署的状态 |
| `runtime` | 执行时观测到的状态 |

这个区分对于漂移检测、运行排障和治理审计都非常关键。

## 4. Runtime 数据策略

### 4.1 双通道运行时采集

#### 热通道：近实时

来源：

- ADF Query Runs API

频率：

- 根据规模和 SLA 敏感度，每 1 到 5 分钟轮询一次

存储示例：

- `pipeline_runs_hot`
- `activity_runs_hot`

主要用途：

- dashboard
- agent 实时问答
- incident 分析

#### 冷通道：历史数据

来源：

- Log Analytics

主要用途：

- SLA 统计
- 趋势分析
- 参数与执行审计

## 5. 核心数据模型

### 5.1 统一 Asset 模型

所有技术对象都应归一化为统一的 `asset` 抽象。

示例：

- pipeline
- dataset
- dataflow
- notebook
- table
- cosmos container

这样即使未来接入更多 Azure 服务，治理模型也能保持稳定。

### 5.2 推荐核心表

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

## 6. Lineage 建模

血缘必须支持跨平台链路，例如：

```text
ADF Pipeline
   ↓ calls
Synapse Notebook
   ↓ produces
Synapse Table
   ↓ publishes
Cosmos Container
```

推荐 dependency 类型：

- `calls`
- `reads_from`
- `writes_to`
- `publishes_to`
- `triggers`

该模型既要保留技术执行顺序，也要能表达面向业务的下游影响。

## 7. SLA 设计

### 7.1 关键约束

ADF 本身并没有原生的业务 SLA 模型。

因此，SLA 应来自分层推导。

#### 优先级 1：Manual SLA

业务手工定义的期望应作为最高优先级来源。

#### 优先级 2：Trigger-Derived SLA

可以根据调度触发器推导预期执行窗口。

#### 优先级 3：Historical SLA

可基于历史均值、分位数与运行模式作为兜底来源。

推荐优先级：

```text
manual SLA > trigger SLA > historical SLA
```

### 7.2 SLA 挂载原则

SLA 应优先挂在数据资产上，例如 table、container，而不只是挂在 pipeline 上。

这样更适合业务影响分析。

## 8. Synapse 建模原则

默认情况下，不应把 Synapse 建模为编排层。

更合理的解释是：

- ADF 是主编排层
- Synapse 是被编排调用的计算或转换层

例如：

```text
ADF Pipeline → Synapse Notebook → Table → Cosmos
```

## 9. Business Context 接入

### 9.1 Spreadsheet / Excel Mapping

作用：

- 建立业务概念与技术资产之间的映射
- 补充 domain、owner、criticality 等信息

### 9.2 Azure DevOps PBI 接入

作用：

- 记录变更来源
- 补充 ownership 与工作管理上下文
- 将技术变更与 feature、bug、计划项关联

### 9.3 价值

这一层让系统能够回答：

- 影响了哪个业务域？
- 谁负责这个资产？
- 为什么发生这次变更？
- 当前优先级是什么？

## 10. 系统整体架构

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

## 11. 最终定位

系统的目标不只是一个 metadata catalog。

它应该演进为一个治理引擎，能够：

- 回答实时运行问题
- 自动分析血缘
- 监控 SLA 风险
- 解释业务影响
- 自动定位 owner
- 支持基于可信结构化数据的 LLM 推理

## 12. 建议 Roadmap

### Phase 1

- 接入 ADF metadata 与 run API
- 实现 runtime polling
- 建立最小可用 canonical metadata 层

### Phase 2

- 建立 lineage 模型与依赖图
- 增加 SLA 定义与评估逻辑

### Phase 3

- 接入基于表格的业务映射

### Phase 4

- 接入 Azure DevOps PBI 与 ownership 上下文

### Phase 5

- 增强 agent 推理与决策工作流

## 13. 一句话总结

DataGovAgent 的目标，是把 Azure 数据系统的定义、运行和业务语义统一到一个治理模型中，并支持自动分析与辅助决策。
