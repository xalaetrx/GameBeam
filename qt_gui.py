# // FILE: qt_gui.py
import os
import platform

from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QApplication,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QProgressBar,
    QFrame,
)
from PySide6.QtGui import QPalette, QColor, QFont
import logging

logger = logging.getLogger(__name__)
from utils import get_local_ip, encode_connection_code, decode_connection_code
from sunshine import SunshineManager, SunshineInstaller, SunshineAPI
from moonlight import MoonlightInstaller, MoonlightRunner


CONFIG_FILE = "gb_config.txt"


# =========================
# Helpers: config load/save
# NOTE: Config handling is primitive. Maybe switch to JSON or TOML if this file grows?
# =========================

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        cfg[k] = v.strip()
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            for k, v in cfg.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        logger.warning(f"Failed to save config: {e}")


# =========================
# Threads / Workers
# =========================

class SunshineStatusWorker(QThread):
    result = Signal(bool)

    def run(self):
        running = SunshineManager.is_running()
        self.result.emit(running)


class InstallWorker(QThread):
    progress = Signal(str, int)      # text, percent
    finished = Signal(bool, str)     # success, path_or_error

    def __init__(self, installer_cls, target_dir, parent=None):
        super().__init__(parent)
        self.installer_cls = installer_cls
        self.target_dir = target_dir

    def run(self):
        def cb(text, percent):
            self.progress.emit(text, percent)

        success, res = self.installer_cls.install(self.target_dir, cb)
        self.finished.emit(success, res)


# =========================
# Screens
# =========================

class HostScreen(QWidget):
    """
    Host screen: control Sunshine, show IP & connect code, send PIN.
    # TODO: This screen is getting crowded. Consider splitting status and actions into tabs.
    """

    def __init__(self, parent, sunshine_api: SunshineAPI):
        super().__init__(parent)
        self.sunshine_api = sunshine_api
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Host (Sunshine)")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(title)

        # Status Card
        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)

        self.lbl_status = QLabel("Checking Sunshine status...")
        self.lbl_status.setFont(QFont("Segoe UI", 12))
        status_layout.addWidget(self.lbl_status)

        self.btn_status_action = QPushButton("...")
        self.btn_status_action.setFixedWidth(160)
        status_layout.addWidget(self.btn_status_action, alignment=Qt.AlignRight)

        layout.addWidget(status_card)

        # IP / Code Card
        ip_card = QFrame()
        ip_card.setObjectName("card")
        ip_layout = QVBoxLayout(ip_card)
        ip_layout.setContentsMargins(16, 16, 16, 16)
        ip_layout.setSpacing(12)

        self.lbl_ip = QLabel()
        self.lbl_ip.setFont(QFont("Segoe UI", 11))
        ip_layout.addWidget(self.lbl_ip)

        row_code = QHBoxLayout()
        self.edit_code = QLineEdit()
        self.edit_code.setReadOnly(True)
        row_code.addWidget(self.edit_code)

        btn_copy = QPushButton("Copy Code")
        btn_copy.clicked.connect(self.copy_code)
        row_code.addWidget(btn_copy)
        ip_layout.addLayout(row_code)

        layout.addWidget(ip_card)

        # PIN Card
        pin_card = QFrame()
        pin_card.setObjectName("card")
        pin_layout = QHBoxLayout(pin_card)
        pin_layout.setContentsMargins(16, 16, 16, 16)

        self.edit_pin = QLineEdit()
        self.edit_pin.setPlaceholderText("Enter PIN shown in Moonlight")
        pin_layout.addWidget(self.edit_pin)

        btn_send_pin = QPushButton("Send PIN")
        btn_send_pin.clicked.connect(self.on_send_pin)
        pin_layout.addWidget(btn_send_pin)

        layout.addWidget(pin_card)

        layout.addStretch()

        # Prepare IP + code
        ip = get_local_ip()
        self.lbl_ip.setText(f"LAN IP: <b>{ip}</b>")
        code = encode_connection_code(ip)
        self.edit_code.setText(code)

        # Default status
        self.update_status(False)

    def update_status(self, running: bool):
        # Safely disconnect any previous connections
        # FIXME: This disconnect logic is a bit brute-force. Need a cleaner signal management later.
        try:
            self.btn_status_action.clicked.disconnect()
        except RuntimeError:
            pass # No connection existed

        if running:
            self.lbl_status.setText("● Sunshine Web UI is reachable on https://localhost:47990")
            self.lbl_status.setStyleSheet("color: #2cc985;")
            self.btn_status_action.setText("Open Sunshine Web UI")
            self.btn_status_action.clicked.connect(self.open_web_ui)
        else:
            self.lbl_status.setText("● Sunshine not detected (service not running)")
            self.lbl_status.setStyleSheet("color: #ff6666;")
            self.btn_status_action.setText("Start Sunshine")
            self.btn_status_action.clicked.connect(self.start_sunshine)

    @Slot()
    def copy_code(self):
        QApplication.clipboard().setText(self.edit_code.text())
        QMessageBox.information(self, "Copied", "Connection code copied to clipboard.")

    @Slot()
    def open_web_ui(self):
        SunshineManager.open_web_ui()

    @Slot()
    def start_sunshine(self):
        ok, msg = SunshineManager.start_service()
        if not ok:
            QMessageBox.warning(self, "Failed to start Sunshine", msg)

    @Slot()
    def on_send_pin(self):
        pin = self.edit_pin.text().strip()
        if not pin:
            QMessageBox.warning(self, "PIN Required", "Enter the PIN shown in Moonlight.")
            return

        ok, msg = self.sunshine_api.send_pin(pin)
        if ok:
            QMessageBox.information(self, "PIN Sent", "PIN sent successfully.")
        else:
            QMessageBox.warning(self, "Error", msg)


