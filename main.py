# // FILE: main.py
import sys
import platform

import logging

# TODO: Verify if this fallback actually works on user machines without crashing immediately
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from PySide6.QtCore import Qt
except ImportError:
    print("CRITICAL: PySide6 is not installed. Please run 'pip install -r requirements.txt'")
    sys.exit(1)

from qt_gui import MainWindow

# NOTE: Logging config is basic for now, maybe add rotating file handler later?
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("gamebeam.log", mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting GameStream Pro (Qt / Sunshine Launcher)...")

    app = QApplication(sys.argv)

    # Theme setup moved to MainWindow to keep this clean
    app.setApplicationName("GameBeam")
    app.setOrganizationName("GameBeam")
    # NOTE: Qt6 handles HighDPI mostly automatically now, so explicit attribute setting removed.

    window = MainWindow()
    window.show()

    try:
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Fatal error in Qt main loop: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
