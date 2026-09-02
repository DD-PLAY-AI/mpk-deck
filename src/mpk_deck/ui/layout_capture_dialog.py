"""Capture the current open windows into a named Workspace Layout.

Same glass styling as ActionConfigDialog. A checklist of open windows (from
core.window_layout.list_open_windows); browser rows show an editable URL field
pre-filled from the best-effort UIA read, so the user fills in whatever the
address bar couldn't give us.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mpk_deck.config import ACCENT_HEX, LAYOUTS_PATH
from mpk_deck.core.layout_store import Layout, LayoutItem, generate_layout_id, load_layouts, save_layouts
from mpk_deck.core.window_layout import OpenWindow, capture_item, list_open_windows
from mpk_deck.ui.action_config_dialog import _dialog_qss


@dataclass
class _CaptureRow:
    checkbox: QCheckBox
    item: LayoutItem
    url_edit: "QLineEdit | None"
    window: OpenWindow


class LayoutCaptureDialog(QDialog):
    def __init__(
        self,
        existing_id: str | None = None,
        accent_hex: str = ACCENT_HEX,
        dark: bool = True,
        parent: QWidget | None = None,
        *,
        window_lister=None,
        url_reader=None,
    ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(540)
        self._existing_id = existing_id
        self._result_id: str | None = None
        self._url_reader = url_reader
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
        root.setSpacing(12)

        heading = QLabel("레이아웃 저장")
        heading.setObjectName("controlId")
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("레이아웃 이름")
        root.addWidget(heading)
        root.addWidget(self._name_edit)
        label = QLabel("포함할 창")
        label.setObjectName("fieldLabel")
        root.addWidget(label)

        self._rows: list[_CaptureRow] = []
        rows_container = QWidget()
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(6)
        for window in (window_lister or list_open_windows)():
            row = self._make_row(window)
            self._rows.append(row)
            rows_layout.addWidget(self._row_widget(row))
        rows_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(rows_container)
        scroll.setMinimumHeight(220)
        root.addWidget(scroll, stretch=1)

        self._error = QLabel("")
        self._error.setObjectName("nlError")
        root.addWidget(self._error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setObjectName("primary")
        save.clicked.connect(self._on_save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        if existing_id is not None:
            existing = load_layouts(LAYOUTS_PATH).get(existing_id)
            if existing is not None:
                self._name_edit.setText(existing.name)

    # frameless drag
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ----------------------------------------------------------------- rows --

    def _make_row(self, window: OpenWindow) -> _CaptureRow:
        item = (
            capture_item(window, url_reader=self._url_reader)
            if self._url_reader is not None
            else capture_item(window)
        )
        url_edit = None
        if item.kind == "url":
            url_edit = QLineEdit(item.url)
            url_edit.setPlaceholderText("https://…  (URL을 못 읽었으면 직접 입력)")
        return _CaptureRow(checkbox=QCheckBox(), item=item, url_edit=url_edit, window=window)

    def _row_widget(self, row: _CaptureRow) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(row.checkbox)
        title = QLabel(row.window.title)
        title.setMinimumWidth(150)
        title.setMaximumWidth(220)
        lay.addWidget(title)
        if row.url_edit is not None:
            lay.addWidget(row.url_edit, stretch=1)
        else:
            dims = QLabel(f"{row.window.rect[2]}×{row.window.rect[3]}")
            dims.setObjectName("hint")
            lay.addWidget(dims)
            lay.addStretch(1)
        return w

    # ------------------------------------------------------------- save/state --

    def _can_save(self) -> bool:
        if not self._name_edit.text().strip():
            return False
        return not any(
            r.checkbox.isChecked() and r.url_edit is not None and not r.url_edit.text().strip()
            for r in self._rows
        )

    def _build_layout(self) -> Layout:
        items: list[LayoutItem] = []
        for r in self._rows:
            if not r.checkbox.isChecked():
                continue
            item = r.item
            if r.url_edit is not None:
                item = LayoutItem(
                    kind="url",
                    url=r.url_edit.text().strip(),
                    browser=item.browser,
                    rect=item.rect,
                    maximized=item.maximized,
                    title_match=item.title_match,
                )
            items.append(item)
        return Layout(name=self._name_edit.text().strip(), items=items)

    def _on_save(self) -> None:
        if not self._can_save():
            self._error.setText("이름을 입력하고, 체크한 브라우저 창엔 URL을 채워주세요.")
            return
        layouts = load_layouts(LAYOUTS_PATH)
        layout = self._build_layout()
        layout_id = self._existing_id or generate_layout_id(layout.name, layouts.keys())
        layouts[layout_id] = layout
        save_layouts(layouts, LAYOUTS_PATH)
        self._result_id = layout_id
        self.accept()

    def result_layout_id(self) -> str | None:
        return self._result_id
