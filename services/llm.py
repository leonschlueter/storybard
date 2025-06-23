import openai

def call_openai_structured(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """
    Sends a structured system + user prompt to OpenAI.
    Returns: (narration string, full OpenAI response dict)
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=600
        )
        text = response["choices"][0]["message"]["content"].strip()
        return text, response

    except Exception as e:
        return f"(LLM ERROR) {str(e)}", {}