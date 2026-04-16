"""
Model-agnostic AI engine. Supports Anthropic Claude and OpenAI GPT.
Switch provider via AI_PROVIDER env var.
"""

import os
import json
from dotenv import load_dotenv
from utils.prompts import get_system_prompt
from services.error_logger import log_error

# Ensure .env is loaded regardless of which page or directory runs first
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)


def _get_provider():
    return os.getenv("AI_PROVIDER", "anthropic").lower()


def _call_anthropic(system_prompt, user_prompt):
    from anthropic import Anthropic

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def _call_openai(system_prompt, user_prompt):
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def generate(user_prompt, system_prompt=None):
    """Send a prompt to the configured AI provider and return the response text."""
    if system_prompt is None:
        system_prompt = get_system_prompt()
    provider = _get_provider()

    try:
        if provider == "anthropic":
            return _call_anthropic(system_prompt, user_prompt)
        elif provider == "openai":
            return _call_openai(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {provider}. Use 'anthropic' or 'openai'.")
    except Exception as e:
        log_error("ai_generation", str(e), context=f"provider={provider}, prompt_length={len(user_prompt)}", exception=e)
        raise RuntimeError(f"AI generation failed: {e}") from e


def _stream_anthropic(system_prompt, user_prompt):
    """Yield text chunks from Anthropic streaming response."""
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def _stream_openai(system_prompt, user_prompt):
    """Yield text chunks from OpenAI streaming response."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    stream = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def generate_stream(user_prompt, system_prompt=None):
    """Stream a response from the configured AI provider. Returns a generator of text chunks."""
    if system_prompt is None:
        system_prompt = get_system_prompt()
    provider = _get_provider()
    try:
        if provider == "anthropic":
            return _stream_anthropic(system_prompt, user_prompt)
        elif provider == "openai":
            return _stream_openai(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {provider}")
    except Exception as e:
        log_error("ai_generation", str(e), context=f"provider={provider}, prompt_length={len(user_prompt)}, stream=True", exception=e)
        raise RuntimeError(f"AI streaming failed: {e}") from e


def generate_json(user_prompt, system_prompt=None):
    """Generate a response and attempt to parse it as JSON."""
    raw = generate(user_prompt, system_prompt)
    # Try to extract JSON from the response
    try:
        # Handle responses wrapped in markdown code blocks
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError):
        return {"raw_response": raw}


def refine_text(text: str, instruction: str, context: str = ""):
    """Stream an inline AI edit of text according to a user instruction.

    Args:
        text:        The existing text to refine.
        instruction: What to do with it, e.g. "make this punchier".
        context:     Optional label for which PR section this text comes from.

    Returns:
        A generator of text chunks (same contract as generate_stream).
    """
    context_line = f"Section: {context}\n\n" if context else ""
    user_prompt = (
        f"{context_line}"
        f"Here is a section of a PR pack. Refine it according to the instruction. "
        f"Return ONLY the refined text with no preamble or explanation.\n\n"
        f"Instruction: {instruction}\n\n"
        f"Text to refine:\n{text}"
    )
    system_prompt = (
        "You are a precise copy editor. When given text and an instruction, "
        "you return only the revised text — no commentary, no labels, no markdown "
        "wrappers unless they were already present in the original."
    )
    return generate_stream(user_prompt, system_prompt=system_prompt)


def refine_text_sync(text: str, instruction: str, context: str = "") -> str:
    """Non-streaming version of refine_text. Returns the full refined string at once.

    Args:
        text:        The existing text to refine.
        instruction: What to do with it, e.g. "shorten this".
        context:     Optional label for which PR section this text comes from.

    Returns:
        The refined text as a single string.
    """
    context_line = f"Section: {context}\n\n" if context else ""
    user_prompt = (
        f"{context_line}"
        f"Here is a section of a PR pack. Refine it according to the instruction. "
        f"Return ONLY the refined text with no preamble or explanation.\n\n"
        f"Instruction: {instruction}\n\n"
        f"Text to refine:\n{text}"
    )
    system_prompt = (
        "You are a precise copy editor. When given text and an instruction, "
        "you return only the revised text — no commentary, no labels, no markdown "
        "wrappers unless they were already present in the original."
    )
    return generate(user_prompt, system_prompt=system_prompt)


def is_configured():
    """Check if at least one AI provider is configured with an API key."""
    provider = _get_provider()
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        return bool(key) and not key.startswith("your-")
    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        return bool(key) and not key.startswith("your-")
    return False
