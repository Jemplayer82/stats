# stats

Personal dashboard for monitoring Claude AI usage, Proxmox, TrueNAS, Ollama, and Gemini.

## Deployment

- Deployed via **Portainer** pulling from **ghcr.io/jemplayer82/stats:latest**
- GitHub Actions builds and pushes the image on every push to `master`
- **Never use `build: .` in docker-compose.yml** — Portainer cannot build images, it only pulls
- Push changes directly to `master` — no PRs needed for this repo
