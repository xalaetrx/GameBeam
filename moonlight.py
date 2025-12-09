# // FILE: moonlight.py
import os
import requests
import zipfile
import threading
import subprocess
import logging

logger = logging.getLogger(__name__)

# NOTE: Handling the client-side installer logic here. 
# Ideally we'd package this, but downloading on the fly keeps the initial footprint small.

class MoonlightInstaller:
    """
    # TODO: Add checksum verification if we get serious about security.
    Downloads and extracts the latest portable Moonlight QT release from GitHub.
    """
    GITHUB_API_URL = "https://api.github.com/repos/moonlight-stream/moonlight-qt/releases/latest"
    
    @staticmethod
    def install(target_dir, progress_callback=None):
        try:
            if progress_callback: progress_callback("Checking Moonlight release...", 10)
            
            resp = requests.get(MoonlightInstaller.GITHUB_API_URL, timeout=10)
            if resp.status_code != 200:
                raise Exception(f"GitHub API Failed: {resp.status_code}")
            
            data = resp.json()
            assets = data.get("assets", [])
            download_url = None
            
            # FIXME: This search loop is fragile. If they change the portable zip naming scheme, we are cooked.
            for asset in assets:
                name = asset["name"].lower()
                if "portable" in name and "x64" in name and name.endswith(".zip"):
                    download_url = asset["browser_download_url"]
                    break
            
            if not download_url:
                 # Fallback to just finding any zip if the specific x64 portable naming fails
                for asset in assets:
                     name = asset["name"].lower()
                     if "portable" in name and name.endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break
            
            if not download_url:
                raise Exception("No suitable Portable release found.")

            if progress_callback: progress_callback("Downloading...", 30)
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
                
            local_zip = os.path.join(target_dir, "moonlight.zip")
            
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
                                percent = 30 + int((dl / int(total_length)) * 40)
                                progress_callback("Downloading...", percent)

            if progress_callback: progress_callback("Extracting...", 80)
            
            with zipfile.ZipFile(local_zip, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            
            try:
                os.remove(local_zip)
            except: pass
            
            # TODO: Improve this. Walking the whole dir is slow if the zip is huge (it shouldn't be).
            exe_path = None
            for root, dirs, files in os.walk(target_dir):
                if "Moonlight.exe" in files:
                    exe_path = os.path.join(root, "Moonlight.exe")
                    break
            
            if progress_callback: progress_callback("Done!", 100)
            return True, exe_path

        except Exception as e:
            logger.error(f"Moonlight Install failed: {e}")
            return False, str(e)

    @staticmethod
    def start_install_thread(target_dir, callback, on_complete):
        def _run():
            success, res = MoonlightInstaller.install(target_dir, callback)
            if success:
                on_complete(True, res)
            else:
                on_complete(False, res)
        threading.Thread(target=_run, daemon=True).start()


# =========================
# Moonlight Runner
# =========================

class MoonlightRunner:
    DEFAULT_PATHS = [
        r"C:\Program Files\Moonlight Game Streaming\Moonlight.exe",
        r"C:\Program Files (x86)\Moonlight Game Streaming\Moonlight.exe",
        os.path.expanduser(r"~\AppData\Local\Moonlight Game Streaming\Moonlight.exe")
    ]

    def __init__(self, exe_path=None):
        self.exe_path = exe_path or self._find_moonlight()
    
    def _find_moonlight(self):
        # NOTE: Just checking the usual suspects. Users can override this in settings.
        for path in self.DEFAULT_PATHS:
            if os.path.exists(path):
                logger.info(f"Found Moonlight at: {path}")
                return path
        return None

    def launch(self, host_ip, width=1920, height=1080, fps=60, bitrate=20000, vsync=True, app_name="Desktop"):
        if not self.exe_path or not os.path.exists(self.exe_path):
            logger.error("Moonlight executable not found.")
            return False, "Moonlight.exe not found. Please set path."

        # Moonlight Qt CLI format: stream [options] [host] [app]
        cmd = [
            self.exe_path,
            "stream",
            host_ip,
            app_name,
            "--resolution", f"{width}x{height}",
            "--fps", str(fps),
            "--bitrate", str(bitrate),
            "--quit-after" 
        ]
        
        if vsync:
            cmd.append("--vsync")
        else:
            cmd.append("--no-vsync")

        logger.info(f"Launching Moonlight: {' '.join(cmd)}")
        
        try:
            # Fire and forget. We don't need to hold the handle.
            subprocess.Popen(cmd)
            return True, "Moonlight Launched"
        except Exception as e:
            logger.error(f"Failed to launch Moonlight: {e}")
            return False, str(e)

    def open_gui(self):
        """Launches Moonlight GUI for pairing."""
        if not self.exe_path or not os.path.exists(self.exe_path):
             return False, "Moonlight.exe not found."
        
        try:
            logger.info("Opening Moonlight GUI...")
            subprocess.Popen([self.exe_path])
            return True, "Moonlight GUI Opened"
        except Exception as e:
            return False, str(e)