class ClientScreen(QWidget):
    """
    Client screen: guide Moonlight usage and launch a stream.
    """

    def __init__(self, parent, moonlight_runner: MoonlightRunner, config: dict):
        super().__init__(parent)
        self.moonlight = moonlight_runner
        self.config = config
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Client (Moonlight)")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(title)

        if not self.moonlight.exe_path:
            warn = QLabel("Moonlight is not configured. Go to Settings to install or set the path.")
            warn.setStyleSheet("color: #ff6666;")
            layout.addWidget(warn)
            layout.addStretch()
            return

        # Pairing Card
        pair_card = QFrame()
        pair_card.setObjectName("card")
        pair_layout = QVBoxLayout(pair_card)
        pair_layout.setContentsMargins(16, 16, 16, 16)
        pair_layout.setSpacing(8)

        lbl_pair = QLabel("1. First-time pairing:")
        lbl_pair.setFont(QFont("Segoe UI", 12, QFont.Bold))
        pair_layout.addWidget(lbl_pair)

        lbl_pair_desc = QLabel(
            "• Click \"Open Moonlight\" and add this PC using the IP shown on the Host tab.\n"
            "• Sunshine may show a pairing request and PIN.\n"
            "• Enter the PIN in the Host screen."
        )
        lbl_pair_desc.setWordWrap(True)
        pair_layout.addWidget(lbl_pair_desc)

        btn_open_moon = QPushButton("Open Moonlight")
        btn_open_moon.clicked.connect(self.open_moonlight_gui)
        pair_layout.addWidget(btn_open_moon, alignment=Qt.AlignLeft)

        layout.addWidget(pair_card)

        # Connect Card
        conn_card = QFrame()
        conn_card.setObjectName("card")
        conn_layout = QVBoxLayout(conn_card)
        conn_layout.setContentsMargins(16, 16, 16, 16)
        conn_layout.setSpacing(12)

        lbl_conn = QLabel("2. Connect:")
        lbl_conn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        conn_layout.addWidget(lbl_conn)

        row_code = QHBoxLayout()
        self.edit_conn_code = QLineEdit()
        self.edit_conn_code.setPlaceholderText("Enter Host Code (or IP)")
        row_code.addWidget(self.edit_conn_code)
        conn_layout.addLayout(row_code)

        row_res = QHBoxLayout()
        lbl_res = QLabel("Resolution:")
        self.combo_res = QComboBox()
        self.combo_res.addItems(["1920x1080", "1280x720", "2560x1440"])
        row_res.addWidget(lbl_res)
        row_res.addWidget(self.combo_res, 1)
        conn_layout.addLayout(row_res)

        btn_start = QPushButton("Start Stream")
        btn_start.setObjectName("primaryButton")
        btn_start.clicked.connect(self.start_stream)
        conn_layout.addWidget(btn_start, alignment=Qt.AlignLeft)

        layout.addWidget(conn_card)
        layout.addStretch()

    @Slot()
    def open_moonlight_gui(self):
        ok, msg = self.moonlight.open_gui()
        if not ok:
            QMessageBox.warning(self, "Error", msg)

    @Slot()
    def start_stream(self):
        code = self.edit_conn_code.text().strip()
        if not code:
            QMessageBox.warning(self, "Code Required", "Enter the host code or IP.")
            return

        ip = decode_connection_code(code) or code

        res_text = self.combo_res.currentText()
        try:
            w_str, h_str = res_text.split("x")
            width, height = int(w_str), int(h_str)
        except Exception:
            width, height = 1920, 1080

        ok, msg = self.moonlight.launch(ip, width=width, height=height)
        if not ok:
            QMessageBox.warning(self, "Error", msg)


