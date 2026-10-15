from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.actions import ConfirmationLine
from app.models.auth import CurrentStudent


class ActionError(Exception):
    """An action cannot go ahead, for a reason that can be told to the student as it is."""


def text_arg(args: dict, key: str, label: str, minimum: int, maximum: int) -> str:
    """A required text argument from the model, trimmed, with a length check."""
    value = args.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ActionError(f"I need the {label} ({minimum} to {maximum} characters) to go ahead.")
    return value.strip()


@dataclass(frozen=True)
class Prepared:
    """A checked, previewed action that is ready to wait for approval."""

    title: str
    lines: list[ConfirmationLine]
    params: dict  # what will be run, exactly, on approval


@dataclass(frozen=True)
class Done:
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionSpec:
    """One thing the assistant can propose but only the student can approve.

    schema is what the model is told (without any student id: the action is
    always for the signed-in student). prepare checks the model's arguments and
    builds the preview, raising ActionError with a plain reason if it cannot go
    ahead. execute runs the stored parameters when the student approves, and is
    the authority: it re-checks everything, since time has passed.
    """

    name: str
    schema: dict
    prepare: Callable[[dict, CurrentStudent], Prepared]
    execute: Callable[[dict, CurrentStudent], Done]
