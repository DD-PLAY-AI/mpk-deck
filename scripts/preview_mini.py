import sys

from PySide6.QtWidgets import QApplication

from mpk_deck.ui.mini_view import MiniView

app = QApplication(sys.argv)
view = MiniView(labels={"pad_1": "DEV", "pad_2": "TRADE", "pad_3": "WEB", "pad_4": "MUSIC"})
view.resize(260, 160)
view.show()
sys.exit(app.exec())
