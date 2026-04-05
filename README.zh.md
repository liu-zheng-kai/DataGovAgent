# DataGovAgent

[English](./README.md) | 中文 | [日本語](./README.ja.md)

DataGovAgent 是一个本地化的元数据治理与追踪原型，基于 FastAPI、SQLAlchemy、MySQL、SQLite 回退机制以及 OpenAI 兼容的工具调用模式构建。

## 项目概览

DataGovAgent 的核心目标：

- 让各类数据系统把元数据写入统一标准模型
- 让服务层和工具层只面向 canonical schema
- 让 LLM 通过工具回答治理问题，而不是直接查库
- 让 Prompt 策略、后台控制、运行审计和扩展集成都能独立演进

## 架构总览

![Architecture Diagram](./docs/images/architecture_flow.png)

### 页面效果图

#### 1. 管理后台首页
![Admin Console Home](./docs/images/admin_overview.png)

#### 2. Chat 对话效果
![Chat Experience](./docs/images/chat_effect.png)

#### 3. Prompt Template 管理效果
![Prompt Template Management](./docs/images/prompt_template_effect.png)

### 核心模块

#### 1. Agent 编排层
- 组件：`MetadataAgent`
- 文件：`app/agent/llm_agent.py`
- 作用：负责一次问答流程编排，不直接访问数据库

#### 2. Tools 层
- 组件：`TOOL_DEFINITIONS`、`MetadataToolRegistry`
- 文件：`app/agent/tooling.py`、`app/tools/registry.py`
- 作用：把模型调用转成标准化业务函数，再路由到服务层

#### 3. Metadata Store
- 组件：数据库与 `app/models/*`
- 作用：项目中的统一事实来源，覆盖资产、血缘、运行状态、SLA、影响分析、报告和后台控制数据

#### 4. Prompt 管理
- 组件：`PromptTemplateRecord`、`ToolPromptBindingRecord`、`/api/admin/prompt-templates*`
- 作用：将提示词从代码中解耦，支持场景化默认模板、版本管理、预览和在线调优

## 快速开始

### 1. 前置依赖

- Python `3.11+`
- MySQL `8+`
- 可选：OpenAI 兼容 API Key

### 2. 创建虚拟环境

```bash
cd D:\codexAIcode\metadata_governance_poc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，并确认：

```env
app_name=DataGovAgent
app_public_base_url=http://127.0.0.1:8000
database_url=mysql+pymysql://root:root@localhost:3306/metadata_governance
database_fallback_url=sqlite:///./metadata_governance.db
openai_auth_mode=api_key
openai_api_key=your_openai_key
```

### 4. 初始化并启动

```bash
python -m app.seed.seed_data
uvicorn app.main:app --reload --port 8000
```

打开：

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`
- Admin: `http://127.0.0.1:8000/admin`

## 常用接口示例

```bash
curl http://127.0.0.1:8000/assets/customer_profile
curl "http://127.0.0.1:8000/runtime/failed?domain=Customer"
curl http://127.0.0.1:8000/sla/risks
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"Which teams are impacted by silver.customer_contact failure?\"}"
```

## 说明

- 默认主 README 为英文版：[README.md](./README.md)
- 如果你需要完整的 API 列表、故障排查说明和 VS Code 开发流程，优先参考英文版
- 当前仓库目录名仍然保持 `metadata_governance_poc`，以避免影响现有代码路径
