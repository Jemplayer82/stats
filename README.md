<img src="assets/fathom-header-banner.svg" alt="Fathom Works — stats" width="100%">

# `$ stats`

**A self-hosted web dashboard that aggregates usage and health metrics from multiple AI services and home infrastructure into a single view.** Configure your credentials once and check everything from one page.

---

## `[ what it monitors ]`

| Service | Data Shown |
|---------|------------|
| Claude.ai | Usage quotas and limits |
| Codex / ChatGPT | Usage windows, reset countdowns, and daily token history when available |
| Ollama.com | Bandwidth and resource utilization |
| Google Gemini | API request counts via Cloud Monitoring |
| Proxmox | VM and container status, CPU, memory, disk |
| Ceph | Cluster health, capacity, OSD status, throughput |
| TrueNAS SCALE | Pool health, VMs, network traffic, and acknowledgeable alerts |
| UniFi Network | Devices, clients, and WAN uptime/latency history |

Credentials are stored locally in a SQLite database and managed through the built-in settings page — nothing leaves your machine.

---

## `[ stack ]`

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11 + Flask |
| Database | SQLite (via Flask-SQLAlchemy) |
| Deployment | Docker + Docker Compose |

---

## `[ quick start ]`

### 1. clone the repo

```bash
$ git clone https://github.com/jemplayer82/stats.git
$ cd stats
```

### 2. create the data directory

```bash
$ mkdir -p /storage/stats
```

### 3. start the container

```bash
$ docker compose up -d
```

The dashboard will be available at **http://\<your-host\>:5000**.

Open a compact widget-only view at **http://<your-host>:5000/widget** for a smaller dashboard that only shows usage meters (Codex, Claude.ai, Ollama.com, Gemini).  
Use that page in a small always-on-top browser window for a desktop-style widget.

Use **Settings → Usage cards to show** to choose which usage cards are visible.

## `[ widgetlauncher integration ]`

The repository includes a native Windows extension in [`widget-launcher/`](widget-launcher/README.md). It provides a desktop widget with settings for the Stats address, visible services, connection testing, and refresh frequency.

If you are using [Widget Launcher](https://github.com/chanallenk/widgetlauncher.extension), your extension can consume this endpoint:

### `GET /api/widget/usage`

Returns a compact JSON payload your desktop widget can bind to, with optional filtering by services:

```bash
# Return whatever is enabled in Settings
curl "http://<your-host>:5000/api/widget/usage"

# Return only chosen services
curl "http://<your-host>:5000/api/widget/usage?services=codex,claude,gemini"
```

The response includes:

- `schema_version` (currently `stats-widget-v1`)
- `timestamp`
- `services[]` entries (`codex`, `claude`, `ollama`, `gemini`)
  - `status`: `ok` or `error`
  - `visible`: whether the service is enabled in Settings
  - `payload`: same shape as each service’s existing `api/*-usage` endpoint

Quick C# shape in your Widget Launcher control:

```csharp
using System.Net.Http;
using System.Net.Http.Json;

public sealed record WidgetServicePayload(
    string ServiceId,
    string Status,
    bool Visible,
    object Payload);

public sealed record WidgetPayload(
    string SchemaVersion,
    long Timestamp,
    WidgetServicePayload[] Services);

...
var client = new HttpClient();
var data = await client.GetFromJsonAsync<WidgetPayload>(
    "http://192.168.1.10:5000/api/widget/usage?services=codex,claude,ollama");
```

You can map `Payload` from each service into your WPF controls and refresh on your widget
interval. If you want each extension instance to keep its own service selection, pass that
selection through `services` on each request and keep that selection in the extension’s saved
settings.

---

## `[ configuration ]`

Open `http://<your-host>:5000/settings` and enter credentials for the services you want to monitor:

| Service | What You Need |
|---------|---------------|
| Claude.ai | Session cookie from your browser |
| Ollama.com | Account session cookie |
| Google Gemini | Cloud service account JSON or API key |
| Proxmox | API token (`user@realm!tokenid` + secret) |
| TrueNAS SCALE | API key from the TrueNAS web UI |
| UniFi Network | **API key** (preferred) — or controller username/password |

Save and return to the dashboard — each service card populates automatically.

> **UniFi auth:** prefer an **API key** (UniFi → Settings → Control Plane → Integrations).
> It's stateless — sent as the `X-API-KEY` header with no login call — so it can't trip
> UniFi OS's login-attempt rate limit the way repeated username/password logins do. Username
> and password still work as a fallback when no key is set.

---

## `[ environment variables ]`

### Codex account setup

The image includes a pinned Codex CLI. After pulling the updated image in Portainer,
open the `stats` container console and run:

```bash
codex -c 'cli_auth_credentials_store="file"' login --device-auth
```

Alternatively, on the Docker host:

```bash
docker exec -it stats codex -c 'cli_auth_credentials_store="file"' login --device-auth
```

Follow the displayed link and code using your ChatGPT account. Device-code login may
need enabling in ChatGPT security settings. Credentials live under `CODEX_HOME`,
which the image sets to `/data/codex` inside the existing persistent `/data` volume.
Treat that volume as sensitive. No browser cookie or OpenAI API key is needed.

The dashboard reads `account/rateLimits/read` and `account/usage/read` through
[Codex app-server](https://learn.chatgpt.com/docs/app-server). It never starts a model
turn. A shared cache refreshes on dashboard access at most once every five minutes
(failed requests retry after one minute). Login changes invalidate the cache.
Usage percentages are account-wide; the card uses the actual returned window lengths
and separate limit buckets. Missing windows are omitted, and unavailable history is
shown explicitly. The graph shows up to 30 reported days; missing days aren't
invented as zero. Temporary failures retain previously collected data with a stale
label and its original timestamp. Only sanitized metrics are returned to the browser.

To reconnect, rerun the login command. To disconnect, run `codex logout` in the
container. Update the `CODEX_VERSION` Docker build argument when upgrading the CLI;
older versions may not provide daily history even when quota bars work.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:////data/usage.db` | SQLite path inside the container |
| `CODEX_HOME` | `/data/codex` (Docker image) | Persistent Codex login and usage cache |

Data is persisted to `/storage/stats` on the host.

---

## `[ useful commands ]`

```bash
# View logs
$ docker compose logs -f

# Stop
$ docker compose down

# Rebuild after code changes
$ docker compose up -d --build

# Backup current settings before updating/redeploying
$ ./scripts/stats-backup.sh

# Restore a backup (replace `usage-YYYYMMDD_HHMMSS.db` with your backup file)
$ ./scripts/stats-restore.sh backups/usage-YYYYMMDD_HHMMSS.db

# One-command safe deploy (backup -> pull -> rebuild -> up)
$ ./scripts/update-stats.sh
```

## `[ preserving settings ]`

Your service credentials and usage-card visibility settings are stored in the SQLite DB
inside the `stats` data volume (`stats_data` inside Docker Compose).

- `scripts/stats-backup.sh` copies `/data/usage.db` from that volume into the repo's
  `backups/` folder so you can keep a dated snapshot.
- `scripts/stats-restore.sh` restores any `usage-*.db` backup into the live volume.
- `scripts/update-stats.sh` runs backup + `docker compose pull` + `docker compose up -d --build`
  in one step.

If something changes during an update, restore the newest backup and run:

```bash
$ ./scripts/stats-restore.sh
$ docker compose restart stats
```

---

<img src="assets/fathom-footer-banner.svg" alt="Fathom Works — sound the depths before you set a course" width="100%">
