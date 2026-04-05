from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ToolDefinitionRecord(Base):
    __tablename__ = 'tools'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_schema_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    versions = relationship('ToolVersionRecord', back_populates='tool')
    prompt_bindings = relationship('ToolPromptBindingRecord', back_populates='tool')


class ToolVersionRecord(Base):
    __tablename__ = 'tool_versions'
    __table_args__ = (Index('ix_tool_versions_tool_id', 'tool_id'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey('tools.id'), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    changelog: Mapped[str] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    tool = relationship('ToolDefinitionRecord', back_populates='versions')


class PromptTemplateRecord(Base):
    __tablename__ = 'prompt_templates'
    __table_args__ = (
        Index('ix_prompt_templates_scene', 'scene_type'),
        Index('ix_prompt_templates_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    template_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    scene_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    usage_notes: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(Text, nullable=True)
    example_input: Mapped[str] = mapped_column(Text, nullable=True)
    example_output: Mapped[str] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='draft', nullable=False)
    version: Mapped[str] = mapped_column(String(32), default='v1', nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    versions = relationship('PromptTemplateVersionRecord', back_populates='template')
    tool_bindings = relationship('ToolPromptBindingRecord', back_populates='prompt_template')


class PromptTemplateVersionRecord(Base):
    __tablename__ = 'prompt_template_versions'
    __table_args__ = (
        Index('ix_prompt_template_versions_template', 'prompt_template_id'),
        UniqueConstraint(
            'prompt_template_id', 'version', name='uq_prompt_template_version'
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_template_id: Mapped[int] = mapped_column(
        ForeignKey('prompt_templates.id'), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    change_log: Mapped[str] = mapped_column(Text, nullable=True)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='draft', nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    template = relationship('PromptTemplateRecord', back_populates='versions')


class ToolPromptBindingRecord(Base):
    __tablename__ = 'tool_prompt_bindings'
    __table_args__ = (
        UniqueConstraint(
            'tool_id',
            'scene_type',
            'prompt_template_id',
            name='uq_tool_scene_template_binding',
        ),
        Index('ix_tool_prompt_bindings_tool_scene', 'tool_id', 'scene_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey('tools.id'), nullable=False, index=True)
    scene_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_template_id: Mapped[int] = mapped_column(
        ForeignKey('prompt_templates.id'), nullable=False, index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tool = relationship('ToolDefinitionRecord', back_populates='prompt_bindings')
    prompt_template = relationship('PromptTemplateRecord', back_populates='tool_bindings')


class DataSourceRecord(Base):
    __tablename__ = 'data_sources'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connection_uri: Mapped[str] = mapped_column(String(500), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tables = relationship('DataSourceTableRecord', back_populates='data_source')


class DataSourceTableRecord(Base):
    __tablename__ = 'data_source_tables'
    __table_args__ = (
        UniqueConstraint(
            'data_source_id',
            'schema_name',
            'table_name',
            name='uq_data_source_table_name',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey('data_sources.id'), nullable=False, index=True)
    schema_name: Mapped[str] = mapped_column(String(120), nullable=False)
    table_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    sample_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    data_source = relationship('DataSourceRecord', back_populates='tables')


class ChannelRecord(Base):
    __tablename__ = 'channels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    default_assistant_id: Mapped[str] = mapped_column(String(120), nullable=True)
    last_seen_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChatSessionRecord(Base):
    __tablename__ = 'chats'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='active', nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey('channels.id'), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_message_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)

    channel = relationship('ChannelRecord')
    messages = relationship('ChatMessageRecord', back_populates='chat_session')
    tool_calls = relationship('ToolCallRecord', back_populates='chat_session')


class ChatMessageRecord(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        Index('ix_chat_messages_chat_session', 'chat_session_id'),
        Index('ix_chat_messages_message_order', 'message_order'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey('chats.id'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_order: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    chat_session = relationship('ChatSessionRecord', back_populates='messages')


class ToolCallRecord(Base):
    __tablename__ = 'tool_calls'
    __table_args__ = (
        Index('ix_tool_calls_chat_session', 'chat_session_id'),
        Index('ix_tool_calls_tool_name', 'tool_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_session_id: Mapped[int] = mapped_column(ForeignKey('chats.id'), nullable=False, index=True)
    chat_message_id: Mapped[int] = mapped_column(ForeignKey('chat_messages.id'), nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    args_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    chat_session = relationship('ChatSessionRecord', back_populates='tool_calls')
    chat_message = relationship('ChatMessageRecord')


class MemoryRecord(Base):
    __tablename__ = 'memories'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ScheduledJobRecord(Base):
    __tablename__ = 'scheduled_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default='idle', nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    runs = relationship('JobRunRecord', back_populates='job')


class JobRunRecord(Base):
    __tablename__ = 'job_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('scheduled_jobs.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    job = relationship('ScheduledJobRecord', back_populates='runs')


class AuditLogRecord(Base):
    __tablename__ = 'audit_logs'
    __table_args__ = (Index('ix_audit_logs_entity', 'entity_type', 'entity_id'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
