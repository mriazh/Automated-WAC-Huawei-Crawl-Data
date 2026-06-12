# Automated WAC Huawei Crawl Data

GUI tool to collect LLDP neighbor data from Access Points (APs) managed by a Huawei WLAN Access Controller (WAC) via SSH.

## What does this tool do?

1. Connects to the WAC via SSH (with login verification)
2. Connects to each AP via `stelnet ap ap-id {ID}`
3. Runs `display lldp neighbor brief` on each AP
4. Extracts all LLDP neighbor entries including Local Intf, Neighbor Dev, and Neighbor Intf
5. Maps each neighbor device name to its IP address from the switch list
6. Outputs results to a CSV file

## Output

CSV file (`lldp_result.csv`) with the following format:

```csv
"AP","Local Intf","Switch","Neighbor Intf"
"AP-BLDG-A-L1-IN01 (192.0.2.10)","GE0/0/0","SW-BLDG-A-L2 (198.51.100.10)","85"
"AP-BLDG-B-L1-IN22 (192.0.2.11)","GE0/0/0","AP-BLDG-B-L1-IN07 (N/A)","GE0/0/0"
"AP-BLDG-B-L1-IN22 (192.0.2.11)","GE0/0/0","SW-BLDG-B-L1 (198.51.100.20)","GE0/0/0"
```

> APs with multiple LLDP neighbors will have multiple rows in the CSV (one per neighbor).

---

## Installation

Choose one of the two options below:

### Option A: Download EXE (no Python needed)

