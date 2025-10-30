"""Hilfsfunktionen zum Extrahieren von Text aus OpenAI-Responses."""

from __future__ import annotations

from typing import Any, Iterable
import json


def extract_output_text(response: Any) -> str:
    """Versucht, Text aus der Antwortstruktur zu gewinnen."""

    if response is None:
        return ""

    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    data = None
    if hasattr(response, "model_dump"):
        data = response.model_dump()
    elif isinstance(response, dict):
        data = response

    parts: list[str] = []

    def _collect_text(chunks: Iterable[Any]) -> None:
        for chunk in chunks:
            text_obj = getattr(chunk, "text", None)
            if text_obj and getattr(text_obj, "value", None):
                parts.append(str(text_obj.value))
            elif isinstance(chunk, dict):
                value = chunk
                if "text" in value and isinstance(value["text"], dict):
                    nested = value["text"].get("value")
                    if nested:
                        parts.append(str(nested))
                elif "value" in value:
                    parts.append(str(value["value"]))

    if hasattr(response, "output") and response.output:
        for item in response.output:
            _collect_text(getattr(item, "content", []))
    elif data and "output" in data:
        for item in data["output"] or []:
            _collect_text(item.get("content", []))

    if not parts and data:
        if "choices" in data:
            for choice in data.get("choices") or []:
                if isinstance(choice, dict):
                    # ChatCompletion-ähnliche Struktur: message -> content / tool_calls
                    message = choice.get("message", {})
                    if isinstance(message, dict):
                        content = message.get("content")
                        if content:
                            parts.append(str(content))
                        parsed = message.get("parsed")
                        if parsed is not None:
                            parts.append(json.dumps(parsed, ensure_ascii=False) if not isinstance(parsed, str) else parsed)
                        tool_calls = message.get("tool_calls") or []
                        for call in tool_calls:
                            if isinstance(call, dict):
                                args = call.get("function", {}).get("arguments")
                                if args:
                                    parts.append(str(args))
                elif hasattr(choice, "message"):
                    message = choice.message
                    if getattr(message, "content", None):
                        parts.append(str(message.content))
                    parsed = getattr(message, "parsed", None)
                    if parsed is not None:
                        parts.append(json.dumps(parsed, ensure_ascii=False) if not isinstance(parsed, str) else parsed)
                    if getattr(message, "tool_calls", None):
                        for call in message.tool_calls:
                            args = getattr(getattr(call, "function", None), "arguments", None)
                            if args:
                                parts.append(str(args))

    combined = "\n".join(part for part in parts if part)
    return combined or ""
