---
name: deploy-hetzner
description: Deploy and operate services on a Hetzner VPS with Docker Compose and Caddy. Use for "deploy", "rollout", "production", "Hetzner", "Caddy", "docker compose", "reverse proxy", "TLS", "health check", "rollback", or when a live site must be updated without downtime. Read-only recon first, one change at a time, always with a rollback path.
---

# Deploy on Hetzner

A production server is shared state. Recon first, change one thing, verify,
and keep a rollback ready. Never run a destructive command you cannot undo.

## Ground rules

- **Never commit secrets.** `.env`, service config, and keys stay on the server.
- **Read before write:** `docker ps`, `docker compose config`, `caddy validate`.
- **One change per deploy.** A pull, a rebuild, and a config change are three
  separate steps with their own verification.
- **No blind cleanup.** `docker system prune -a` can remove the image you need
  to roll back to. Prune build cache first.
- **Ask before touching the firewall, SSH, or the reverse proxy.** A mistake
  there locks everyone out.

## Recon

```sh
hostnamectl
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker compose -f /opt/<app>/docker-compose.yml config -q
docker exec caddy caddy validate --config /etc/caddy/Caddyfile
df -h /
free -h
```

Record the current image tags. That is your rollback target.

## Deploy a Compose service

```sh
cd /opt/<app>
docker compose pull                 # or: docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps
docker compose logs --tail=80 <service>
```

Health check before calling it done:

```sh
curl -fsS --retry 10 --retry-delay 2 --retry-connrefused http://127.0.0.1:<port>/health
```

If the container has no health endpoint, check the port and the logs, and say
explicitly that the check is weaker.

## Caddy

```sh
docker exec caddy caddy validate --config /etc/caddy/Caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Verify from outside with the real hostname and TLS:

```sh
curl -fsSI https://<host>/
curl -fsS https://<host>/health
```

An `on_demand_tls` block with an `ask` endpoint is a security boundary: do not
expose the ask endpoint publicly.

## Database changes

1. Back up first: `pg_dump`/`sqlite3 .backup`/volume snapshot.
2. Run the migration in a maintenance window or behind a feature flag.
3. Verify row counts and the app's read path.
4. Keep the backup until the deploy has survived a full traffic cycle.

## Rollback

```sh
# image tag rollback
docker compose down
IMAGE_TAG=<previous> docker compose up -d

# or restore the previous compose file
cp docker-compose.yml.bak docker-compose.yml && docker compose up -d
```

Test the rollback path before you need it. A rollback that was never run is a
guess.

## Disk and logs

```sh
docker system df
docker builder prune -f            # safe: rebuilds are cheap
docker image prune -f              # only dangling images
journalctl -u <service> --since '30 min ago'
```

Do not delete volumes. They hold the data.

## Security baseline

- Only 22, 80, 443 public; databases and app ports stay on the Docker network.
- SSH key auth only; no root password login.
- TLS everywhere; HSTS only after the domain is stable.
- Backups off the server, tested by restoring once.

## Report

State: what changed, the image tag before and after, the health result, the
rollback command, and anything still unverified. No "should work".
