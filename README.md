# Automated WAC Huawei Crawl Data

GUI tool to collect LLDP neighbor data from Access Points (APs) managed by a Huawei WLAN Access Controller (WAC) via SSH.

## What does this tool do?

1. Connects to the WAC via SSH (with login verification)
2. Connects to each AP via `stelnet ap ap-id {ID}`
3. Runs `display lldp neighbor brief` on each AP
4. Extracts **all** "Neighbor Dev" entries (the devices connected to the AP)
5. Maps each neighbor device name to its IP address from the switch list
6. Outputs results to a CSV file

## Screenshots

### Login Page
- SSH connection verification (host, port, username, password)
- Remember me with encrypted credential storage
- Autocomplete suggestions for host and username
- Smart error messages (host/port vs credentials)

### Crawl Page
- File input with Browse + Check validation
- Start/Stop with resume support
- Live log with color-coded entries
- Progress bar with current/total count

## Output

CSV file (`lldp_result.csv`) with the following format:

```csv
"AP","Switch"
"AP-BLDG-A-L1-IN01 (192.0.2.10)","SW-BLDG-A-L2 (198.51.100.10)"
"AP-BLDG-B-L1-IN22 (192.0.2.11)","AP-BLDG-B-L1-IN07 (N/A)"
"AP-BLDG-B-L1-IN22 (192.0.2.11)","SW-BLDG-B-L1 (198.51.100.20)"
```

> APs with multiple LLDP neighbors will have multiple rows in the CSV (one per neighbor).

## Prerequisites

- **Python 3.10 or higher** — [Download here](https://www.python.org/downloads/)
- **SSH access** to the Huawei WAC (IP, port, username, password)
- **VPN connection** (if the WAC is on an internal network)

## Installation

### Step 1: Download the project

```bash
git clone https://github.com/mriazh/Automated-WAC-Huawei-Crawl-Data.git
cd Automated-WAC-Huawei-Crawl-Data
```

Or download as ZIP from GitHub and extract it.

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Prepare input files

You need 2 input files (select them in the GUI via Browse):

#### AP List (`list_ap.txt`)

Tab-separated, one AP per line:

```
AP-Name<TAB>IP-Address<TAB>ID
```

Example:
```
AP-BUILDING1-L1-IN01	10.0.1.10	0
AP-BUILDING2-L1-OUT01	10.0.1.11	1
AP-OFFLINE-01	--	2
```

> Use `--` as IP for offline/unreachable APs (they will be skipped).

#### Switch List (`list_switch.txt`)

Tab-separated:

```
Switch-Name<TAB>IP-Address
```

Example:
```
SW-BLDG-A-L2	198.51.100.10
SW-BLDG-B-L1	198.51.100.20
```

> Used to map neighbor device names to their IP addresses in the output.

## Usage

### Run the GUI

```bash
python main.py
```

### Login

1. Enter WAC host, port (default 22), username, and password
2. Click **Connect** (or press Enter)
3. The tool verifies SSH connection before proceeding
4. Check **Remember me** to auto-login next time

### Crawl

1. Select AP list, switch list, and output directory via **Browse**
2. Click **Check** to validate file format and see AP/switch count
3. Click **Start** to begin crawling
4. Live log shows progress with color-coded results
5. Click **Stop** to pause — progress is saved automatically
6. Click **Start** again to resume from where you left off

### Resume after interruption

If the tool stops mid-crawl (Stop, close window, VPN drop), just start again. It reads the existing `lldp_result.csv` and skips APs already crawled.

## Features

| Feature | Description |
|---------|-------------|
| PySide6 GUI | Dark/light theme toggle, no console needed |
| SSH verification | Smart error messages for host/port vs credentials |
| Remember me | Encrypted credential storage with auto-login |
| Autocomplete | Host and username suggestions from history |
| File validation | Check button shows AP/switch count and format errors |
| Multi-neighbor | Collects ALL LLDP neighbors per AP |
| Auto-reconnect | If SSH drops mid-crawl, reconnects and continues |
| Resume mode | Skips already-crawled APs on re-run |
| Graceful shutdown | Saves partial results on Stop, close, or Ctrl+C |
| Detailed logging | Full debug log in `crawl.log` |

## Build Executable

```bash
pip install pyinstaller
pyinstaller build/build.spec --distpath dist --workpath build/temp
```

Output: `dist/WAC-Crawl/WAC-Crawl.exe`

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
├── .env.example         # Credentials template
├── list_ap-example.txt  # AP list template
├── list_switch-example.txt  # Switch list template
└── requirements.txt     # Python dependencies
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Host/port not reachable` | Check VPN is active and WAC IP/port is correct |
| `Invalid username or password` | Host is reachable — check credentials |
| `Not an SSH server` | Port is open but not SSH — check port number |
| `Not a WAC device` | SSH login OK but device is not a WAC |
| AP shows `FAILED: Timeout` | AP may be behind NAT — takes longer to connect |
| AP shows `Login failed` | AP is offline or unreachable from WAC |

## Security

- Credentials encrypted with Fernet (stored in `%APPDATA%/WAC-Crawl/`)
- `.env`, `list_ap.txt`, `list_switch.txt` excluded from git
- The tool only runs **read-only** commands (`display`) — no configuration is modified
- SSH host keys are auto-accepted (standard for internal network automation)

## Requirements

- Python 3.10+
- PySide6 >= 6.5.0
- paramiko >= 3.4.0
- cryptography >= 41.0.0
- python-dotenv >= 1.0.0

## License

MIT
