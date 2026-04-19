# stats — Project Notes

## Deployment

- **Webserver:** `landon@192.168.7.50`
- **Target directory:** `/storage/stats`

### Deploy (run from your local machine)

```bash
# 1. Sync files to server (excludes git, venv, db, etc.)
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='venv/' --exclude='instance/' --exclude='*.db' \
  /home/user/stats/ landon@192.168.7.50:/storage/stats/

# 2. SSH in and start the container
ssh landon@192.168.7.50 "cd /storage/stats && docker compose up -d --build"
```

### Update (re-deploy after changes)

```bash
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='venv/' --exclude='instance/' --exclude='*.db' \
  /home/user/stats/ landon@192.168.7.50:/storage/stats/ && \
ssh landon@192.168.7.50 "cd /storage/stats && docker compose up -d --build"
```

### Useful commands on the server

```bash
docker compose logs -f        # stream logs
docker compose ps             # check status
docker compose down           # stop
```
