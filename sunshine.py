# // FILE: sunshine.py
import os
import requests
import zipfile
import threading
import subprocess
import socket
import webbrowser
import urllib3
import logging

logger = logging.getLogger(__name__)

# NOTE: Sunshine uses self-signed certs by default, so we have to suppress these warnings or the logs get spammed.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================
# Sunshine API Wrapper
# NOTE: This only covers the bare minimum we need (pin, auth). Full API is huge.
# =========================

class SunshineAPI:
    BASE_URL = "https://localhost:47990/api"

    def __init__(self, username: str | None = None, password: str | None = None):
        self.auth = (username, password) if username and password else None

    def update_auth(self, username: str, password: str) -> None:
        """Update stored HTTP Basic Auth credentials."""
        self.auth = (username, password)

    def send_pin(self, pin: str) -> tuple[bool, str]:
        """
        Sends the pairing PIN (displayed on Moonlight Client) to the Sunshine Host.

        Returns:
            (success: bool, message: str)
        """
        url = f"{self.BASE_URL}/pin"
        payload = {"pin": str(pin)}

        try:
            resp = requests.post(
                url,
                json=payload,
                auth=self.auth,
                verify=False,  # NOTE: skipping verification because of self-signed certs
                timeout=5,
            )

            if resp.status_code == 200:
                logger.info(f"PIN {pin} sent successfully.")
                return True, "PIN accepted by Sunshine."
            elif resp.status_code == 401:
                # REVIEW: Should we handle the 401 distinctively or just lump it in? Authentication failure implies bad creds.
                logger.warning("PIN send failed: authentication error.")
                return False, "Authentication Failed (check Sunshine username/password)."
            else:
                logger.error(f"PIN send failed: {resp.status_code} {resp.text}")
                return False, f"Error {resp.status_code}: {resp.text}"

        except requests.exceptions.ConnectionError:
            logger.error("Sunshine is not reachable on https://localhost:47990.")
            return False, "Sunshine is not running or not reachable."
        except Exception as e:
            logger.error(f"PIN send error: {e}")
            return False, str(e)


# =========================
# Sunshine Installer
# =========================

