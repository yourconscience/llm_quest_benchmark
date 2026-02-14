# Deployment Options (Flask)

Goal: expose `llm-quest server` publicly with a stable domain you control.

## Recommended: Cloudflare Tunnel + Custom Domain

This keeps your Flask app running where it already runs, while Cloudflare provides a stable hostname and TLS.

### Steps
1. Run Flask in production mode on local host:
```bash
uv run llm-quest server --host 127.0.0.1 --port 8000 --production --workers 4
```
2. Install and authenticate `cloudflared`.
3. Create a named tunnel:
```bash
cloudflared tunnel create llmquest
```
4. Route DNS for your domain/subdomain:
```bash
cloudflared tunnel route dns llmquest quest.yourdomain.com
```
5. Create a local Cloudflare config file (for example, in your home `.cloudflared` directory):
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<user>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: quest.yourdomain.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```
6. Run tunnel:
```bash
cloudflared tunnel run llmquest
```

Result: fixed URL such as `https://quest.yourdomain.com` (not a random tunnel URL).

## Managed Hosting Alternatives

### Fly.io
- Deploy as containerized Flask app with persistent volume for SQLite.
- Good control and fixed app hostname/custom domain support.

### Render
- Deploy as Python web service (`gunicorn` entrypoint) with custom domain.
- Simple setup, managed TLS, and background workers if needed later.

## Production Notes
- Prefer running behind `gunicorn` for non-dev traffic.
- Keep `instance/` and `metrics.db` on persistent storage.
- Add periodic backups for SQLite files.
- Restrict CORS and add authentication if the app is public-facing.
