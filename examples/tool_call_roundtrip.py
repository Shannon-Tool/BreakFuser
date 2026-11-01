"""Model-proposed tool call followed by an explicit harness observation.

BreakFuser validates the proposal; the harness remains responsible for execution.
"""

import json

from BreakFuser import BreakFuser

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Read weather from the external harness",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }
]
messages: list[dict[str, object]] = [
    {"role": "user", "content": "Read Paris weather using the supplied tool"}
]
with BreakFuser() as client:
    proposal = client.chat.completions.create(messages=messages, tools=tools)
    message = proposal.choices[0].message
    call = message.tool_calls[0]
    print(call.function.name, call.function.arguments)

    synthetic_harness_observation = json.dumps({"temperature": 21, "unit": "C"})
    messages.extend(
        [
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [item.model_dump(mode="json") for item in message.tool_calls],
            },
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": synthetic_harness_observation,
            },
        ]
    )
    final = client.chat.completions.create(messages=messages)
    print(final.choices[0].message.content)
