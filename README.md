# Automated WAC Huawei Crawl Data

Automated tool to collect LLDP neighbor data from Access Points (APs) managed by a Huawei WLAN Access Controller (WAC) via SSH.

## What does this tool do?

1. Connects to the WAC via SSH
2. Connects to each AP via `stelnet ap ap-id {ID}`
3. Runs `display lldp neighbor brief` on each AP
4. Extracts the "Neighbor Dev" column (the switch connected to the AP)
5. Maps the switch name to its IP address from the switch list
6. Outputs results to a timestamped CSV file

## Output

CSV file with the following format:

```csv
"AP","Switch"
"AP-BUILDING1-L1-IN01 (10.0.1.10)","ASW01-BUILDING1-L2 (10.0.2.20)"
"AP-BUILDING2-L1-OUT01 (10.0.1.11)","SW-BUILDING2-L1 (10.0.2.21)"
```

## Installation

```bash
# Clone the repo
git clone https://github.com/USERNAME/Automated-WAC-Huawei-Crawl-Data.git
cd Automated-WAC-Huawei-Crawl-Data

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. `.env` file

Copy the template and fill in your WAC credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
HOST=10.0.0.1
PORT=22
USERNAME=your-username
PASSWORD=your-password

# Optional (default values shown)
SSH_TIMEOUT=30
AP_CONNECT_TIMEOUT=30
COMMAND_TIMEOUT=15
```

### 2. `list_ap.txt`

Copy the template and fill with your AP data:

```bash
cp list_ap-example.txt list_ap.txt
```

Format (tab-separated):
```
AP-Name    IP-Address    ID
```

Example:
```
AP-BUILDING1-L1-IN01	10.0.1.10	0
AP-BUILDING2-L1-OUT01	10.0.1.11	1
AP-BUILDING3-L1-OUT01	--	2
```

> APs with `--` as IP will be skipped (considered offline).

### 3. `list_switch.txt`

Copy the template and fill with your switch data:

```bash
cp list_switch-example.txt list_switch.txt
```

Format (tab-separated):
```
Switch-Name    IP-Address
```

Example:
```
ASW01-BUILDING1-L2	10.0.2.20
SW-BUILDING2-L1	10.0.2.21
```

## Usage

```bash
python main.py
```

Output:
```
Processing AP 1/100: AP-BUILDING1-L1-IN01
Processing AP 2/100: AP-BUILDING2-L1-OUT01
  Skipped: AP-BUILDING3-L1-OUT01 (no IP assigned)
...

--- Crawl Summary ---
Total APs: 100
Skipped (offline): 3
Successful: 90
Failed: 7
Output file: lldp_result_20260527_143022.csv
```

## Project Structure

```
├── main.py              # Entry point
├── config.py            # Load & validate .env
├── parsers.py           # Parse AP list, switch list, LLDP output
├── ssh_client.py        # SSH connection & interactive shell
├── crawler.py           # Crawl orchestration per-AP
├── output.py            # CSV writer & summary
├── .env.example         # Credentials template
├── list_ap-example.txt  # AP list template
├── list_switch-example.txt  # Switch list template
├── requirements.txt     # Python dependencies
└── .gitignore           # Exclude sensitive files
```

## Timeout Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_TIMEOUT` | 30s | SSH connection timeout to WAC |
| `AP_CONNECT_TIMEOUT` | 30s | Stelnet connection timeout per AP |
| `COMMAND_TIMEOUT` | 15s | LLDP command execution timeout |

These can be adjusted in `.env` if the network is slow.

## Security

- Credentials are stored in `.env` (excluded from git)
- `list_ap.txt` and `list_switch.txt` contain internal IPs (excluded from git)
- The tool only runs **read-only** commands (`display`) — no WAC/AP configuration is modified

## Requirements

- Python 3.10+
- paramiko >= 3.4.0
- python-dotenv >= 1.0.0
- SSH access to Huawei WAC

## License

MIT
