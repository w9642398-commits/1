"""Entry point for RailTrack application."""
import sys


def main():
    from PySide6.QtWidgets import QApplication
    from railtrack.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("RailTrack")
    app.setApplicationVersion("0.1.0")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
