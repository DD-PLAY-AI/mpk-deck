from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mpk_deck.config import ACCENT_HEX
from mpk_deck.core.action_registry import Binding
from mpk_deck.core.nl_action import parse_nl_action
from mpk_deck.core.program_finder import list_installed_programs
from mpk_deck.core.icon_gen import generate_icon_svg
from mpk_deck.core.layout_store import load_layouts
from mpk_deck.ui.accent import hex_to_rgb_str, mix
from mpk_deck.ui.action_icons import ACTION_KO_LABEL, action_label, action_pixmap, render_svg_icon
from mpk_deck.ui.knob_geometry import needle_angle

ACTION_CHOICES = [
    ("launch_program", "\U0001f680", "Launch Program"),
    ("open_url", "\U0001f310", "Open URL"),
    ("focus_window", "\U0001fa9f", "Focus Window"),
    ("set_system_volume", "\U0001f50a", "System Volume"),
    ("scroll_horizontal", "↔", "Scroll Horizontal"),
    ("scroll_vertical", "↕", "Scroll Vertical"),
    ("apply_layout", "\U0001f5c2", "Layout"),
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
    "apply_layout": "trigger",
    "switch_bank": "trigger",
}
PARAM_KEY = {
    "launch_program": "path",
    "open_url": "url",
    "focus_window": "title_contains",
    "set_system_volume": None,
    "scroll_horizontal": None,
    "scroll_vertical": None,
    "apply_layout": None,
    "switch_bank": None,
}

SENSITIVITY_MIN, SENSITIVITY_MAX = 0.1, 3.0


def control_display_id(control: str) -> str:
    """'pad_3' -> 'PAD 3', 'joystick_x' -> 'JOYSTICK X', 'key_5' -> 'KEY 5'."""
    kind, _, rest = control.partition("_")
    return f"{kind.upper()} {rest.upper()}".strip()


def _kind_of(control: str) -> str:
    return control.split("_")[0]


def _dialog_qss(accent_hex: str, dark: bool) -> str:
    accent_rgb = hex_to_rgb_str(accent_hex)
    if dark:
        card_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(20,22,28,245), stop:1 rgba(10,12,16,238))"
        ink, muted = "#f2f4f8", "rgba(242,244,248,130)"
        field_bg, field_line = "rgba(255,255,255,16)", "rgba(255,255,255,36)"
        tile_bg, tile_line = "rgba(255,255,255,13)", "rgba(255,255,255,30)"
        popup_bg = "#23262f"
    else:
        card_bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(255,255,255,240), stop:1 rgba(235,240,255,246))"
        ink, muted = "#23242b", "rgba(35,36,43,140)"
        field_bg, field_line = "rgba(255,255,255,180)", "rgba(120,120,140,80)"
        tile_bg, tile_line = "rgba(255,255,255,140)", "rgba(120,120,140,70)"
        popup_bg = "#f4f6fb"
    return f"""
QWidget#card {{
    background: {card_bg};
    border: 1px solid rgba({accent_rgb}, 110);
    border-radius: 18px;
}}
QLabel {{ color: {ink}; font-size: 12px; }}
QLabel#controlId {{ color: {accent_hex}; font-size: 12px; font-weight: 600; letter-spacing: 1px; }}
QLabel#nowBinding {{ font-size: 14px; font-weight: 600; }}
QLabel#nowBinding[empty="true"] {{ color: {muted}; font-weight: 400; }}
QLabel#fieldLabel {{
    color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}}
QLabel#hint {{ color: {muted}; font-size: 11px; }}
QLabel#nlError {{ color: #ff6b6b; font-size: 11px; }}

QLineEdit, QListWidget, QTextEdit {{
    background: {field_bg};
    border: 1px solid {field_line};
    border-radius: 8px;
    color: {ink};
    font-size: 12px;
    padding: 6px 8px;
    selection-background-color: {accent_hex};
}}
QLineEdit:focus, QListWidget:focus, QTextEdit:focus {{ border: 1px solid {accent_hex}; }}
QListWidget::item {{ padding: 5px 7px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {accent_hex}; color: white; }}
QListWidget::item:hover:!selected {{ background: rgba({accent_rgb}, 30); }}

QFrame#paramFrame {{
    background: {field_bg};
    border: 1px solid {field_line};
    border-radius: 12px;
}}

QToolButton#tile {{
    background: {tile_bg};
    border: 1px solid {tile_line};
    border-radius: 11px;
    color: {ink};
    font-size: 10px;
    padding: 6px 2px;
}}
QToolButton#tile:hover {{ background: rgba({accent_rgb}, 26); }}
QToolButton#tile:checked {{ border: 1px solid {accent_hex}; background: rgba({accent_rgb}, 36); }}

QToolButton#nlToggle {{
    border: none; background: transparent; color: {accent_hex};
    font-size: 12px; font-weight: 600; padding: 0;
}}

QPushButton#ghost, QPushButton#primary {{
    border-radius: 9px; font-size: 12px; font-weight: 600; padding: 7px 18px;
}}
QPushButton#ghost {{ background: transparent; border: 1px solid {field_line}; color: {ink}; }}
QPushButton#ghost:hover {{ background: rgba({accent_rgb}, 22); }}
QPushButton#primary {{ background: {accent_hex}; border: none; color: white; }}
QPushButton#primary:hover {{ background: {mix(accent_hex, (255, 255, 255), 0.16)}; }}

QSlider::groove:horizontal {{ height: 4px; background: {field_line}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; background: {accent_hex};
}}
QSlider::sub-page:horizontal {{ background: {accent_hex}; border-radius: 2px; }}

QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {field_line}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollArea {{ background: transparent; border: none; }}
QCheckBox {{ color: {ink}; }}
QComboBox {{
    background: {field_bg}; border: 1px solid {field_line}; border-radius: 6px;
    color: {ink}; padding: 5px 8px; font-size: 12px;
}}
QComboBox:focus {{ border: 1px solid {accent_hex}; }}
QComboBox QAbstractItemView {{
    background: {popup_bg}; color: {ink}; border: 1px solid {field_line};
    selection-background-color: {accent_hex}; selection-color: white;
}}
"""


