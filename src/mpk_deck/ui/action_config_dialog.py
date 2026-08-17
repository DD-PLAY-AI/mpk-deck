from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from mpk_deck.core.action_registry import Binding

ACTION_CHOICES = ["launch_program", "open_url", "focus_window", "set_system_volume"]
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
}


class ActionConfigDialog(QDialog):
    def __init__(self, control: str, existing: Binding | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure {control}")
        self._control = control

        self._action_combo = QComboBox(self)
        self._action_combo.addItems(ACTION_CHOICES)
        self._param_edit = QLineEdit(self)
        self._browse_button = QPushButton("Browse...", self)
        self._browse_button.clicked.connect(self._browse_for_path)

        if existing is not None:
            self._action_combo.setCurrentText(existing.action)
            key = PARAM_KEY.get(existing.action)
            if key:
                self._param_edit.setText(str(existing.params.get(key, "")))

        form = QFormLayout(self)
        form.addRow("Action", self._action_combo)
        form.addRow("Param", self._param_edit)
        form.addRow("", self._browse_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse_for_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose program")
        if path:
            self._param_edit.setText(path)

    def result_binding(self) -> Binding:
        action = self._action_combo.currentText()
        key = PARAM_KEY.get(action)
        params = {key: self._param_edit.text()} if key else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)
