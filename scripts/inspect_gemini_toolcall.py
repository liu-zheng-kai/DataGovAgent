from openai import OpenAI

from app.agent.tooling import TOOL_DEFINITIONS
from app.core.config import settings


def main():
    client = OpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)
    messages = [
        {
            'role': 'system',
            'content': 'You are a metadata governance assistant. Use tools for factual answers.',
        },
        {'role': 'user', 'content': 'Which teams are impacted by silver.customer_contact failure?'},
    ]
    response = client.chat.completions.create(
        model=settings.gemini_model,
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_choice='auto',
    )
    msg = response.choices[0].message
    print('message dump:')
    try:
        print(msg.model_dump())
    except Exception:
        print(msg)
    print('tool_calls dump:')
    if msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                print(tc.model_dump())
            except Exception:
                print(tc)


if __name__ == '__main__':
    main()
