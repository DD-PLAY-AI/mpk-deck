import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from mpk_deck.ui.main_window import MainWindow


def main() -> None:
    load_dotenv()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(680, 420)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
