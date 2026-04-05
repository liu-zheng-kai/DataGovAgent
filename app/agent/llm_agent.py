import json

from openai import OpenAI

from app.agent.tooling import TOOL_DEFINITIONS
from app.core.config import settings
from app.core.openai_oauth import load_codex_access_token
from app.services.admin_service import AdminService, infer_scene_type
from app.tools.registry import MetadataToolRegistry


SYSTEM_PROMPT = (
    'You are a metadata governance assistant. Always use tools for factual answers '
    'and do not fabricate runtime, SLA, or lineage data.'
)


class MetadataAgent:
    def __init__(self, db, oauth_access_token: str | None = None):
        self.db = db
        self.provider = settings.llm_provider
        self.auth_mode = settings.openai_auth_mode
        self.model_name = self._resolve_model_name(self.provider)
        self.api_key = self._resolve_api_key(oauth_access_token)
        self.base_url = self._resolve_base_url(self.provider)
        self.client = None
        self.tools = MetadataToolRegistry(db)
        self.tool_map = {
            'get_asset': self.tools.get_asset,
            'get_asset_detail': self.tools.get_asset_detail,
            'get_downstream': self.tools.get_downstream,
            'get_upstream': self.tools.get_upstream,
            'get_failed_runs': self.tools.get_failed_runs,
            'get_domain_health': self.tools.get_domain_health,
            'get_business_impact': self.tools.get_business_impact,
            'get_impacted_apis': self.tools.get_impacted_apis,
            'get_sla_risk_assets': self.tools.get_sla_risk_assets,
            'generate_daily_summary': self.tools.generate_daily_summary,
        }

    def _resolve_openai_credential(self, oauth_access_token: str | None) -> str:
        if self.auth_mode == 'oauth_token':
            return (
                oauth_access_token
                or settings.openai_oauth_token
                or load_codex_access_token(settings.openai_oauth_token_file)
                or ''
            )
        return settings.openai_api_key

    def _resolve_api_key(self, oauth_access_token: str | None) -> str:
        if self.provider == 'gemini':
            return settings.gemini_api_key
        return self._resolve_openai_credential(oauth_access_token)

    @staticmethod
    def _resolve_model_name(provider: str) -> str:
        if provider == 'gemini':
            value = (settings.gemini_model or '').strip()
            aliases = {
                'gemini 3 flash': 'gemini-3-flash-preview',
                'gemini3flash': 'gemini-3-flash-preview',
            }
            return aliases.get(value.lower(), value)
        value = (settings.openai_model or '').strip()
        aliases = {
            'gpt5.4': 'gpt-5.4',
            'gpt5': 'gpt-5',
        }
        return aliases.get(value.lower(), value)

    @staticmethod
    def _resolve_base_url(provider: str) -> str:
        if provider == 'gemini':
            return settings.gemini_base_url
        return settings.openai_base_url

    def _call_tool(self, tool_name, tool_args):
        fn = self.tool_map.get(tool_name)
        if not fn:
            return {'error': f'Unknown tool: {tool_name}'}
        try:
            return fn(**tool_args)
        except Exception as exc:
            return {'error': f'Tool execution failed: {exc}'}

    def _resolve_prompt_template(
        self,
        question: str,
        scene_type: str | None = None,
        prompt_template_key: str | None = None,
    ):
        admin = AdminService(self.db)
        selected = admin.resolve_prompt_template(
            scene_type=scene_type,
            prompt_template_key=prompt_template_key,
            question=question,
        )
        resolved_scene = scene_type or infer_scene_type(question)
        if not selected:
            return {
                'scene_type': resolved_scene,
                'prompt_template_key': None,
                'system_prompt': SYSTEM_PROMPT,
            }

        full_system_prompt = (
            f'{SYSTEM_PROMPT}\n\n'
            f'Scene Type: {selected.scene_type}\n'
            f'Template Key: {selected.template_key}\n'
            f'Usage Notes: {selected.usage_notes or ""}\n\n'
            f'Template Prompt:\n{selected.prompt_content}\n\n'
            f'Output Format:\n{selected.output_format or ""}'
        )
        return {
            'scene_type': selected.scene_type,
            'prompt_template_key': selected.template_key,
            'system_prompt': full_system_prompt,
        }

    def ask(
        self,
        question,
        scene_type: str | None = None,
        prompt_template_key: str | None = None,
    ):
        if not self.api_key:
            if self.provider == 'gemini':
                raise ValueError('GEMINI_API_KEY is empty. Configure .env before using /chat.')
            if self.auth_mode == 'oauth_token':
                raise ValueError(
                    'OpenAI OAuth token is empty. Set openai_oauth_token in .env '
                    'or pass oauth_access_token in /chat request body, '
                    f'or ensure {settings.openai_oauth_token_file} contains a valid token.'
                )
            raise ValueError('OPENAI_API_KEY is empty. Configure .env before using /chat.')
        if self.client is None:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        prompt_ctx = self._resolve_prompt_template(
            question=question,
            scene_type=scene_type,
            prompt_template_key=prompt_template_key,
        )
        messages = [
            {'role': 'system', 'content': prompt_ctx['system_prompt']},
            {'role': 'user', 'content': question},
        ]
        tool_trace = []

        for _ in range(settings.agent_max_iterations):
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice='auto',
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                return {
                    'answer': message.content or 'No answer generated.',
                    'tool_trace': tool_trace,
                    'scene_type': prompt_ctx['scene_type'],
                    'prompt_template_key': prompt_ctx['prompt_template_key'],
                }

            assistant_tool_calls = []
            for tc in tool_calls:
                payload = {
                    'id': tc.id,
                    'type': 'function',
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments,
                    },
                }
                extra_content = getattr(tc, 'extra_content', None)
                if extra_content:
                    payload['extra_content'] = extra_content
                assistant_tool_calls.append(payload)
            messages.append(
                {
                    'role': 'assistant',
                    'content': message.content or '',
                    'tool_calls': assistant_tool_calls,
                }
            )

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or '{}')
                except json.JSONDecodeError:
                    args = {}
                result = self._call_tool(tc.function.name, args)
                tool_trace.append(
                    {'tool': tc.function.name, 'args': args, 'result': result}
                )
                messages.append(
                    {
                        'role': 'tool',
                        'tool_call_id': tc.id,
                        'name': tc.function.name,
                        'content': json.dumps(result, default=str),
                    }
                )

        return {
            'answer': 'Agent reached max tool-iteration limit before final response.',
            'tool_trace': tool_trace,
            'scene_type': prompt_ctx['scene_type'],
            'prompt_template_key': prompt_ctx['prompt_template_key'],
        }
