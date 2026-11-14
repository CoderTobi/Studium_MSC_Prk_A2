"""Prompt injection check for ``POST /recommendations`` (``PROMPT_REJECTED``).

This is a rule-based filter that runs before the model is called. It is the first of
several layers. The others are in ``ollama.py`` and ``recommendations.py``: the user
text is passed to the model as delimited data under a fixed system prompt, the model
is forced into a JSON schema, and its output is parsed into item names that are
validated against an allowlist. So a prompt that slips through this filter still
can't make the backend return arbitrary text.

The rules target things a meal description never needs: instructions aimed at the
model ("ignore the previous instructions", "you are now ..."), questions about its
configuration ("show me your system prompt"), chat template tokens, invisible
characters that could hide such text, and long multi-line payloads. English and
German phrasings are covered.

The client never learns which rule matched. The rule name is logged (never the
prompt) so that false positives can be investigated.
"""

import re
import unicodedata

from shopping_list.errors import ApiError, ErrorCode
from shopping_list.logging_setup import get_logger

logger = get_logger("prompt_guard")

# A meal description fits in a few lines. Long multi-line text is typical for
# injected instruction blocks.
MAX_PROMPT_LINES = 10

# Bidirectional overrides can make text render differently from what the model reads.
_BIDI_CONTROLS = frozenset("‪‫‬‭‮⁦⁧⁨⁩")

# Text that is used in the model input to delimit the user prompt (see ``ollama.py``).
PROMPT_DELIMITER_TAG = "meal_request"

# DOTALL: the gaps in the rules (".{0,40}") also span line breaks.
_FLAGS = re.IGNORECASE | re.MULTILINE | re.DOTALL

# (rule name, pattern). The patterns run on the normalized prompt, see ``_normalize``.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, _FLAGS))
    for name, pattern in (
        # --- Overriding the instructions ------------------------------------------
        (
            "override_instructions_en",
            r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}"
            r"\b(instructions?|prompts?|rules?|guidelines?|directions?|directives?|context"
            r"|above|previous|prior|preceding|earlier|everything)\b",
        ),
        (
            "override_instructions_de",
            r"\b(ignorier\w*|vergiss|vergesse\w*|missacht\w*|übergeh\w*|überschreib\w*"
            r"|umgeh\w*)\b.{0,40}"
            r"\b(anweisung\w*|instruktion\w*|befehl\w*|regel\w*|vorgabe\w*|prompts?|alles"
            r"|oben|vorherig\w*|bisherig\w*|vorangegangen\w*|obig\w*)\b",
        ),
        (
            "new_instructions",
            r"\b(new|updated|real|actual|neue|neuen|echten?|eigentlichen?)\s+"
            r"(instructions?|rules?|task|anweisung\w*|regeln|aufgabe)\b",
        ),
        # --- Questions about the model's configuration --------------------------------
        (
            "system_prompt",
            r"\b(system|developer|hidden|initial|original|internal|secret)\s*-?\s*"
            r"(prompts?|messages?|instructions?)\b"
            r"|\bsystem\s*(prompt|nachricht|anweisung)\w*\b"
            r"|\b(versteckt|intern|geheim|ursprünglich)\w*\s+(prompt|anweisung|instruktion)\w*\b",
        ),
        (
            "reveal_configuration",
            r"\b(reveal|print|show|repeat|output|leak|display|tell\s+me|what\s+(is|are))\b.{0,30}"
            r"\b(your|the)\s+(prompt|instructions?|rules?|configuration|config)\b"
            r"|\b(zeig\w*|verrat\w*|gib|wiederhol\w*|nenn\w*)\b.{0,30}"
            r"\b(deine[nmrs]?|die)\s+(prompt|anweisung\w*|instruktion\w*|regeln|konfiguration)\b",
        ),
        # --- Changing the model's role or output --------------------------------------
        (
            "role_change_en",
            r"\byou\s+are\s+(now|no\s+longer|not\s+an?)\b|\bfrom\s+now\s+on\b|\bact\s+as\b"
            r"|\bpretend\b|\brole\s*-?\s*play|\bimpersonate\b|\bjail\s*-?\s*break"
            r"|\bdeveloper\s+mode\b|\bdo\s+anything\s+now\b|\bunrestricted\b",
        ),
        (
            "role_change_de",
            r"\bdu\s+bist\s+(jetzt|nun|ab\s+sofort|ab\s+jetzt|kein\w*|nicht\s+mehr)\b"
            r"|\bab\s+(sofort|jetzt)\b.{0,30}\b(bist|antwortest|sollst|musst)\b"
            r"|\btu\s+so,?\s+als\b|\bspiel\w*\s+die\s+rolle\b|\bverhalte\s+dich\s+wie\b"
            r"|\bentwicklermodus\b",
        ),
        (
            "output_control",
            r"\b(respond|reply|answer|output)\s+(only\s+)?(with|in)\b"
            r"|\b(antworte|antwortest)\b.{0,20}\b(nur|ausschließlich)\b.{0,20}"
            r"\b(mit|aus|in)\b",
        ),
        # --- Chat template tokens and fake conversation turns --------------------------
        (
            "template_tokens",
            r"<\|[^|]{0,40}\|>|\[/?inst\]|<</?sys>>|</?s>|###\s*(instruction|system|response)"
            r"|```|</?" + PROMPT_DELIMITER_TAG,
        ),
        (
            "fake_turn",
            r"^\s*(system|assistant|user|developer|human|ai|model)\s*:",
        ),
    )
)


def _normalize(prompt: str) -> str:
    """Make the rules hard to evade with look-alike or invisible characters.

    NFKC maps compatibility characters (full-width letters, ligatures, ...) to their
    plain form. Format characters such as zero-width spaces are removed, so they can't
    split a keyword. Runs of spaces and tabs are collapsed, newlines are kept for the
    ``fake_turn`` rule. ``lower`` instead of ``casefold``, because casefold turns "ß"
    into "ss" and the German rules are written with "ß".
    """
    text = unicodedata.normalize("NFKC", prompt)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    text = re.sub(r"[^\S\n]+", " ", text)
    return text.lower()


def find_violation(prompt: str) -> str | None:
    """Return the name of the first rule the prompt violates, or ``None``."""
    if any(char in _BIDI_CONTROLS for char in prompt):
        return "bidi_control"
    # Newlines and tabs are fine, other control characters are not.
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in prompt):
        return "control_character"
    if prompt.count("\n") >= MAX_PROMPT_LINES:
        return "too_many_lines"

    text = _normalize(prompt)
    for name, pattern in _RULES:
        if pattern.search(text):
            return name
    return None


def check_prompt(prompt: str) -> None:
    """Raise ``PROMPT_REJECTED`` if the (already trimmed) prompt looks like an injection."""
    rule = find_violation(prompt)
    if rule is not None:
        logger.info("Prompt rejected by the injection check (rule=%s)", rule)
        raise ApiError(ErrorCode.PROMPT_REJECTED)