1. Go to [Releases](https://github.com/mriazh/Automated-WAC-Huawei-Crawl-Data/releases)
2. Download `WAC-Crawl.zip` from the latest release
3. Extract the ZIP to any folder
4. Inside you'll find:
   - `WAC-Crawl.exe` — the application
   - `list_ap.txt` — AP list template (edit this)
   - `list_switch.txt` — switch list template (edit this)

### Option B: Run from Python source

1. Install [Python 3.10+](https://www.python.org/downloads/)
2. Clone or download this repository:
   ```bash
   git clone https://github.com/mriazh/Automated-WAC-Huawei-Crawl-Data.git
   cd Automated-WAC-Huawei-Crawl-Data
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run:
   ```bash
   python main.py
   ```

---

## Setup — Edit Input Files (REQUIRED)

Before using the tool, you **must** edit the input files with your own data.

### Step 1: Edit `list_ap.txt`

This file contains your AP data. Format is **tab-separated**, one AP per line:

```
AP-Name<TAB>IP-Address<TAB>ID
```

Example:
```
AP-BUILDING1-L1-IN01	10.0.1.10	0
AP-BUILDING2-L1-OUT01	10.0.1.11	1
AP-OFFLINE-01	--	2
```

> - Use `--` as IP for offline/unreachable APs (they will be skipped)
> - The ID is the AP ID in the WAC (used for `stelnet ap ap-id {ID}`)
> - You can get this data from WAC command: `display ap all`

### Step 2: Edit `list_switch.txt`

This file maps switch names to their IP addresses. Format is **tab-separated**:

```
Switch-Name<TAB>IP-Address
```

Example:
```
SW-BLDG-A-L2	198.51.100.10
SW-BLDG-B-L1	198.51.100.20
ASW01-CORE	198.51.100.1
```

> This is used to resolve neighbor device names to IP addresses in the output CSV.
> If a neighbor name is not in this list, it will show as `N/A` for the IP.

---

## Usage

### 1. Login

1. Open the application (`WAC-Crawl.exe` or `python main.py`)
2. Enter your WAC SSH credentials:
   - **Host** — WAC IP address (e.g., `192.0.2.10`)
   - **Port** — SSH port (default `22`)
   - **Username** — SSH username
   - **Password** — SSH password
3. Click **Connect** (or press Enter)
4. The tool verifies the SSH connection before proceeding
5. Check **Remember me** to auto-login next time you open the app

### 2. Select Files

1. Click **Browse** next to "AP List" → select your `list_ap.txt`
2. Click **Browse** next to "Switch List" → select your `list_switch.txt`
3. Click **Browse** next to "Output Dir" → select where to save the CSV
4. (Optional) Click **Check** to validate file format and see AP/switch count

### 3. Crawl

1. Click **Start** to begin crawling
2. Watch the live log for progress (color-coded: green = success, red = failed, yellow = skipped)
3. Click **Stop** to pause — progress is saved automatically
4. Click **Start** again to resume from where you left off

### 4. Results

- Output CSV is saved to your selected output directory as `lldp_result.csv`
- Summary shows multi-neighbor (double) APs at the end of each crawl
- Detailed log is saved to `crawl.log` in the application folder

---

## Features

| Feature | Description |
|---------|-------------|
| PySide6 GUI | Dark/light theme toggle, no console needed |
| SSH verification | Smart error messages for host/port vs credentials |
| Remember me | Encrypted credential storage with auto-login |
| Autocomplete | Host and username suggestions from history |
| File validation | Check button shows AP/switch count and format errors |
| Multi-neighbor | Collects ALL LLDP neighbors per AP, including local and neighbor interfaces |
| Auto-reconnect | If SSH drops mid-crawl, reconnects and continues |
| Resume mode | Skips already-crawled APs on re-run |
| Graceful shutdown | Saves partial results on Stop, close, or Ctrl+C |
| Detailed logging | Full debug log in `crawl.log` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Host/port not reachable` | Check VPN is active and WAC IP/port is correct |
| `Invalid username or password` | Host is reachable — check credentials |
| `Not an SSH server` | Port is open but not SSH — check port number |
| `Not a WAC device` | SSH login OK but device is not a WAC |
| AP shows `FAILED: Timeout` | AP may be behind NAT — takes longer to connect |
| AP shows `Login failed` | AP is offline or unreachable from WAC |

---

## Prerequisites

- **SSH access** to the Huawei WAC (IP, port, username, password)
- **VPN connection** (if the WAC is on an internal network)
- **Python 3.10+** (only if running from source)

---

## Updates

- App checks GitHub Releases for updates on startup.
- Manual check is available from Help → Check for Updates.
- Updates download the Windows installer from GitHub Releases.
- The app closes and launches the installer; the installer performs the update.
- No Python or Git is required for users.

---

## Build Executable (for developers)

```bash
pip install pyinstaller
pyinstaller build/build.spec --distpath dist --workpath build/temp
```

Output: `dist/WAC-Crawl/WAC-Crawl.exe`

---

## Project Structure

```
├── main.py              # GUI entry point
├── config.py            # Load & validate config
├── parsers.py           # Parse AP list, switch list, LLDP output
├── ssh_client.py        # SSH connection & interactive shell
├── crawler.py           # Crawl orchestration per-AP
├── output.py            # CSV writer & summary
├── gui/
│   ├── main_window.py   # Main window with page navigation
│   ├── login_page.py    # SSH login form with verification
│   ├── crawl_page.py    # Crawl controls, progress, live log
│   ├── workers.py       # Background threads (crawl, connect)
│   ├── themes.py        # Dark/light QSS stylesheets + toggle
│   ├── config_store.py  # JSON config persistence (%APPDATA%)
│   ├── encryption.py    # Fernet encryption for stored passwords
│   ├── validators.py    # Input field validation
│   └── icons.py         # SVG icon helpers
├── assets/
│   └── huawei.svg       # App icon
├── build/
│   ├── build.spec       # PyInstaller spec
│   └── installer.iss    # Inno Setup installer script
├── tests/               # Unit & property-based tests
├── list_ap-example.txt  # AP list template
├── list_switch-example.txt  # Switch list template
└── requirements.txt     # Python dependencies
```

---

## Security

- Credentials encrypted with Fernet (stored in `%APPDATA%/WAC-Crawl/`)
- Input files (`list_ap.txt`, `list_switch.txt`) contain internal IPs — keep them private
- The tool only runs **read-only** commands (`display`) — no configuration is modified
- SSH host keys are auto-accepted (standard for internal network automation)

## License

MIT
