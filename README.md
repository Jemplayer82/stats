# Stats Dashboard

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?style=flat&logo=sqlite&logoColor=white)

A self-hosted web dashboard that aggregates usage and health metrics from multiple AI services and infrastructure tools into a single view.

## What It Does

Displays real-time data from:

| Service | Data Shown |
|---------|-----------|
| ![Claude](https://img.shields.io/badge/Claude.ai-CC785C?style=flat&logo=anthropic&logoColor=white) | Usage quotas and limits |
| ![Ollama](https://img.shields.io/badge/Ollama.com-000000?style=flat&logoColor=white) | Bandwidth and resource utilization |
| ![Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=flat&logo=google&logoColor=white) | API request counts via Cloud Monitoring |
| ![Proxmox](https://img.shields.io/badge/Proxmox-E57000?style=flat&logo=proxmox&logoColor=white) | VM/container status, CPU, memory, disk |
| ![Ceph](https://img.shields.io/badge/Ceph-EF5C55?style=flat&logo=ceph&logoColor=white) | Cluster health, capacity, OSD status, throughput |
| ![TrueNAS](https://img.shields.io/badge/TrueNAS_SCALE-0095D5?style=flat&logo=truenas&logoColor=white) | Pool health, alerts, network traffic |

Credentials are stored locally in a SQLite database and configured through the built-in settings page.

## Deploy with Docker

**Prerequisites:** Docker and Docker Compose installed.

### 1. Clone the repo

```bash
git clone https://github.com/Jemplayer82/stats.git
cd stats
```

### 2. Create the data directory

```bash
mkdir -p /storage/stats
```

### 3. Start the container

```bash
docker compose up -d
```

The dashboard will be available at `http://<your-host>:5000`.

## Setup

1. Open `http://<your-host>:5000/settings`
2. Enter credentials for the services you want to monitor:
   - **Claude.ai** — session cookie from your browser
   - **Gemini** — Google Cloud service account JSON or API key
   - **Proxmox** — API token (user@realm!tokenid + secret)
   - **TrueNAS** — API key from TrueNAS web UI
   - **Ollama.com** — account session cookie
3. Save and return to the dashboard — cards will populate automatically.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:////data/usage.db` | SQLite path inside container |

Data is persisted at `/storage/stats` on the host.

## Useful Commands

```bash
# View logs
docker compose logs -f

# Stop
docker compose down

# Rebuild after code changes
docker compose up -d --build
```
