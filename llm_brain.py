"""LLM integration for generating patient responses."""

from openai import AsyncOpenAI
from config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

WRAPPER_PROMPT = (
    "You are role-playing as a patient calling a medical/dental office. "
    "Stay in character at all times. Respond naturally and conversationally — "
    "keep responses to 1-3 sentences like a real phone call. "
    "Do not narrate actions or use asterisks. Just speak as the patient would.\n\n"
    "PATIENT PERSONA:\n{scenario_prompt}"
)


async def get_patient_response(
    scenario_prompt: str,
    conversation_history: list[dict],
    agent_message: str,
) -> str:
    """Generate the next patient response given the conversation so far."""
    system = WRAPPER_PROMPT.format(scenario_prompt=scenario_prompt)

    messages = [{"role": "system", "content": system}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": f"[Office agent says]: {agent_message}"})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=150,
        temperature=0.8,
    )

    return response.choices[0].message.content.strip()