class SunshineInstaller:
    """
    Downloads and extracts the latest portable Sunshine release from GitHub.
    """
    GITHUB_API_URL = "https://api.github.com/repos/LizardByte/Sunshine/releases/latest"
    
    @staticmethod
    def install(target_dir, progress_callback=None):
        """
        Downloads and installs Sunshine to the specified directory.
        """
        try:
            if progress_callback: progress_callback("Checking latest release...", 10)
            
            # 1. Get Release Info
            resp = requests.get(SunshineInstaller.GITHUB_API_URL, timeout=10)
            if resp.status_code != 200:
                raise Exception(f"GitHub API Failed: {resp.status_code}")
            
            data = resp.json()
            assets = data.get("assets", [])
            download_url = None
            for asset in assets:
                name = asset["name"].lower()
                if "windows" in name and "portable" in name and name.endswith(".zip"):
                    download_url = asset["browser_download_url"]
                    break
            
            if not download_url:
                # Fallback: sometimes they name it differently, so we broaden the search
                for asset in assets:
                     name = asset["name"].lower()
                     if "windows" in name and name.endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break
            
            if not download_url:
                raise Exception("No suitable Windows release found on GitHub.")

            # 2. Download
            if progress_callback: progress_callback("Downloading...", 30)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            local_zip = os.path.join(target_dir, "sunshine.zip")
            
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                total_length = r.headers.get('content-length')
                dl = 0
                with open(local_zip, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        if chunk: 
                            dl += len(chunk)
                            f.write(chunk)
                            if total_length and progress_callback:
                                percent = 30 + int((dl / int(total_length)) * 40) # 30 to 70
                                progress_callback("Downloading...", percent)

            # 3. Extract
            if progress_callback: progress_callback("Extracting...", 80)
            
            with zipfile.ZipFile(local_zip, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            
            try:
                os.remove(local_zip)
            except: pass
            
            # Find the exe
            exe_path = None
            for root, dirs, files in os.walk(target_dir):
                if "sunshine.exe" in files:
                    exe_path = os.path.join(root, "sunshine.exe")
                    break
            
            if progress_callback: progress_callback("Done!", 100)
            return True, exe_path

        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False, str(e)

    @staticmethod
    def start_install_thread(target_dir, callback, on_complete):
        def _run():
            success, res = SunshineInstaller.install(target_dir, callback)
            if success:
                on_complete(True, res) # res is exe_path
            else:
                on_complete(False, res) # res is error msg
        threading.Thread(target=_run, daemon=True).start()


# =========================
# Sunshine Manager
# =========================

class SunshineManager:
    """
    Manages interaction with the Sunshine Host service.

    - Finds sunshine.exe (either from user-configured path or common system locations)
    - Can start Sunshine as a background process
    - Can initialize Sunshine's admin credentials via the '--creds' CLI flag
    - Can check whether the Sunshine web/API endpoint is reachable
    """
    DEFAULT_WEB_UI = "https://localhost:47990"

    # System paths fallback
    SYSTEM_PATHS = [
        r"C:\Program Files\Sunshine\sunshine.exe",
        r"C:\Program Files (x86)\Sunshine\sunshine.exe",
        r"C:\Sunshine\sunshine.exe",
    ]

    _custom_path: str | None = None

    @staticmethod
    def set_custom_path(path: str) -> None:
        """Sets a user-defined path for the Sunshine executable."""
        if path and os.path.exists(path):
            logger.info(f"Using custom Sunshine path: {path}")
            SunshineManager._custom_path = path
        else:
            logger.warning(f"Custom Sunshine path does not exist: {path}")

    @staticmethod
    def _find_executable() -> str | None:
        """Return the best guess for sunshine.exe, or None if not found."""
        # 1. Custom Path
        if SunshineManager._custom_path and os.path.exists(SunshineManager._custom_path):
            return SunshineManager._custom_path

        # 2. System Install
        for path in SunshineManager.SYSTEM_PATHS:
            if os.path.exists(path):
                logger.info(f"Found Sunshine at: {path}")
                return path

        logger.warning("Sunshine executable not found in known locations.")
        return None

    @staticmethod
    def is_running(host: str = "localhost", port: int = 47990) -> bool:
        """
        Checks if Sunshine's web/API endpoint is reachable.
        """
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    @staticmethod
    def open_web_ui() -> None:
        """
        Optional: Opens the Sunshine web UI in the default browser.
        This is not required for normal use if credentials are set via '--creds'.
        """
        try:
            webbrowser.open(SunshineManager.DEFAULT_WEB_UI)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    @staticmethod
    def initialize_credentials(username: str, password: str) -> tuple[bool, str]:
        """
        Configure Sunshine's admin credentials using the '--creds' CLI flag.
        This replaces the initial "set password in browser" onboarding.

        Must be called BEFORE starting Sunshine normally.

        Returns:
            (success: bool, message: str)
        """
        exe = SunshineManager._find_executable()
        if not exe:
            return False, "Sunshine.exe not found. Configure its path in Settings."

        if not username or not password:
            return False, "Username and password are required."

        try:
            cmd = [exe, "--creds", username, password]
            # Don't log the password
            safe_cmd_repr = " ".join([exe, "--creds", username, "********"])
            logger.info(f"Initializing Sunshine credentials via: {safe_cmd_repr}")

            proc = subprocess.run(
                cmd,
                cwd=os.path.dirname(exe),
                capture_output=True,
                text=True,
                shell=False,
            )

            if proc.returncode != 0:
                logger.error(
                    f"Sunshine --creds failed (code {proc.returncode}): {proc.stderr}"
                )
                msg = proc.stderr.strip() or "Failed to set credentials."
                return False, msg

            logger.info("Sunshine credentials initialized successfully.")
            return True, "Credentials initialized."
        except Exception as e:
            logger.error(f"Error running Sunshine --creds: {e}")
            return False, str(e)

    @staticmethod
    def start_service(explicit_path: str | None = None) -> tuple[bool, str]:
        """
        Attempts to find and start the Sunshine executable in the background.

        Returns:
            (success: bool, message: str)
        """
        path = explicit_path or SunshineManager._find_executable()

        if not path:
            logger.error("Cannot start Sunshine: executable not found.")
            return False, "Sunshine.exe not found."

        try:
            logger.info(f"Starting Sunshine: {path}")
            subprocess.Popen(
                [path],
                cwd=os.path.dirname(path),
                shell=True,  # fine on Windows, starts detached
            )
            return True, "Service Started"
        except Exception as e:
            logger.error(f"Failed to start Sunshine: {e}")
            return False, str(e)
