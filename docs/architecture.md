# DataGovAgent Architecture Design

English | [中文](./architecture.zh.md) | [日本語](./architecture.ja.md)

This document describes the target architecture direction for DataGovAgent as it evolves from a local metadata governance proof of concept into an Azure-oriented governance engine. It complements the current implementation and clarifies how metadata, runtime telemetry, and business context should be unified under one model.

## Table of Contents

- [1. Objective](#1-objective)
- [2. Core Design Principles](#2-core-design-principles)
- [2.1 Three-Layer Model](#21-three-layer-model)
- [3. Metadata Acquisition Strategy](#3-metadata-acquisition-strategy)
- [4. Runtime Data Strategy](#4-runtime-data-strategy)
- [5. Canonical Data Model](#5-canonical-data-model)
- [6. Lineage Modeling](#6-lineage-modeling)
- [7. SLA Design](#7-sla-design)
- [8. Synapse Modeling Principle](#8-synapse-modeling-principle)
- [9. Business Context Integration](#9-business-context-integration)
- [10. Overall System Architecture](#10-overall-system-architecture)
- [11. End-State Positioning](#11-end-state-positioning)
- [12. Suggested Roadmap](#12-suggested-roadmap)
- [13. One-Sentence Summary](#13-one-sentence-summary)

## 1. Objective

Build a data governance platform for the Azure data ecosystem, with primary support for Azure Data Factory (ADF), Azure Synapse, and Cosmos DB.

Core capabilities:

- Unified metadata management
- Near real-time runtime monitoring
- Cross-platform lineage analysis
- SLA and data health evaluation
- Business context association
- Agent and LLM-friendly querying and decision support

## 2. Core Design Principles

### 2.1 Three-Layer Model

The most important abstraction in the system is a three-layer model.

#### 1. Metadata Layer

Describes what a resource is.

Typical sources:

- ADF, Synapse, and Cosmos REST APIs
- Repository definitions such as JSON, ARM, Bicep, or Terraform

Typical content:

- Pipelines, datasets, dataflows
- Notebooks, tables, containers
- Structural dependencies and lineage definitions

#### 2. Runtime Layer

Describes how a resource is actually running.

Typical sources:

- ADF Query Runs API for near real-time polling
- Log Analytics for historical operations data

Typical content:

- Pipeline runs and activity runs
- Status, duration, retry count, and errors
- Parameters, inputs, outputs, and execution context

#### 3. Business Context Layer

Describes what a resource means to the business.

Typical sources:

- Shared Excel or spreadsheet mappings
- Azure DevOps PBIs and work items
- Team-maintained ownership catalogs

Typical content:

- Business domain
- Owner and responsible team
- Business purpose and criticality
- Change source and linked delivery items

## 3. Metadata Acquisition Strategy

### 3.1 Dual-Path Ingestion

DataGovAgent should ingest metadata through two complementary paths.

#### Path A: Repo-Based

Represents the design-time or desired state.

Sources:

- GitHub or Azure DevOps repositories
- JSON, ARM, Bicep, and Terraform

Characteristics:

- Versioned and reviewable
- Easy to diff
- Represents what should exist

#### Path B: API-Based

Represents the deployed and operational state.

Sources:

- Azure REST APIs
- Azure SDKs

Characteristics:

- Reflects the current state in Azure
- Can include runtime-facing attributes
- Represents what exists now

### 3.2 Required Three-State Model

The platform should preserve the difference between desired, deployed, and runtime states.

| State | Meaning |
| --- | --- |
| `desired` | Defined in source control |
| `deployed` | Actually deployed in Azure |
| `runtime` | Observed during execution |

This separation is critical for drift detection, operational debugging, and governance audits.

## 4. Runtime Data Strategy

### 4.1 Dual-Channel Runtime Collection

#### Hot Channel: Near Real-Time

Source:

- ADF Query Runs API

Frequency:

- Poll every 1 to 5 minutes depending on scale and SLA sensitivity

Storage examples:

- `pipeline_runs_hot`
- `activity_runs_hot`

Primary use cases:

- Dashboards
- Agent-assisted operational questions
- Live incident analysis

#### Cold Channel: Historical

Source:

- Log Analytics

Primary use cases:

- SLA statistics
- Trend analysis
- Parameter and execution audit

## 5. Canonical Data Model

### 5.1 Unified Asset Model

All technical objects should be normalized into a common `asset` abstraction.

Examples:

- Pipeline
- Dataset
- Dataflow
- Notebook
- Table
- Cosmos container

This keeps the governance model stable even when new Azure services are added later.

### 5.2 Recommended Core Tables

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

## 6. Lineage Modeling

Lineage must support cross-platform dependency chains such as:

```text
ADF Pipeline
   ↓ calls
Synapse Notebook
   ↓ produces
Synapse Table
   ↓ publishes
Cosmos Container
```

Recommended dependency types:

- `calls`
- `reads_from`
- `writes_to`
- `publishes_to`
- `triggers`

The model should preserve both technical execution order and business-facing downstream impact.

## 7. SLA Design

### 7.1 Key Constraint

ADF does not provide a native business SLA model.

Because of that, SLA should be derived from layered sources.

#### Priority 1: Manual SLA

Business-defined expectations should be treated as the highest-priority source.

#### Priority 2: Trigger-Derived SLA

Scheduled triggers can be used to infer expected execution windows.

#### Priority 3: Historical SLA

Historical averages, percentiles, and operating patterns can be used as a fallback.

Recommended precedence:

```text
manual SLA > trigger SLA > historical SLA
```

### 7.2 SLA Attachment Principle

SLA should be attached primarily to data assets such as tables and containers, not only to pipelines.

That makes the model much more useful for business impact analysis.

## 8. Synapse Modeling Principle

Synapse should not be modeled as the orchestration layer by default.

Recommended interpretation:

- ADF is the primary orchestration layer
- Synapse is a compute or transformation layer invoked by orchestration

Example:

```text
ADF Pipeline → Synapse Notebook → Table → Cosmos
```

## 9. Business Context Integration

### 9.1 Spreadsheet Mapping

Role:

- Map business concepts to technical assets
- Attach domain, owner, and criticality metadata

### 9.2 Azure DevOps PBI Integration

Role:

- Capture change origin
- Link ownership and work management context
- Connect technical changes to features, bugs, and planned work

### 9.3 Why It Matters

This layer enables questions such as:

- Which business domain is impacted?
- Who owns the affected asset?
- Why was this changed?
- What is the operational priority?

## 10. Overall System Architecture

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

## 11. End-State Positioning

The intended end state is not just a metadata catalog.

It is a governance engine that can:

- Answer real-time operational questions
- Analyze lineage automatically
- Monitor SLA risks
- Explain business impact
- Route incidents to the right owner
- Support LLM-driven reasoning on trusted structured data

## 12. Suggested Roadmap

### Phase 1

- Integrate ADF metadata and run APIs
- Implement runtime polling
- Build the minimum canonical metadata layer

### Phase 2

- Build lineage modeling and dependency graphs
- Add SLA definitions and evaluation logic

### Phase 3

- Integrate spreadsheet-based business mapping

### Phase 4

- Integrate Azure DevOps PBI and ownership context

### Phase 5

- Add advanced agent reasoning and decision workflows

## 13. One-Sentence Summary

DataGovAgent should unify the definition, execution, and business meaning of Azure data systems into a single governance model that supports automated analysis and decision-making.
