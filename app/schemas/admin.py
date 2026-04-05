from typing import Any

from pydantic import BaseModel, Field


class ToolUpdateRequest(BaseModel):
    description: str | None = None
    enabled: bool | None = None
    output_schema_json: dict[str, Any] | None = None


class PromptTemplateCreateRequest(BaseModel):
    name: str
    template_key: str
    scene_type: str
    description: str | None = None
    usage_notes: str | None = None
    prompt_content: str
    output_format: str | None = None
    example_input: str | None = None
    example_output: str | None = None
    is_default: bool = False
    status: str = Field(default='draft')
    version: str = Field(default='v1')


class PromptTemplateUpdateRequest(BaseModel):
    name: str | None = None
    template_key: str | None = None
    scene_type: str | None = None
    description: str | None = None
    usage_notes: str | None = None
    prompt_content: str | None = None
    output_format: str | None = None
    example_input: str | None = None
    example_output: str | None = None
    is_default: bool | None = None
    status: str | None = None
    version: str | None = None


class PromptTemplatePreviewRequest(BaseModel):
    question: str = ''
    params: dict[str, Any] | None = None


class ToolPromptBindingCreateRequest(BaseModel):
    scene_type: str
    prompt_template_id: int
    is_default: bool = True


class ToolPromptBindingUpdateRequest(BaseModel):
    scene_type: str | None = None
    prompt_template_id: int | None = None
    is_default: bool | None = None


class MemoryCreateRequest(BaseModel):
    memory_type: str = Field(default='note')
    title: str
    content: str
    metadata_json: dict[str, Any] | None = None


class MemoryUpdateRequest(BaseModel):
    memory_type: str | None = None
    title: str | None = None
    content: str | None = None
    metadata_json: dict[str, Any] | None = None


class JobCreateRequest(BaseModel):
    name: str
    job_type: str = Field(default='metadata_sync')
    cron_expr: str = Field(default='*/15 * * * *')
    enabled: bool = True
    config_json: dict[str, Any] | None = None


class JobUpdateRequest(BaseModel):
    job_type: str | None = None
    cron_expr: str | None = None
    enabled: bool | None = None
    status: str | None = None
    config_json: dict[str, Any] | None = None


class ChannelCreateRequest(BaseModel):
    channel_id: str
    channel_name: str
    channel_type: str = Field(default='telegram')
    enabled: bool = True
    config_json: dict[str, Any] | None = None
    default_assistant_id: str | None = None


class ChannelUpdateRequest(BaseModel):
    channel_name: str | None = None
    channel_type: str | None = None
    enabled: bool | None = None
    config_json: dict[str, Any] | None = None
    default_assistant_id: str | None = None
