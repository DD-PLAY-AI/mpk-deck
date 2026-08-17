import sys

from PySide6.QtWidgets import QApplication

from mpk_deck.ui.expanded_view import ExpandedView

app = QApplication(sys.argv)
view = ExpandedView()
view.resize(640, 380)
view.show()
sys.exit(app.exec())
