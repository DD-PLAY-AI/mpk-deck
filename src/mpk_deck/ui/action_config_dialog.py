from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mpk_deck.config import ACCENT_HEX
from mpk_deck.core.action_registry import Binding
from mpk_deck.core.nl_action import parse_nl_action
from mpk_deck.core.program_finder import list_installed_programs

ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
    ("scroll_horizontal", "↔", "Scroll Horizontal"),
    ("scroll_vertical", "↕", "Scroll Vertical"),
    ("switch_bank", "➕", "Add Bank"),
]
ACTION_GLYPHS = {name: glyph for name, glyph, _ in ACTION_CHOICES}
ACTION_LABELS = {name: label for name, _, label in ACTION_CHOICES}
ACTION_TYPE = {
    "launch_program": "trigger",
    "open_url": "trigger",
    "focus_window": "trigger",
    "set_system_volume": "continuous",
    "scroll_horizontal": "continuous",
    "scroll_vertical": "continuous",
    "switch_bank": "trigger",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
    "scroll_horizontal": None,
    "scroll_vertical": None,
    "switch_bank": None,
}

def _dialog_qss(accent_hex: str) -> str:
    return f"""
QDialog {{ background: #1c1e26; }}
QLabel {{ color: #f2f4f8; font-size: 12px; }}
QLabel#heading {{ font-size: 14px; font-weight: 600; }}
QLabel#nlError {{ color: #ff6b6b; font-size: 11px; }}
QListWidget {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 8px;
    color: #f2f4f8;
    font-size: 12px;
    outline: none;
}}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {accent_hex}; color: white; }}
QListWidget::item:hover:!selected {{ background: #2c2e38; }}
QLineEdit {{
    background: #23242b;
    border: 1px solid #33343d;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 8px;
    font-size: 12px;
}}
QPushButton {{
    background: #2c2e38;
    border: 1px solid #3a3c47;
    border-radius: 6px;
    color: #f2f4f8;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{ background: #363844; }}
QPushButton#primary {{ background: {accent_hex}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: #4b7bf5; }}
"""