class _ControlChip(QWidget):
    """A small painted replica of the physical control being wired - the same
    shape and accent treatment it has on the deck, so the dialog reads as
    'you're patching THIS pad', not editing an abstract row."""

    def __init__(self, control: str, accent_hex: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = _kind_of(control)
        self._accent = accent_hex
        self._action_pixmap = None
        self.setFixedSize(58, 58)

    def set_action(self, binding: Binding) -> None:
        self._action_pixmap = action_pixmap(binding, 26, self._accent)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self._accent)
        rect = self.rect().adjusted(3, 3, -3, -3)

        pen = QPen(accent, 2)
        painter.setPen(pen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 28))

        if self._kind == "knob":
            painter.drawEllipse(rect)
            painter.save()
            painter.translate(QPointF(self.width() / 2, self.height() / 2))
            painter.rotate(needle_angle(0.5))
            npen = QPen(accent, 3)
            npen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(npen)
            painter.drawLine(QPointF(0, 3), QPointF(0, -rect.height() / 2 + 6))
            painter.restore()
        elif self._kind == "joystick":
            painter.drawEllipse(rect)
            painter.setBrush(accent)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(self.width() / 2 + 8, self.height() / 2), 5, 5)
        elif self._kind == "key":
            painter.drawRoundedRect(rect.adjusted(9, 0, -9, 0), 4, 4)
        else:  # pad
            painter.drawRoundedRect(rect, 12, 12)

        if self._action_pixmap is not None:
            pm = self._action_pixmap
            painter.drawPixmap(
                round((self.width() - pm.width()) / 2), round((self.height() - pm.height()) / 2), pm
            )