class SettingsScreen(QWidget):
    """
    Settings: configure Sunshine & Moonlight paths and run installers.
    """
    
    # Emit (username, password) when credentials are saved
    credentials_changed = Signal(str, str)

    def __init__(self, parent, config: dict, on_paths_changed):
        super().__init__(parent)
        self.config = config
        self.on_paths_changed = on_paths_changed

        self.sunshine_path = self.config.get("sunshine_path", "")
        self.moonlight_path = self.config.get("moonlight_path", "")
        
        self.init_user = self.config.get("sunshine_user", "")
        self.init_pass = self.config.get("sunshine_pass", "")

        self.install_overlay = None
        self.progress_label = None
        self.progress_bar = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        layout.addWidget(title)

        # Sunshine Card
        sun_card = QFrame()
        sun_card.setObjectName("card")
        sun_layout = QVBoxLayout(sun_card)
        sun_layout.setContentsMargins(16, 16, 16, 16)
        sun_layout.setSpacing(10)

        lbl_sun = QLabel("Sunshine (Host)")
        lbl_sun.setFont(QFont("Segoe UI", 14, QFont.Bold))
        sun_layout.addWidget(lbl_sun)

        self.lbl_sun_path = QLabel(self.sunshine_path or "Not configured")
        self.lbl_sun_path.setStyleSheet("color: #bbbbbb;")
        sun_layout.addWidget(self.lbl_sun_path)

        row_sun_btns = QHBoxLayout()
        btn_browse_sun = QPushButton("Browse .exe")
        btn_browse_sun.clicked.connect(self.browse_sunshine)
        row_sun_btns.addWidget(btn_browse_sun)

        btn_install_sun = QPushButton("Download & Install")
        btn_install_sun.clicked.connect(self.install_sunshine)
        row_sun_btns.addWidget(btn_install_sun)

        row_sun_btns.addStretch()
        sun_layout.addLayout(row_sun_btns)
        
        # Headless Setup Section within Sunshine Card
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #444444;")
        sun_layout.addWidget(line)
        
        lbl_creds = QLabel("Headless Setup (Create/Update Login)")
        lbl_creds.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_creds.setStyleSheet("color: #aaaaaa;")
        sun_layout.addWidget(lbl_creds)
        
        row_creds = QHBoxLayout()
        self.edit_user = QLineEdit(self.init_user)
        self.edit_user.setPlaceholderText("Username")
        row_creds.addWidget(self.edit_user)
        
        self.edit_pass = QLineEdit(self.init_pass)
        self.edit_pass.setPlaceholderText("Password")
        self.edit_pass.setEchoMode(QLineEdit.Password)
        row_creds.addWidget(self.edit_pass)
        
        btn_save_creds = QPushButton("Save & Initialize")
        btn_save_creds.clicked.connect(self.save_credentials)
        btn_save_creds.setStyleSheet("background-color: #2b8c2b; color: white;")
        row_creds.addWidget(btn_save_creds)
        
        sun_layout.addLayout(row_creds)
        lbl_hint = QLabel("Sets credentials via CLI so you don't need a browser.")
        lbl_hint.setStyleSheet("color: #888888; font-size: 10px;")
        sun_layout.addWidget(lbl_hint)

        layout.addWidget(sun_card)

        # Moonlight Card
        moon_card = QFrame()
        moon_card.setObjectName("card")
        moon_layout = QVBoxLayout(moon_card)
        moon_layout.setContentsMargins(16, 16, 16, 16)
        moon_layout.setSpacing(10)

        lbl_moon = QLabel("Moonlight (Client)")
        lbl_moon.setFont(QFont("Segoe UI", 14, QFont.Bold))
        moon_layout.addWidget(lbl_moon)

        self.lbl_moon_path = QLabel(self.moonlight_path or "Not configured")
        self.lbl_moon_path.setStyleSheet("color: #bbbbbb;")
        moon_layout.addWidget(self.lbl_moon_path)

        row_moon_btns = QHBoxLayout()
        btn_browse_moon = QPushButton("Browse .exe")
        btn_browse_moon.clicked.connect(self.browse_moonlight)
        row_moon_btns.addWidget(btn_browse_moon)

        btn_install_moon = QPushButton("Download & Install")
        btn_install_moon.clicked.connect(self.install_moonlight)
        row_moon_btns.addWidget(btn_install_moon)

        row_moon_btns.addStretch()
        moon_layout.addLayout(row_moon_btns)

        layout.addWidget(moon_card)
        layout.addStretch()

    # --- Path handling ---

    @Slot()
    def browse_sunshine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Sunshine Executable", "", "Executable (*.exe)")
        if path:
            self.sunshine_path = path
            self.config["sunshine_path"] = path
            save_config(self.config)
            self.lbl_sun_path.setText(path)
            self.on_paths_changed()

    @Slot()
    def browse_moonlight(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Moonlight Executable", "", "Executable (*.exe)")
        if path:
            self.moonlight_path = path
            self.config["moonlight_path"] = path
            save_config(self.config)
            self.lbl_moon_path.setText(path)
            self.on_paths_changed()
            
    # --- Credentials ---
    
    @Slot()
    def save_credentials(self):
        user = self.edit_user.text().strip()
        pwd = self.edit_pass.text().strip()
        
        if not user or not pwd:
            QMessageBox.warning(self, "Missing Data", "Please enter both username and password.")
            return

        # Save to config
        self.config["sunshine_user"] = user
        self.config["sunshine_pass"] = pwd
        save_config(self.config)
        
        # Initialize via CLI
        ok, msg = SunshineManager.initialize_credentials(user, pwd)
        if ok:
             QMessageBox.information(self, "Success", "Credentials initialized!\nYou can now pair directly.")
             # Notify main window to update API auth
             self.credentials_changed.emit(user, pwd)
             
             # Auto-start if not running
             if not SunshineManager.is_running():
                 SunshineManager.start_service()
        else:
             QMessageBox.critical(self, "Initialization Failed", msg)

    # --- Installers ---

    def _show_install_overlay(self, title_text: str):
        if self.install_overlay is not None:
            self.install_overlay.deleteLater()

        self.install_overlay = QFrame(self)
        self.install_overlay.setStyleSheet("background-color: rgba(0,0,0,180);")
        self.install_overlay.setFrameShape(QFrame.NoFrame)
        self.install_overlay.setGeometry(self.rect())
        self.install_overlay.raise_()

        vbox = QVBoxLayout(self.install_overlay)
        vbox.setAlignment(Qt.AlignCenter)

        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: white;")
        vbox.addWidget(title, alignment=Qt.AlignHCenter)

        self.progress_label = QLabel("Starting...")
        self.progress_label.setStyleSheet("color: white;")
        vbox.addWidget(self.progress_label, alignment=Qt.AlignHCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        vbox.addWidget(self.progress_bar)

        self.install_overlay.show()

    def _hide_install_overlay(self):
        if self.install_overlay is not None:
            self.install_overlay.hide()
            self.install_overlay.deleteLater()
            self.install_overlay = None
            self.progress_label = None
            self.progress_bar = None

    @Slot()
    def install_sunshine(self):
        target_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Install Sunshine")
        if not target_dir:
            return

        self._show_install_overlay("Installing Sunshine...")
        self.worker = InstallWorker(SunshineInstaller, target_dir)
        self.worker.progress.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_sunshine_installed)
        self.worker.start()

    @Slot()
    def install_moonlight(self):
        target_dir = QFileDialog.getExistingDirectory(self, "Select Folder to Install Moonlight")
        if not target_dir:
            return

        self._show_install_overlay("Installing Moonlight...")
        self.worker = InstallWorker(MoonlightInstaller, target_dir)
        self.worker.progress.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_moonlight_installed)
        self.worker.start()

    @Slot(str, int)
    def _on_install_progress(self, text, percent):
        if self.progress_label:
            self.progress_label.setText(text)
        if self.progress_bar:
            self.progress_bar.setValue(percent)

    @Slot(bool, str)
    def _on_sunshine_installed(self, success, res):
        self._hide_install_overlay()
        if success:
            self.sunshine_path = res
            self.config["sunshine_path"] = res
            save_config(self.config)
            self.lbl_sun_path.setText(res)
            self.on_paths_changed()
            QMessageBox.information(self, "Sunshine Installed", "Sunshine was installed successfully.")
        else:
            QMessageBox.warning(self, "Install Failed", res)

    @Slot(bool, str)
    def _on_moonlight_installed(self, success, res):
        self._hide_install_overlay()
        if success:
            self.moonlight_path = res
            self.config["moonlight_path"] = res
            save_config(self.config)
            self.lbl_moon_path.setText(res)
            self.on_paths_changed()
            QMessageBox.information(self, "Moonlight Installed", "Moonlight was installed successfully.")
        else:
            QMessageBox.warning(self, "Install Failed", res)


