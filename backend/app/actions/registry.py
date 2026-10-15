from app.actions import registration
from app.actions.base import ActionSpec

# Every action the assistant may propose. The model can ask for any of these;
# none of them runs until the student approves it.
ACTIONS: dict[str, ActionSpec] = {spec.name: spec for spec in (registration.SPEC,)}

ACTION_SCHEMAS = [spec.schema for spec in ACTIONS.values()]
