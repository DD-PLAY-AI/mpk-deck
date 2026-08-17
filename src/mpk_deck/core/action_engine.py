import logging
from typing import Callable

from mpk_deck.core.action_registry import Binding

logger = logging.getLogger(__name__)

TriggerHandler = Callable[[dict], None]
ContinuousHandler = Callable[[dict, float], None]


class ActionEngine:
    def __init__(self) -> None:
        self._trigger_handlers: dict[str, TriggerHandler] = {}
        self._continuous_handlers: dict[str, ContinuousHandler] = {}
        self._bindings_by_control: dict[str, Binding] = {}

    def register_trigger(self, action_name: str, handler: TriggerHandler) -> None:
        self._trigger_handlers[action_name] = handler

    def register_continuous(self, action_name: str, handler: ContinuousHandler) -> None:
        self._continuous_handlers[action_name] = handler

    def load_bindings(self, bindings: list[Binding]) -> None:
        self._bindings_by_control = {b.control: b for b in bindings}

    @property
    def bindings(self) -> dict[str, Binding]:
        return dict(self._bindings_by_control)

    def trigger(self, control: str) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            logger.info("no binding for control %s", control)
            return
        handler = self._trigger_handlers.get(binding.action)
        if handler is None:
            logger.warning("no trigger handler registered for action %s", binding.action)
            return
        handler(binding.params)

    def set_continuous(self, control: str, value: float) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            return
        handler = self._continuous_handlers.get(binding.action)
        if handler is None:
            logger.warning("no continuous handler registered for action %s", binding.action)
            return
        handler(binding.params, value)
