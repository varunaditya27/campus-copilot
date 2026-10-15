import re
import unicodedata
from dataclasses import dataclass, field

from app.core import config
from app.models.chat import ChatResponse
from app.observability import metrics
from app.observability.logging import get_logger

logger = get_logger(__name__)

BLOCK_AT = 3  # a message scoring this much is treated as an attack

REFUSAL = (
    "I can't follow instructions like that one. I'm here to help with campus questions: events, your "
    "timetable and attendance, the library, fees and so on. What would you like to know?"
)

# Characters that show nothing but can hide text from a person while the model still reads it:
# zero-width and joiner characters, bidirectional overrides, invisible operators, the byte order mark.
_INVISIBLE = {c: None for c in (*range(0x200B, 0x2010), *range(0x202A, 0x202F), *range(0x2060, 0x2065), 0xFEFF, 0x00AD)}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize(text: str) -> str:
    """Make a message safe to hand on: the same text with nothing hidden in it.

    Unicode is normalised (so fullwidth or ligature spellings of a word read as the word),
    invisible and control characters are removed, and runs of blank space are collapsed.
    Ordinary text, including other languages, passes through unchanged."""
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    text = _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = re.sub(r"[ \t]{3,}", "  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_I = re.IGNORECASE
# (pattern, weight, name). Weighted, so one mild phrase alone never blocks, while a clear attack does.
_RULES: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"\b(ignore|disregard|forget|override|bypass|skip)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|your|the|these|those)\b[^.\n]{0,30}\b(instructions?|rules?|prompts?|guidelines?|directions?|polic(?:y|ies)|restrictions?)\b", _I), 3, "override_instructions"),
    (re.compile(r"\b(reveal|show|print|repeat|display|output|leak|dump|recite)\b[^.\n]{0,40}\b(system|initial|hidden|original|secret)\b[^.\n]{0,15}\b(prompt|instructions?|message|rules)\b", _I), 3, "reveal_system_prompt"),
    (re.compile(r"\b(what|which)\b[^.\n]{0,15}\b(is|are)\b[^.\n]{0,10}\byour\b[^.\n]{0,10}\b(system prompt|hidden instructions|initial instructions)\b", _I), 3, "ask_system_prompt"),
    (re.compile(r"\byou are (now|no longer)\b|\bpretend (to be|that you are|you are)\b|\bfrom now on,? you\b", _I), 2, "role_change"),
    (re.compile(r"\b(DAN|do anything now|developer mode|jailbreak(ed)?|god mode|unrestricted mode|no restrictions)\b", _I), 3, "jailbreak_term"),
    (re.compile(r"\bact as\b[^.\n]{0,25}\b(unrestricted|unfiltered|jailbroken|evil|without (rules|restrictions|limits))\b", _I), 3, "role_without_limits"),
    (re.compile(r"<\|?(im_start|im_end|system|assistant|endoftext)\|?>|\[/?INST\]|<<\s*/?SYS\s*>>|</?(system|assistant)>", _I), 3, "fake_delimiter"),
    (re.compile(r"^\s*(#{1,3}\s*)?(system|assistant|developer)\s*(message|prompt)?\s*:", _I | re.MULTILINE), 2, "fake_role_line"),
    (re.compile(r"\b(new|updated|real|actual)\s+(instructions?|rules?|system prompt)\s*[:\-]", _I), 2, "new_instructions"),
    (re.compile(r"\b(cgpa|grades?|attendance|fees?|records?|marks|timetable)\b[^.\n]{0,25}\b(of|for)\b[^.\n]{0,15}\b[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}\b", _I), 2, "other_students_data"),
    (re.compile(r"\b(send|post|forward|upload|email|exfiltrate)\b[^.\n]{0,60}\bhttps?://", _I), 2, "send_to_url"),
    (re.compile(r"!\[[^\]]*\]\(https?://[^)\s]*\?[^)\s]*\)"), 3, "image_exfiltration"),
    (re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"), 2, "encoded_blob"),
]


@dataclass(frozen=True)
class Verdict:
    score: int
    reasons: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return self.score >= BLOCK_AT


def inspect(text: str) -> Verdict:
    """Score a message for patterns that appear when someone tries to take over an assistant.

    This is a heuristic filter, not a guarantee: a determined attacker can rephrase around any list of
    patterns. What really limits the damage is that the assistant can only act for the signed-in student,
    that tools never take a student id from the model, and that every change needs the student's approval."""
    matched = [(weight, name) for pattern, weight, name in _RULES if pattern.search(text)]
    return Verdict(score=sum(w for w, _ in matched), reasons=[name for _, name in matched])


def screen(message: str) -> ChatResponse | None:
    """The refusal to give instead of running the agent, or None to let the message through."""
    if config.PROMPT_GUARD == "off":
        return None
    verdict = inspect(message)
    if not verdict.flagged:
        return None
    action = "blocked" if config.PROMPT_GUARD == "block" else "logged"
    metrics.PROMPT_INJECTION.labels(action).inc()
    # Which rules matched, never the message itself: it may hold personal data.
    logger.warning("security.prompt_injection", action=action, score=verdict.score, reasons=verdict.reasons)
    return ChatResponse(reply=REFUSAL) if action == "blocked" else None
