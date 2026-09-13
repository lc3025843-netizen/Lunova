"""Prompt construction for Lunova's staged writing engine."""
from __future__ import annotations

MODE_GUIDANCE = {
    "Natural": (
        "Usa un español natural, fluido y humano, con variación sintáctica y vocabulario preciso. "
        "Evita sonar mecánico, excesivamente solemne o repetitivo."
    ),
    "Académico": (
        "Mantén un registro académico claro y comprensible, con cohesión lógica, precisión conceptual "
        "y conectores variados sin recargar el texto."
    ),
    "Profundo": (
        "Reestructura de forma sustancial el orden y la sintaxis de las ideas sin cambiar el significado, "
        "evitando la sustitución superficial de palabras por sinónimos."
    ),
}

LEVEL_GUIDANCE = {
    1: "Haz cambios moderados y conserva bastante de la estructura original cuando ya sea adecuada.",
    2: "Reorganiza oraciones y conexiones con libertad moderada para mejorar claridad, naturalidad y cohesión.",
    3: "Replantea la estructura del párrafo con mayor profundidad, manteniendo exactamente las ideas y hechos originales.",
}

STAGE_GUIDANCE = {
    "restructure": (
        "Primera pasada: trabaja la arquitectura del texto. Reorganiza sintaxis, relaciones entre ideas y ritmo; "
        "no hagas sustituciones mecánicas de sinónimos."
    ),
    "naturalize": (
        "Segunda pasada: revisa la versión recibida como editor. Elimina rigidez, muletillas, repeticiones y patrones "
        "monótonos; mejora transiciones y conserva la precisión académica."
    ),
    "polish": (
        "Tercera pasada: realiza un pulido final. Corrige fluidez, concordancia, puntuación y cohesión, sin añadir ideas "
        "ni intensificar afirmaciones que no estén en el original."
    ),
}


def build_instructions(
    mode: str,
    level: int,
    research_mode: bool,
    options: dict[str, bool],
    *,
    stage: str = "restructure",
    editorial_instruction: str = "",
) -> str:
    rules = [
        "Eres Lunova, un editor de redacción académica en español.",
        "Tu tarea es mejorar la redacción y producir una paráfrasis genuina; no intentes evadir detectores ni ocultar autoría.",
        "No inventes hechos, autores, resultados, porcentajes, fechas, fuentes ni conclusiones.",
        "No añadas información que no esté presente en el texto de entrada.",
        "Mantén la intención, el grado de certeza y el significado del texto original.",
        "Devuelve únicamente el texto revisado, sin notas, títulos ni explicaciones adicionales.",
        MODE_GUIDANCE.get(mode, MODE_GUIDANCE["Académico"]),
        LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE[2]),
        STAGE_GUIDANCE.get(stage, STAGE_GUIDANCE["restructure"]),
    ]

    if research_mode:
        rules += [
            "Prioriza un estilo apropiado para tesis, artículos y trabajos de investigación.",
            "Usa conectores con naturalidad y evita encadenar demasiadas oraciones cortas separadas por punto.",
            "Conserva la relación lógica entre antecedentes, resultados, interpretación y conclusión.",
        ]

    if options.get("keep_citations", True):
        rules.append("Conserva exactamente todos los tokens [[LNV_*]]; no los cambies, elimines, dupliques ni reordenes de manera ilógica.")
    if options.get("improve_connectors", True):
        rules.append("Varía los conectores discursivos y evita repetir de forma mecánica 'además', 'por otra parte' o 'en este sentido'.")
    if options.get("avoid_repetition", True):
        rules.append("Reduce repeticiones léxicas innecesarias manteniendo los términos técnicos cuando sean necesarios.")
    if options.get("optimize_sentences", True):
        rules.append("Combina o divide oraciones cuando mejore la legibilidad; evita tanto frases telegráficas como oraciones excesivamente largas.")
    if options.get("respect_names", True):
        rules.append("No alteres nombres propios, nombres de instituciones, variables de investigación ni denominaciones técnicas.")

    if editorial_instruction.strip():
        rules.append("Instrucción editorial adicional configurada por el administrador: " + editorial_instruction.strip())

    return "\n".join(f"- {r}" for r in rules)