class ActionConfigDialog(QDialog):
    def __init__(
        self,
        control: str,
        existing: Binding | None = None,
        parent: QWidget | None = None,
        bank_names: dict[str, str] | None = None,
        accent_hex: str = ACCENT_HEX,
        dark: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Configure {control}")
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(468)
        self._control = control
        self._bank_names = bank_names or {}
        self._accent_hex = accent_hex
        self._locked = existing is not None and existing.action == "switch_bank"
        self._drag_offset = None

        card = QWidget(self)
        card.setObjectName("card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet(_dialog_qss(accent_hex, dark))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(16)

        root.addLayout(self._build_header(existing))
        root.addLayout(self._build_action_picker())
        root.addWidget(self._build_param_stack())
        root.addLayout(self._build_name_field(existing))
        root.addWidget(self._build_nl_section())
        root.addLayout(self._build_buttons())

        if existing is not None:
            self._apply_binding(existing)
        else:
            self._select_action(ACTION_CHOICES[0][0])
        if self._locked:
            self._lock_to_switch_bank()

    # frameless: drag the card from any empty area to move the dialog
    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ---- header: control chip + id + current binding -----------------------

    def _build_header(self, existing: Binding | None) -> QHBoxLayout:
        self._chip = _ControlChip(self._control, self._accent_hex)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        control_id = QLabel(control_display_id(self._control))
        control_id.setObjectName("controlId")
        self._now_label = QLabel()
        self._now_label.setObjectName("nowBinding")
        self._set_now_binding(existing)
        meta.addStretch(1)
        meta.addWidget(control_id)
        meta.addWidget(self._now_label)
        meta.addStretch(1)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._chip)
        row.addLayout(meta, stretch=1)
        return row

    def _build_name_field(self, existing: Binding | None) -> QVBoxLayout:
        self._custom_icon = existing.icon if existing is not None else ""

        col = QVBoxLayout()
        col.setSpacing(6)
        label = QLabel("이름")
        label.setObjectName("fieldLabel")
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("비워두면 자동 (프로그램 이름 등)")
        if existing is not None and existing.label:
            self._label_edit.setText(existing.label)
        col.addWidget(label)
        col.addWidget(self._label_edit)

        icon_label = QLabel("아이콘")
        icon_label.setObjectName("fieldLabel")
        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(30, 30)
        self._icon_preview.setScaledContents(True)
        default_btn = QPushButton("기본")
        default_btn.setObjectName("ghost")
        default_btn.clicked.connect(self._clear_custom_icon)
        self._icon_ai_toggle = QToolButton()
        self._icon_ai_toggle.setObjectName("nlToggle")
        self._icon_ai_toggle.setText("✨ AI로 만들기")
        self._icon_ai_toggle.setCheckable(True)
        self._icon_ai_toggle.toggled.connect(self._on_icon_ai_toggled)
        self._icon_default_btn = default_btn
        icon_row = QHBoxLayout()
        icon_row.setSpacing(8)
        icon_row.addWidget(self._icon_preview)
        icon_row.addWidget(default_btn)
        icon_row.addWidget(self._icon_ai_toggle)
        icon_row.addStretch(1)

        self._icon_ai_row = QWidget()
        ai = QHBoxLayout(self._icon_ai_row)
        ai.setContentsMargins(0, 0, 0, 0)
        ai.setSpacing(6)
        self._icon_desc_edit = QLineEdit()
        self._icon_desc_edit.setPlaceholderText("무엇을 그릴까요 (예: 상승 차트)")
        self._icon_gen_btn = QPushButton("생성")
        self._icon_gen_btn.setObjectName("primary")
        self._icon_gen_btn.clicked.connect(self._on_generate_icon)
        ai.addWidget(self._icon_desc_edit, stretch=1)
        ai.addWidget(self._icon_gen_btn)
        self._icon_ai_row.setVisible(False)
        self._icon_error = QLabel("")
        self._icon_error.setObjectName("nlError")

        col.addSpacing(4)
        col.addWidget(icon_label)
        col.addLayout(icon_row)
        col.addWidget(self._icon_ai_row)
        col.addWidget(self._icon_error)
        self._refresh_icon_preview()
        return col

    def _on_icon_ai_toggled(self, checked: bool) -> None:
        self._icon_ai_row.setVisible(checked)
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def _set_metadata_enabled(self, enabled: bool) -> None:
        """switch_bank has no slot for a custom label/icon (its label is the bank
        name), so grey those controls out rather than silently discarding them."""
        for w in (self._label_edit, self._icon_default_btn, self._icon_ai_toggle, self._icon_preview):
            w.setEnabled(enabled)
        if not enabled and self._icon_ai_toggle.isChecked():
            self._icon_ai_toggle.setChecked(False)

    def _clear_custom_icon(self) -> None:
        self._custom_icon = ""
        self._icon_error.setText("")
        self._refresh_icon_preview()
        self._refresh_chip(self._current_action())

    def _refresh_icon_preview(self) -> None:
        if self._custom_icon:
            pm = render_svg_icon(self._custom_icon, 30, self._accent_hex)
        else:
            pm = action_pixmap(
                Binding(control=self._control, type="trigger", action=self._current_action(), params={}),
                30, self._accent_hex,
            )
        if pm is not None:
            self._icon_preview.setPixmap(pm)

    def _on_generate_icon(self) -> None:
        desc = self._icon_desc_edit.text().strip()
        self._icon_error.setText("")
        self._icon_gen_btn.setEnabled(False)
        self._icon_gen_btn.repaint()
        try:
            svg = generate_icon_svg(desc)
        finally:
            self._icon_gen_btn.setEnabled(True)
        if svg is None or render_svg_icon(svg, 30, self._accent_hex) is None:
            self._icon_error.setText("아이콘을 만들지 못했어요 — 다르게 말해보거나 .env의 ANTHROPIC_API_KEY를 확인하세요")
            return
        self._custom_icon = svg
        self._refresh_icon_preview()
        self._refresh_chip(self._current_action())

    def _set_now_binding(self, existing: Binding | None) -> None:
        if existing is None:
            self._now_label.setText("비어 있음")
            self._now_label.setProperty("empty", "true")
            return
        text = action_label(existing, self._bank_names)
        key = PARAM_KEY.get(existing.action)
        detail = str(existing.params.get(key, "")) if key else ""
        if detail and detail != text:
            text += f" · {detail}"
        self._now_label.setText(text)
        self._now_label.setProperty("empty", "false")

    # ---- action picker: icon tiles ----------------------------------------

    def _build_action_picker(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(9)
        heading = QLabel("무엇을 할까요")
        heading.setObjectName("fieldLabel")
        wrap.addWidget(heading)

        grid = QGridLayout()
        grid.setSpacing(8)
        self._action_group = QButtonGroup(self)
        self._action_group.setExclusive(True)
        self._tiles: dict[str, QToolButton] = {}
        for i, (name, _glyph, _label) in enumerate(ACTION_CHOICES):
            tile = QToolButton()
            tile.setObjectName("tile")
            tile.setText(ACTION_KO_LABEL.get(name, name))
            tile.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            tile.setCheckable(True)
            tile.setMinimumHeight(54)
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tile.setIcon(QIcon(action_pixmap(Binding("", "trigger", name, {}), 22, self._accent_hex)))
            tile.setIconSize(QSize(22, 22))
            tile.clicked.connect(lambda _checked, n=name: self._on_action_selected(n))
            self._action_group.addButton(tile)
            self._tiles[name] = tile
            grid.addWidget(tile, i // 4, i % 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        wrap.addLayout(grid)
        return wrap

    # ---- param area: one frame, one page per action ---------------------

    def _build_param_stack(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("paramFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(14, 12, 14, 12)

        self._param_stack = QStackedWidget()
        frame_layout.addWidget(self._param_stack)

        self._path_edit = self._add_program_page()
        self._url_edit = self._add_line_page("open_url", "주소", "https://example.com", "기본 브라우저에서 엽니다.")
        self._title_edit = self._add_line_page(
            "focus_window", "창 제목에 포함된 글자", "예: Chrome", "제목이 일치하는 첫 창을 앞으로 가져옵니다."
        )
        self._add_note_page("set_system_volume", "시스템 볼륨", "노브를 돌리면 시스템 볼륨이 따라갑니다. 추가 설정 없음.")
        self._sensitivity_slider = self._add_sensitivity_page()
        self._bank_name_edit = self._add_line_page("switch_bank", "뱅크 이름", "예: 트레이딩", "이 컨트롤이 해당 뱅크로 영구 전환됩니다.")
        self._add_layout_page()

        # both scroll actions share the sensitivity page; everything else is 1:1
        self._page_for_action = {
            "launch_program": 0,
            "open_url": 1,
            "focus_window": 2,
            "set_system_volume": 3,
            "scroll_horizontal": 4,
            "scroll_vertical": 4,
            "switch_bank": 5,
            "apply_layout": 6,
        }
        return frame

    def _add_layout_page(self) -> None:
        page, layout = self._page_shell("레이아웃")
        self._layout_combo = QComboBox()
        self._reload_layout_combo()
        row = QHBoxLayout()
        save_new = QPushButton("새로 저장…")
        save_new.setObjectName("ghost")
        edit = QPushButton("편집…")
        edit.setObjectName("ghost")
        save_new.clicked.connect(lambda: self._open_capture(None))
        edit.clicked.connect(lambda: self._open_capture(self._layout_combo.currentData()))
        row.addWidget(self._layout_combo, stretch=1)
        row.addWidget(save_new)
        row.addWidget(edit)
        layout.addLayout(row)
        hint = QLabel("저장된 레이아웃을 고르거나 현재 창 배치를 새로 저장하세요.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)
        self._param_stack.addWidget(page)

    def _reload_layout_combo(self) -> None:
        current = self._layout_combo.currentData() if self._layout_combo.count() else None
        self._layout_combo.clear()
        for layout_id, layout in load_layouts().items():
            self._layout_combo.addItem(layout.name, layout_id)
        if current is not None:
            i = self._layout_combo.findData(current)
            if i >= 0:
                self._layout_combo.setCurrentIndex(i)

    def _open_capture(self, existing_id) -> None:
        from mpk_deck.ui.layout_capture_dialog import LayoutCaptureDialog

        dialog = LayoutCaptureDialog(existing_id, accent_hex=self._accent_hex, parent=self)
        if dialog.exec() and dialog.result_layout_id():
            self._reload_layout_combo()
            i = self._layout_combo.findData(dialog.result_layout_id())
            if i >= 0:
                self._layout_combo.setCurrentIndex(i)

    def _page_shell(self, label_text: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        return page, layout

    def _add_line_page(self, action: str, label_text: str, placeholder: str, hint: str) -> QLineEdit:
        page, layout = self._page_shell(label_text)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        layout.addWidget(edit)
        hint_label = QLabel(hint)
        hint_label.setObjectName("hint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return edit

    def _add_note_page(self, action: str, label_text: str, note: str) -> None:
        page, layout = self._page_shell(label_text)
        note_label = QLabel(note)
        note_label.setObjectName("hint")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
        layout.addStretch(1)
        self._param_stack.addWidget(page)

    def _add_sensitivity_page(self) -> QSlider:
        page, layout = self._page_shell("스크롤 감도")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(SENSITIVITY_MIN * 10), int(SENSITIVITY_MAX * 10))
        slider.setValue(10)
        value_label = QLabel("1.0×")
        value_label.setObjectName("hint")
        slider.valueChanged.connect(lambda v: value_label.setText(f"{v / 10:.1f}×"))
        row = QHBoxLayout()
        row.addWidget(slider, stretch=1)
        row.addWidget(value_label)
        layout.addLayout(row)
        hint_label = QLabel("조이스틱을 끝까지 밀었을 때의 스크롤 속도.")
        hint_label.setObjectName("hint")
        layout.addWidget(hint_label)
        layout.addStretch(1)
        self._param_stack.addWidget(page)
        return slider

    def _add_program_page(self) -> QLineEdit:
        page, layout = self._page_shell("프로그램")
        search = QLineEdit()
        search.setPlaceholderText("설치된 프로그램 검색…")
        program_list = QListWidget()
        program_list.setMaximumHeight(96)
        for program in list_installed_programs():
            item = QListWidgetItem(program.name)
            item.setData(Qt.ItemDataRole.UserRole, program.path)
            program_list.addItem(item)

        path_edit = QLineEdit()
        path_edit.setPlaceholderText("선택된 프로그램 경로")
        browse_button = QPushButton("찾아보기…")
        browse_button.setObjectName("ghost")

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
        path_edit.textChanged.connect(lambda: self._refresh_chip(self._current_action()))

        browse_row = QHBoxLayout()
        browse_row.addWidget(path_edit, stretch=1)
        browse_row.addWidget(browse_button)

        layout.addWidget(search)
        layout.addWidget(program_list, stretch=1)
        layout.addLayout(browse_row)
        self._param_stack.addWidget(page)
        return path_edit

    # ---- natural-language: collapsed until asked for --------------------

    def _build_nl_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._nl_toggle = QToolButton()
        self._nl_toggle.setObjectName("nlToggle")
        self._nl_toggle.setText("✨ 말로 설명하기")
        self._nl_toggle.setCheckable(True)
        self._nl_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._nl_toggle.toggled.connect(self._on_nl_toggled)
        layout.addWidget(self._nl_toggle, alignment=Qt.AlignmentFlag.AlignLeft)

        self._nl_body = QWidget()
        body = QVBoxLayout(self._nl_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        self._nl_edit = QLineEdit()
        self._nl_edit.setPlaceholderText("예: 크롬을 열고 유튜브로 이동")
        body.addWidget(self._nl_edit)
        gen_row = QHBoxLayout()
        note = QLabel("Claude Haiku가 제안 · 저장 전 검토")
        note.setObjectName("hint")
        self._nl_generate_btn = QPushButton("만들기")
        self._nl_generate_btn.setObjectName("primary")
        self._nl_generate_btn.clicked.connect(self._on_generate_clicked)
        gen_row.addWidget(note)
        gen_row.addStretch(1)
        gen_row.addWidget(self._nl_generate_btn)
        body.addLayout(gen_row)
        self._nl_error = QLabel("")
        self._nl_error.setObjectName("nlError")
        body.addWidget(self._nl_error)
        self._nl_body.setVisible(False)
        layout.addWidget(self._nl_body)
        return container

    def _on_nl_toggled(self, checked: bool) -> None:
        self._nl_body.setVisible(checked)
        self._nl_toggle.setText(("▾ " if checked else "✨ ") + "말로 설명하기")
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    # ---- footer buttons -------------------------------------------------

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

    # ---- selection / state --------------------------------------------

    def _param_edit_for(self, action: str) -> QLineEdit | None:
        return {
            "launch_program": self._path_edit,
            "open_url": self._url_edit,
            "focus_window": self._title_edit,
        }.get(action)

    def _select_action(self, action: str) -> None:
        tile = self._tiles.get(action)
        if tile is not None:
            tile.setChecked(True)
        self._on_action_selected(action)

    def _on_action_selected(self, action: str) -> None:
        self._param_stack.setCurrentIndex(self._page_for_action.get(action, 0))
        self._set_metadata_enabled(action != "switch_bank")
        self._refresh_chip(action)
        self._refresh_icon_preview()

    def _refresh_chip(self, action: str) -> None:
        params = {}
        if action == "launch_program" and self._path_edit.text().strip():
            params = {"path": self._path_edit.text().strip()}
        self._chip.set_action(
            Binding(control="", type="trigger", action=action, params=params, icon=self._custom_icon)
        )

    def _current_action(self) -> str:
        for name, tile in self._tiles.items():
            if tile.isChecked():
                return name
        return ACTION_CHOICES[0][0]

    def _apply_binding(self, binding: Binding) -> None:
        self._select_action(binding.action)
        if binding.action == "switch_bank":
            bank_id = binding.params.get("bank_id", "")
            self._bank_name_edit.setText(self._bank_names.get(bank_id, ""))
            return
        if binding.action == "apply_layout":
            i = self._layout_combo.findData(binding.params.get("layout_id", ""))
            if i >= 0:
                self._layout_combo.setCurrentIndex(i)
            return
        if binding.action in ("scroll_horizontal", "scroll_vertical"):
            self._sensitivity_slider.setValue(round(float(binding.params.get("sensitivity", 1.0)) * 10))
            return
        key = PARAM_KEY.get(binding.action)
        if key:
            edit = self._param_edit_for(binding.action)
            if edit:
                edit.setText(str(binding.params.get(key, "")))

    def _lock_to_switch_bank(self) -> None:
        for name, tile in self._tiles.items():
            if name != "switch_bank":
                tile.setEnabled(False)
        self._nl_toggle.setEnabled(False)
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
            self._nl_error.setText("이해하지 못했어요 — 다르게 말해보거나 .env의 ANTHROPIC_API_KEY를 확인하세요")
            return
        self._apply_binding(binding)

    # ---- results -----------------------------------------------------

    def result_binding(self) -> Binding:
        action = self._current_action()
        label = self._label_edit.text().strip()
        icon = self._custom_icon
        if self._locked or action == "switch_bank":
            # The real bank_id is assigned by the caller. switch_bank has no slot
            # for a custom label/icon (its label is the bank name) - the UI greys
            # those fields out, so don't carry them here either.
            return Binding(control=self._control, type="trigger", action="switch_bank", params={})
        if action in ("scroll_horizontal", "scroll_vertical"):
            sensitivity = max(SENSITIVITY_MIN, min(SENSITIVITY_MAX, self._sensitivity_slider.value() / 10))
            return Binding(
                control=self._control, type="continuous", action=action,
                params={"sensitivity": sensitivity}, label=label, icon=icon,
            )
        if action == "apply_layout":
            return Binding(
                control=self._control, type="trigger", action="apply_layout",
                params={"layout_id": self._layout_combo.currentData() or ""}, label=label, icon=icon,
            )
        key = PARAM_KEY.get(action)
        edit = self._param_edit_for(action)
        params = {key: edit.text().strip()} if key and edit else {}
        return Binding(
            control=self._control, type=ACTION_TYPE[action], action=action, params=params, label=label, icon=icon
        )

    def result_bank_name(self) -> str:
        return self._bank_name_edit.text().strip()
