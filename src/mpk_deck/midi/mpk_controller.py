import logging

import mido

from mpk_deck.core.action_engine import ActionEngine
from mpk_deck.midi.translator import translate

logger = logging.getLogger(__name__)

# Ports whose device vanished while still open. Closing an rtmidi WinMM port after
# the device is physically unplugged crashes the process at the C level
# (midiInClose / midiInUnprepareHeader), past any Python-level guard - so we drop
# the reference here and never touch it again (keeping it referenced also stops
# __dealloc__ from running the same doomed close). Bounded leak: one dead port per
# unplug per process.
# ponytail: per-session leak on hot-unplug; only matters if something unplugs hundreds of times.
_ABANDONED_PORTS: list = []


class MPKController:
    def __init__(self, action_engine: ActionEngine, port_name_contains: str = "MPK mini") -> None:
        self._engine = action_engine
        self._port_name_contains = port_name_contains
        self._port = None

    def find_port_name(self, *, log: bool = True) -> str | None:
        try:
            names = mido.get_input_names()
        except Exception:
            if log:
                logger.warning("no MIDI backend available")
            return None
        for name in names:
            if self._port_name_contains.lower() in name.lower():
                return name
        return None

    def start(self, *, log: bool = True) -> bool:
        name = self.find_port_name(log=log)
        if name is None:
            if log:
                logger.warning("MPK mini MK2 not found among MIDI inputs")
            return False
        try:
            self._port = mido.open_input(name, callback=self._on_message)
        except Exception:
            if log:
                logger.warning("failed to open MIDI port %s", name, exc_info=True)
            self._port = None
            return False
        self._install_error_callback()
        logger.info("listening on MIDI port %s", name)
        return True

    def _install_error_callback(self) -> None:
        try:
            rt = getattr(self._port, "_rt", None)
            if rt is None or not hasattr(rt, "set_error_callback"):
                return
            rt.set_error_callback(self._on_rtmidi_error)
        except Exception:
            logger.debug("failed to install MIDI backend error callback", exc_info=True)

    def _on_rtmidi_error(self, error_type, message, _data=None) -> None:
        logger.warning("MIDI backend error (%s): %s", error_type, message)

    def stop(self) -> None:
        if self._port is None:
            return
        if self.find_port_name(log=False) is None:
            # Device already gone - closing it would crash the process (see
            # _ABANDONED_PORTS). Drop it without touching the C layer.
            self._abandon_port()
            return
        try:
            self._port.close()
        except Exception:
            logger.debug("error closing MIDI port; abandoning it", exc_info=True)
            _ABANDONED_PORTS.append(self._port)
        self._port = None

    def _abandon_port(self) -> None:
        """Drop a port whose device physically disappeared, without closing it
        (see _ABANDONED_PORTS). A fresh port is opened on the next reconnect."""
        if self._port is not None:
            _ABANDONED_PORTS.append(self._port)
            self._port = None

    def poll_connection(self) -> bool:
        """Check device presence and open/close the port as needed. Returns the new connected state.

        Cheap: only re-enumerates MIDI input names, doesn't touch the MIDI message stream.
        Safe to call both from a periodic timer and from a manual "retry" click. Silent on repeat
        failure (the caller's connection-status UI is the steady-state indicator, not the log).
        """
        if self._port is not None:
            if self.find_port_name(log=False) is None:
                self._abandon_port()
            return self._port is not None
        return self.start(log=False)

    def _on_message(self, message: mido.Message) -> None:
        try:
            event = translate(message)
            if event is None:
                return
            if event.kind == "trigger":
                self._engine.trigger(event.control)
            else:
                self._engine.set_continuous(event.control, event.value)
        except Exception:
            logger.warning("error handling MIDI input callback", exc_info=True)
