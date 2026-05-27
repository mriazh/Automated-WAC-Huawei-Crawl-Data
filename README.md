# Automated WAC Huawei Crawl Data

Automated tool to collect LLDP neighbor data from Access Points (APs) managed by a Huawei WLAN Access Controller (WAC) via SSH.

## What does this tool do?

1. Connects to the WAC via SSH
2. Connects to each AP via `stelnet ap ap-id {ID}`
3. Runs `display lldp neighbor brief` on each AP
4. Extracts **all** "Neighbor Dev" entries (the devices connected to the AP)
5. Maps each neighbor device name to its IP address from the switch list
6. Outputs results to a CSV file

## Output

CSV file (`lldp_result.csv`) with the following format:

```csv
"AP","Switch"
"AP-H3-L1-IN11 (10.0.1.10)","ASW02-HG3-L2RW (10.0.2.20)"
"AP-MD-L1-IN22 (10.0.1.11)","AP-MD-L1-IN07 (N/A)"
"AP-MD-L1-IN22 (10.0.1.11)","AP-MD-L1-IN14 (N/A)"
"AP-MD-L1-IN22 (10.0.1.11)","ASW01-MD-L1 (10.0.2.21)"
```

> APs with multiple LLDP neighbors will have multiple rows in the CSV (one per neighbor).

## Prerequisites

- **Python 3.10 or higher** — [Download here](https://www.python.org/downloads/)
- **SSH access** to the Huawei WAC (IP, port, username, password)
- **VPN connection** (if the WAC is on an internal network)

## Installation

### Step 1: Download the project

```bash
git clone https://github.com/USERNAME/Automated-WAC-Huawei-Crawl-Data.git
cd Automated-WAC-Huawei-Crawl-Data
```

Or download as ZIP from GitHub and extract it.

### Step 2: Install Python dependencies

Open a terminal/command prompt in the project folder and run:

```bash
pip install -r requirements.txt
```

### Step 3: Set up configuration files

You need to create 3 files. Templates are provided — just copy and fill them in.

#### 3a. Credentials (`.env`)

```bash
copy .env.example .env
```

Open `.env` in a text editor and fill in your WAC connection details:

```env
HOST=192.168.x.x
PORT=22
USERNAME=your-username
PASSWORD=your-password
```

Optional timeout settings (in seconds):

```env
SSH_TIMEOUT=30
AP_CONNECT_TIMEOUT=30
COMMAND_TIMEOUT=15
```

> Increase `AP_CONNECT_TIMEOUT` to 60 if you have APs behind NAT.

#### 3b. AP List (`list_ap.txt`)

```bash
copy list_ap-example.txt list_ap.txt
```

Open `list_ap.txt` and fill with your AP data. Format is **tab-separated**, one AP per line:

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

#### 3c. Switch List (`list_switch.txt`)

```bash
copy list_switch-example.txt list_switch.txt
```

Open `list_switch.txt` and fill with your switch data. Format is **tab-separated**:

```
Switch-Name<TAB>IP-Address
```

Example:
```
ASW02-HG3-L2RW	10.0.2.20
SW-MD-L1-2530	10.0.2.21
```

> This is used to map neighbor device names to their IP addresses in the output.

## Usage

### Run the tool

```bash
python main.py
```

### What you'll see

```
  Mode     : FRESH START (no previous results found)
  Total APs: 451

Connected to WAC. Starting crawl...

[1/451] AP-BUILDING1-L1-IN01 -> ASW01-BUILDING1-L2
[2/451] AP-BUILDING2-L1-OUT01 -> SW-BUILDING2-L1, AP-BUILDING2-L1-IN01
[3/451] AP-OFFLINE-01 - SKIP (offline)
...

--- Crawl Summary ---
Total APs processed this run: 451
Skipped (offline): 4
Successful: 440
Failed: 7
Output file: .\lldp_result.csv
```

### Resume after interruption

If the tool stops mid-crawl (Ctrl+C, VPN drop, SSH timeout), just run it again:

```bash
python main.py
```

It will automatically detect the existing `lldp_result.csv` and skip APs that were already crawled:

```
  Mode     : RESUME (continuing previous crawl)
  Done     : 149 APs already in lldp_result.csv
  Remaining: 302 APs to crawl
```

### Start fresh

To start over from scratch, delete the CSV file first:

```bash
del lldp_result.csv
python main.py
```

## Features

| Feature | Description |
|---------|-------------|
| Multi-neighbor | Collects ALL LLDP neighbors per AP, not just the first |
| Auto-reconnect | If SSH drops mid-crawl, reconnects and continues |
| Resume mode | Skips already-crawled APs on re-run |
| Ctrl+C safe | Saves partial results before exiting |
| Detailed logging | Full debug log in `crawl.log` |
| Clean console | One-line progress per AP |

## Timeout Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_TIMEOUT` | 30s | SSH connection timeout to WAC |
| `AP_CONNECT_TIMEOUT` | 30s | Stelnet connection timeout per AP |
| `COMMAND_TIMEOUT` | 15s | LLDP command execution timeout |

Set these in `.env`. Increase `AP_CONNECT_TIMEOUT` if you have APs behind NAT (they take longer to connect).

## Project Structure

```
├── main.py              # Entry point — run this
├── config.py            # Load & validate .env
├── parsers.py           # Parse AP list, switch list, LLDP output
├── ssh_client.py        # SSH connection & interactive shell
├── crawler.py           # Crawl orchestration per-AP
├── output.py            # CSV writer & summary
├── .env.example         # Credentials template
├── list_ap-example.txt  # AP list template
├── list_switch-example.txt  # Switch list template
├── requirements.txt     # Python dependencies
├── tests/               # Unit tests (55 tests)
└── .gitignore           # Exclude sensitive files
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Unable to connect` | Check VPN is active and WAC IP is correct |
| `Authentication failed` | Check username/password in `.env` |
| `Socket is closed` after ~150 APs | WAC session limit — tool auto-reconnects |
| AP shows `FAILED: Timeout` | AP may be behind NAT — increase `AP_CONNECT_TIMEOUT=60` in `.env` |
| `Connection closed by remote host` | Normal for some APs — tool handles this gracefully |

## Security

- Credentials are stored in `.env` (excluded from git)
- `list_ap.txt` and `list_switch.txt` contain internal IPs (excluded from git)
- The tool only runs **read-only** commands (`display`) — no WAC/AP configuration is modified
- SSH host keys are auto-accepted (standard for internal network automation)

## Running Tests

```bash
python -m pytest tests/ -v
```

## Requirements

- Python 3.10+
- paramiko >= 3.4.0
- python-dotenv >= 1.0.0
- SSH access to Huawei WAC

## License

MIT
