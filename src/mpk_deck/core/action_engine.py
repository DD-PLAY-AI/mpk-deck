import logging
from typing import Callable, Optional

from mpk_deck.core.action_registry import Binding

logger = logging.getLogger(__name__)

TriggerHandler = Callable[[dict], None]
ContinuousHandler = Callable[[dict, float], None]


class ActionEngine:
    def __init__(
        self,
        on_bank_changed: Optional[Callable[[str], None]] = None,
        on_continuous: Optional[Callable[[str, float], None]] = None,
        on_trigger: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        self._trigger_handlers: dict[str, TriggerHandler] = {}
        self._continuous_handlers: dict[str, ContinuousHandler] = {}
        self._bindings_by_control: dict[str, Binding] = {}
        self._banks: dict[str, list[Binding]] = {}
        self._switch_bindings: dict[str, str] = {}
        self._active_bank: str = ""
        self._on_bank_changed = on_bank_changed
        self._on_continuous = on_continuous
        self._on_trigger = on_trigger

    def register_trigger(self, action_name: str, handler: TriggerHandler) -> None:
        self._trigger_handlers[action_name] = handler

    def register_continuous(self, action_name: str, handler: ContinuousHandler) -> None:
        self._continuous_handlers[action_name] = handler

    def load_banks(self, banks: dict[str, list[Binding]], switch_bindings: dict[str, str], active_bank: str) -> None:
        self._banks = banks
        self._switch_bindings = switch_bindings
        self._active_bank = active_bank
        self._rebuild_bindings()

    def _rebuild_bindings(self) -> None:
        merged: dict[str, Binding] = {}
        for binding in self._banks.get(self._active_bank, []):
            merged[binding.control] = binding
        for control, bank_id in self._switch_bindings.items():
            merged[control] = Binding(control=control, type="trigger", action="switch_bank", params={"bank_id": bank_id})
        self._bindings_by_control = merged

    @property
    def bindings(self) -> dict[str, Binding]:
        return dict(self._bindings_by_control)

    @property
    def active_bank(self) -> str:
        return self._active_bank

    def switch_bank(self, bank_id: str) -> None:
        if bank_id not in self._banks or bank_id == self._active_bank:
            return
        self._active_bank = bank_id
        self._rebuild_bindings()
        if self._on_bank_changed is not None:
            self._on_bank_changed(bank_id)

    def trigger(self, control: str) -> None:
        binding = self._bindings_by_control.get(control)
        if binding is None:
            logger.info("no binding for control %s", control)
            return
        if binding.action == "switch_bank":
            self.switch_bank(binding.params["bank_id"])
            self._report_trigger(control, True)
            return
        handler = self._trigger_handlers.get(binding.action)
        if handler is None:
            logger.warning("no trigger handler registered for action %s", binding.action)
            return
        try:
            handler(binding.params)
        except Exception:
            logger.warning("trigger handler for %s failed", binding.action, exc_info=True)
            self._report_trigger(control, False)
            return
        self._report_trigger(control, True)

    def _report_trigger(self, control: str, ok: bool) -> None:
        if self._on_trigger is not None:
            self._on_trigger(control, ok)

    def set_continuous(self, control: str, value: float) -> None:
        if self._on_continuous is not None:
            self._on_continuous(control, value)
        binding = self._bindings_by_control.get(control)
        if binding is None:
            return
        handler = self._continuous_handlers.get(binding.action)
        if handler is None:
            logger.warning("no continuous handler registered for action %s", binding.action)
            return
        handler(binding.params, value)