# =========================
# Main Window
# =========================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("GameBeam")
        self.resize(1000, 650)

        self.config = load_config()

        # Backend objects
        self.sunshine_user = self.config.get("sunshine_user", "")
        self.sunshine_pass = self.config.get("sunshine_pass", "")
        self.sunshine_api = SunshineAPI(self.sunshine_user, self.sunshine_pass)

        self.moonlight_runner = MoonlightRunner(self.config.get("moonlight_path", None))

        # If we have custom Sunshine path in config, share with manager
        sun_cfg_path = self.config.get("sunshine_path", "")
        if sun_cfg_path:
            SunshineManager.set_custom_path(sun_cfg_path)

        self._init_palette()
        self._build_layout()
        self._start_status_timer()

    def _init_palette(self):
        """
        Apply a Mica-like dark palette on Windows 11,
        and a simple dark flat palette elsewhere.
        """
        pal = self.palette()

        is_win = platform.system() == "Windows"
        # HACK: Very rough Windows 11 check – not perfect but good enough for now.
        is_win11 = is_win and (platform.release() == "10" or platform.release() == "11")
        is_win11 = is_win and (platform.release() == "10" or platform.release() == "11")

        if is_win11:
            # Mica-like dark palette (not true OS-level Mica, but similar look)
            bg = QColor(18, 18, 22, 230)
            card_bg = QColor(32, 32, 38, 245)
        else:
            bg = QColor(18, 18, 18)
            card_bg = QColor(32, 32, 32)

        pal.setColor(QPalette.Window, bg)
        pal.setColor(QPalette.Base, card_bg)
        pal.setColor(QPalette.AlternateBase, card_bg.darker(105))
        pal.setColor(QPalette.WindowText, Qt.white)
        pal.setColor(QPalette.Text, Qt.white)
        pal.setColor(QPalette.Button, card_bg)
        pal.setColor(QPalette.ButtonText, Qt.white)
        pal.setColor(QPalette.Highlight, QColor(50, 120, 220))
        pal.setColor(QPalette.HighlightedText, Qt.white)

        self.setPalette(pal)
        self.setAutoFillBackground(True)

        self.setAutoFillBackground(True)

        # Global stylesheet for modern look
        # TODO: Move this to an external .qss file so designers can tweak it without touching py code.
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121218;
            }
            QFrame#card {
                background-color: rgba(32, 32, 40, 230);
                border-radius: 12px;
            }
            QPushButton {
                background-color: #2d2d35;
                color: white;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #3b3b45;
            }
            QPushButton#primaryButton {
                background-color: #1f6feb;
            }
            QPushButton#primaryButton:hover {
                background-color: #205fd0;
            }
            QLineEdit, QComboBox {
                background-color: #1c1c22;
                color: white;
                border-radius: 6px;
                padding: 4px 8px;
                border: 1px solid #333333;
            }
        """)

    def _build_layout(self):
        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        title = QLabel("GameBeam")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        sidebar_layout.addWidget(title)
        subtitle = QLabel("Sunshine + Moonlight")
        subtitle.setStyleSheet("color: #aaaaaa;")
        sidebar_layout.addWidget(subtitle)

        sidebar_layout.addSpacing(16)

        self.btn_host = QPushButton("Host (Server)")
        self.btn_client = QPushButton("Client (Player)")
        self.btn_settings = QPushButton("Settings")

        for btn in (self.btn_host, self.btn_client, self.btn_settings):
            btn.setCheckable(True)
            btn.setMinimumHeight(32)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Central stack
        self.stack = QStackedWidget()

        self.host_screen = HostScreen(self, self.sunshine_api)
        self.client_screen = ClientScreen(self, self.moonlight_runner, self.config)
        self.settings_screen = SettingsScreen(self, self.config, self.on_paths_changed)
        
        # Connect credential signal
        self.settings_screen.credentials_changed.connect(self.on_credentials_changed)

        self.stack.addWidget(self.host_screen)      # index 0
        self.stack.addWidget(self.client_screen)    # index 1
        self.stack.addWidget(self.settings_screen)  # index 2

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

        # Connect nav
        self.btn_host.clicked.connect(lambda: self._set_page(0))
        self.btn_client.clicked.connect(lambda: self._set_page(1))
        self.btn_settings.clicked.connect(lambda: self._set_page(2))

        self._set_page(0)

    def _set_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate((self.btn_host, self.btn_client, self.btn_settings)):
            btn.setChecked(i == idx)
            if i == idx:
                btn.setStyleSheet("background-color: #1f6feb; color: white; border-radius: 8px;")
            else:
                btn.setStyleSheet("")
    
    @Slot(str, str)
    def on_credentials_changed(self, user, pwd):
        logger.info("Credentials updated, reloading SunshineAPI auth.")
        self.sunshine_api.update_auth(user, pwd)

    def _start_status_timer(self):
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(3000)  # 3 seconds
        self.status_timer.timeout.connect(self._refresh_sunshine_status)
        self.status_timer.start()
        self._refresh_sunshine_status()

    def _refresh_sunshine_status(self):
        # Prevent starting a new thread if one is already running
        if hasattr(self, 'status_worker') and self.status_worker.isRunning():
            return

        self.status_worker = SunshineStatusWorker(self) # Parent it to self
        self.status_worker.result.connect(self.host_screen.update_status)
        self.status_worker.start()

    def on_paths_changed(self):
        """
        Called when Settings updates exe paths.
        Refresh backend objects accordingly.
        """
        sun_path = self.config.get("sunshine_path", "")
        if sun_path:
            SunshineManager.set_custom_path(sun_path)

        self.moonlight_runner = MoonlightRunner(self.config.get("moonlight_path", None))
        # Rebuild client screen with new runner
        idx = self.stack.indexOf(self.client_screen)
        if idx != -1:
            self.stack.removeWidget(self.client_screen)
            self.client_screen.deleteLater()
        self.client_screen = ClientScreen(self, self.moonlight_runner, self.config)
        self.stack.insertWidget(1, self.client_screen)
