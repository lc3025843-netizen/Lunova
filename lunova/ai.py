"""AI provider abstraction for Lunova's staged rewrite engine."""
from __future__ import annotations

from dataclasses import dataclass

from .citations import protect_fragments, restore_fragments, missing_protected_tokens
from .prompts import build_instructions


@dataclass
class RewriteResult:
    text: str
    warning: str | None = None
    passes: int = 0


def _call(client, *, model: str, instructions: str, text: str) -> str:
    response = client.responses.create(model=model, instructions=instructions, input=text)
    return (response.output_text or "").strip()


def rewrite_text(
    text: str,
    *,
    api_key: str,
    model: str,
    mode: str,
    level: int,
    research_mode: bool,
    options: dict[str, bool],
    editorial_instruction: str = "",
) -> RewriteResult:
    if not text.strip():
        return RewriteResult(text="", warning="No hay texto para procesar.")
    if not api_key:
        return RewriteResult(text=text, warning="Falta configurar OPENAI_API_KEY en los secretos del servidor.")

    protected = protect_fragments(text, protect_numbers=options.get("keep_data", True))
    # Lunova performs the internal repetition the user otherwise tends to do manually.
    stages = ["restructure", "naturalize"]
    if level >= 3 or research_mode:
        stages.append("polish")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        working = protected.text
        completed = 0
        for stage in stages:
            instructions = build_instructions(
                mode,
                level,
                research_mode,
                options,
                stage=stage,
                editorial_instruction=editorial_instruction,
            )
            candidate = _call(client, model=model, instructions=instructions, text=working)
            if not candidate:
                return RewriteResult(text=text, warning="El motor devolvió una respuesta vacía; se conservó el original.", passes=completed)
            # Validate tokens while still protected so a lost citation/number is caught immediately.
            missing_tokens = [token for token in protected.replacements if token not in candidate]
            if missing_tokens:
                sample = ", ".join(missing_tokens[:3])
                return RewriteResult(
                    text=text,
                    warning=f"La revisión se descartó porque faltaron elementos protegidos ({sample}).",
                    passes=completed,
                )
            working = candidate
            completed += 1

        restored = restore_fragments(working, protected.replacements)
        missing = missing_protected_tokens(restored, protected.replacements)
        if missing:
            sample = ", ".join(missing[:3])
            return RewriteResult(
                text=text,
                warning=f"La revisión se descartó porque faltaron elementos protegidos ({sample}).",
                passes=completed,
            )
        return RewriteResult(text=restored, passes=completed)
    except Exception as exc:
        return RewriteResult(text=text, warning=f"No se pudo completar la revisión: {type(exc).__name__}.")
