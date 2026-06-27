# Deploying Money Worker (Coolify)

The app is **stateless** — the database lives on **Neon** and media on **Cloudflare R2**,
so the server only runs the Django process. Redeploys are safe and disposable.

## One-time: install Coolify on your VPS
```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```
Then open `http://<your-vps-ip>:8000` and create your admin account.

## Create the application
1. **+ New → Application → Public/Private Repository**, point it at this repo.
2. Build pack: **Dockerfile** (this repo has one).
3. Set the domain (e.g. `https://app.yourdomain.com`). Coolify gets HTTPS automatically.
4. Add the environment variables below.
5. **Deploy.** Coolify builds the image (running `collectstatic`), and the container
   runs migrations then starts gunicorn (see `entrypoint.sh`).

Every `git push` to the tracked branch redeploys.

## Environment variables (set in Coolify → Environment)
```
# Core
SECRET_KEY=<long-random-string>
DEBUG=False
ALLOWED_HOSTS=app.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://app.yourdomain.com

# Database (Neon) — stays in env (read at boot)
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/dbname

# Media (Cloudflare R2) — stays in env (storage configured at boot)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_PUBLIC_URL=https://pub-xxxx.r2.dev

# Integrations (edit these here anytime — no redeploy of code needed)
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-opus-4-8
FAL_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
UPLOAD_POST_API_KEY=
UPLOAD_POST_USER=
RESEND_API_KEY=
RESEND_FROM_EMAIL=
```
Generate a `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## First deploy: create your login
Login uses the Django admin. Open a terminal on the app in Coolify and run:
```bash
python manage.py createsuperuser
```

## Notes
- Migrations run automatically on each deploy via `entrypoint.sh`. If you ever scale to
  more than one replica, move `migrate` to a Coolify "pre-deployment command" instead so
  it runs once.
- Static files are served by WhiteNoise (built into the image) — no nginx config needed.
- To change an integration key, edit it in Coolify's Environment tab and restart the app —
  no code change, no rebuild.