class ActionConfigDialog(QDialog):
    def __init__(
        self,
        control: str,
        existing: Binding | None = None,
        parent: QWidget | None = None,
        bank_names: dict[str, str] | None = None,
        accent_hex: str = ACCENT_HEX,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure {control}")
        self.setMinimumSize(480, 320)
        self.setStyleSheet(_dialog_qss(accent_hex))
        self._control = control
        self._bank_names = bank_names or {}
        self._locked = existing is not None and existing.action == "switch_bank"

        heading = QLabel(f"Configure {control}")
        heading.setObjectName("heading")

        self._action_list = QListWidget(self)
        self._action_list.setFixedWidth(170)
        for action_name, glyph, label in ACTION_CHOICES:
            item = QListWidgetItem(f"{glyph}  {label}")
            item.setData(Qt.ItemDataRole.UserRole, action_name)
            self._action_list.addItem(item)
        self._action_list.currentRowChanged.connect(self._on_action_changed)

        self._param_stack = QStackedWidget(self)
        self._path_edit = self._build_program_picker_page()
        self._url_edit = self._build_line_edit_page("https://example.com")
        self._title_edit = self._build_line_edit_page("Window title contains...")
        self._volume_page = self._build_volume_page()
        self._bank_name_edit = self._build_bank_name_page()
        self._sensitivity_edit = self._build_sensitivity_page()
        # Which _param_stack page each action shows. The action list has 7 rows but
        # only 6 pages (both scroll actions share the sensitivity page), so the row
        # index is NOT the page index - map by action name. Order matches the
        # _build_* calls above.
        self._page_for_action = {
            "launch_program": 0,
            "open_url": 1,
            "focus_window": 2,
            "set_system_volume": 3,
            "switch_bank": 4,
            "scroll_horizontal": 5,
            "scroll_vertical": 5,
        }

        body = QHBoxLayout()
        body.addWidget(self._action_list)
        body.addWidget(self._param_stack, stretch=1)

        self._nl_edit = QLineEdit(self)
        self._nl_edit.setPlaceholderText("or describe what you want...")
        self._nl_generate_btn = QPushButton("Generate", self)
        self._nl_generate_btn.clicked.connect(self._on_generate_clicked)
        self._nl_error = QLabel("", self)
        self._nl_error.setObjectName("nlError")

        nl_row = QHBoxLayout()
        nl_row.addWidget(self._nl_edit, stretch=1)
        nl_row.addWidget(self._nl_generate_btn)

        buttons = QDialogButtonBox(self)
        ok_button = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        ok_button.setObjectName("primary")
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)
        root.addWidget(heading)
        root.addLayout(nl_row)
        root.addWidget(self._nl_error)
        root.addLayout(body, stretch=1)
        root.addWidget(buttons)

        if existing is not None:
            self._apply_binding(existing)
        else:
            self._select_action(ACTION_CHOICES[0][0])
        if self._locked:
            self._lock_to_switch_bank()

    def _build_program_picker_page(self) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        search = QLineEdit(page)
        search.setPlaceholderText("Search installed programs...")
        program_list = QListWidget(page)
        for program in list_installed_programs():
            item = QListWidgetItem(program.name)
            item.setData(Qt.ItemDataRole.UserRole, program.path)
            program_list.addItem(item)

        path_edit = QLineEdit(page)
        path_edit.setPlaceholderText("Selected program path")
        browse_button = QPushButton("Browse...", page)

        def filter_programs(text: str) -> None:
            text = text.lower()
            for i in range(program_list.count()):
                item = program_list.item(i)
                item.setHidden(text not in item.text().lower())

        def select_program(item: QListWidgetItem) -> None:
            path_edit.setText(item.data(Qt.ItemDataRole.UserRole))

        def browse() -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Choose program")
            if path:
                path_edit.setText(path)

        search.textChanged.connect(filter_programs)
        program_list.itemClicked.connect(select_program)
        browse_button.clicked.connect(browse)

        browse_row = QHBoxLayout()
        browse_row.addWidget(path_edit, stretch=1)
        browse_row.addWidget(browse_button)

        layout.addWidget(search)
        layout.addWidget(program_list, stretch=1)
        layout.addLayout(browse_row)
        self._param_stack.addWidget(page)
        return path_edit

    def _build_line_edit_page(self, placeholder: str) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(page)
        edit.setPlaceholderText(placeholder)
        layout.addWidget(edit)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit

    def _build_volume_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Controls system volume as the knob turns. No extra settings needed.", page))
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return page

    def _build_bank_name_page(self) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(page)
        edit.setPlaceholderText("Bank name")
        layout.addWidget(edit)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit

    def _build_sensitivity_page(self) -> QLineEdit:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Scroll sensitivity (0.1 - 3.0, default 1.0):", page))
        edit = QLineEdit(page)
        edit.setText("1.0")
        layout.addWidget(edit)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit

    def _param_edit_for(self, action: str) -> QLineEdit | None:
        return {"launch_program": self._path_edit, "open_url": self._url_edit, "focus_window": self._title_edit}.get(
            action
        )

    def _select_action(self, action: str) -> None:
        index = next((i for i, (name, _, _) in enumerate(ACTION_CHOICES) if name == action), 0)
        self._action_list.setCurrentRow(index)

    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
        if binding.action == "switch_bank":
            bank_id = binding.params.get("bank_id", "")
            self._bank_name_edit.setText(self._bank_names.get(bank_id, ""))
            return
        if binding.action in ("scroll_horizontal", "scroll_vertical"):
            self._sensitivity_edit.setText(str(binding.params.get("sensitivity", 1.0)))
            return
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))

    def _lock_to_switch_bank(self) -> None:
        for i in range(self._action_list.count()):
            item = self._action_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) != "switch_bank":
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._nl_edit.setEnabled(False)
        self._nl_generate_btn.setEnabled(False)

    def _on_generate_clicked(self) -> None:
        text = self._nl_edit.text()
        self._nl_error.setText("")
        self._nl_generate_btn.setEnabled(False)
        self._nl_generate_btn.repaint()
        try:
            binding = parse_nl_action(text, list_installed_programs())
        finally:
            self._nl_generate_btn.setEnabled(True)

        if binding is None:
            self._nl_error.setText("Couldn't figure that out - try rephrasing, or check ANTHROPIC_API_KEY in .env")
            return
        self._apply_binding(binding)

    def _on_action_changed(self, index: int) -> None:
        self._param_stack.setCurrentIndex(self._page_for_action.get(self._current_action(), 0))

    def _current_action(self) -> str:
        item = self._action_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ACTION_CHOICES[0][0]

    def result_binding(self) -> Binding:
        action = self._current_action()
        if self._locked or action == "switch_bank":
            # The real bank_id is assigned by the caller (new bank, or the existing
            # locked control's target) - this dialog only ever supplies the name.
            return Binding(control=self._control, type="trigger", action="switch_bank", params={})
        if action in ("scroll_horizontal", "scroll_vertical"):
            try:
                sensitivity = float(self._sensitivity_edit.text())
            except ValueError:
                sensitivity = 1.0
            sensitivity = max(0.1, min(3.0, sensitivity))
            return Binding(control=self._control, type="continuous", action=action, params={"sensitivity": sensitivity})
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text()} if key and edit else {}
        return Binding(control=self._control, type=ACTION_TYPE[action], action=action, params=params)

    def result_bank_name(self) -> str:
        return self._bank_name_edit.text().strip()
