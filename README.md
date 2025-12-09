# GameBeam

**GameBeam** (formerly Game Stream Pro) is a unified launcher and management tool for local game streaming. It integrates **Sunshine** (Host) and **Moonlight** (Client) into a single, user-friendly interface, making it easier than ever to set up your own high-performance remote gaming experience.

## Purpose

The primary goal of GameBeam is to simplify the process of setting up a local game stream. Instead of managing separate installations and command-line configurations, GameBeam provides:

- **Automated Installation**: Downloads and installs portable versions of Sunshine and Moonlight automatically.
- **Unified Dashboard**: Manage both the Host (Sunshine) and Client (Moonlight) from one app.
- **Easy Pairing**: Helper tools to manage PINs and connection codes without juggling browser windows excessively.
- **Headless Configuration**: Initialize Sunshine credentials directly from the app.

## Features

- **Host Mode**: 
    - Checks Sunshine status.
    - Displays your LAN IP and a sharable Connection Code.
    - Quick access to the Sunshine Web UI.
    - PIN entry for pairing with new clients.
- **Client Mode**:
    - Launches Moonlight with specific resolution and settings.
    - Connects to hosts using IP or GameBeam connection codes.
- **Settings**:
    - Configure custom paths for Sunshine/Moonlight executables.
    - One-click download & install for dependencies.
    - Credential management for Sunshine.

## Getting Started

### Prerequisites

- Windows 10 or 11 (64-bit recommended)
- Python 3.10+ (if running from source)
- Internet connection (for initial download of Sunshine/Moonlight)

### Installation (Source)

1. Clone the repository:
   ```bash
   git clone https://github.com/xalaetrx/gamebeam.git
   cd gamebeam
   ```

2. Install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Primarily requires `PySide6`)*

3. Run the application:
   ```bash
   python main.py
   ```

## Usage

1. **Launch GameBeam**.
2. **Go to Settings**:
   - If you don't have Sunshine or Moonlight installed, use the "Download & Install" buttons.
   - Set your Sunshine credentials if this is a fresh install.
3. **Host Setup**:
   - Navigate to the **Host** tab.
   - Start Sunshine if it's not running.
   - Note your IP or copy the "Connection Code".
4. **Client Setup (on another PC)**:
   - Navigate to the **Client** tab.
   - Enter the Host's IP or Code.
   - Click "Start Stream".
   - If pairing is required, follow the PIN instructions on the Host tab.

## License

This project relies on [Sunshine](https://github.com/LizardByte/Sunshine) and [Moonlight](https://moonlight-stream.org/), which are open-source projects. GameBeam itself is provided under the MIT License.
