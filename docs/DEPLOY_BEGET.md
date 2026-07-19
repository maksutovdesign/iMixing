# Deploy iMixing demo to Beget

This guide is for a temporary public internet demo with free demo credits.

Recommended Beget product: VPS/VDS with the ready Docker image. The FastAPI app has audio dependencies, background processing, uploaded files, and SQLite state, so a Docker VPS is safer than classic shared hosting.

## What will be available

- Public web UI: `http://YOUR_SERVER_IP/`
- v2 UI: `http://YOUR_SERVER_IP/v2`
- Early access: `http://YOUR_SERVER_IP/early-access`
- Health check: `http://YOUR_SERVER_IP/health`
- Free demo credits: `25` credits per browser session by default

## Minimum VPS

For a small private demo:

- 2 CPU cores
- 2 GB RAM
- 30 GB disk
- Docker ready image

The demo config limits audio processing to short test files:

- up to 100 MB total WAV upload
- up to 12 stems
- up to 180 seconds per WAV file
- MIDI up to 5 MB

## Server setup

Connect to the Beget VPS:

```bash
ssh root@YOUR_SERVER_IP
```

Install git if the Docker image does not include it:

```bash
apt-get update
apt-get install -y git
```

Clone the repository:

```bash
mkdir -p /opt/imixing
cd /opt/imixing
git clone https://github.com/maksutovdesign/iMixing.git .
```

If the repository is private, use an SSH deploy key or a GitHub token. Do not paste permanent personal tokens into shell history on shared machines.

Create production env:

```bash
cp .env.beget.example .env.production
nano .env.production
```

Replace:

```bash
IMIXING_PUBLIC_BASE_URL=http://YOUR_BEGET_SERVER_IP
```

Start the demo:

```bash
docker compose -f docker-compose.beget.yml --env-file .env.production up -d --build
```

Check health:

```bash
docker compose -f docker-compose.beget.yml ps
curl -fsS http://127.0.0.1/health
```

Open:

```text
http://YOUR_SERVER_IP/
```

## Update deployment

```bash
cd /opt/imixing
git pull
docker compose -f docker-compose.beget.yml --env-file .env.production up -d --build
```

## Logs

```bash
docker compose -f docker-compose.beget.yml logs -f --tail=200 imixing-web
```

## Stop demo

```bash
docker compose -f docker-compose.beget.yml down
```

Persistent demo state is stored in the Docker volume `imixing_data`.

## Domain later

For a real domain, point an `A` record to the VPS IP, then put Nginx/Caddy/Traefik in front of the container and enable HTTPS. For the first temporary test link, plain `http://SERVER_IP/` is enough.
