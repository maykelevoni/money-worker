# Deploy / Redeploy

## Redeploy to production (run on the VPS)

SSH into the VPS (or use Hostinger hPanel → VPS → Browser terminal), then run:

```bash
cd /docker/money-worker/src && git pull && cp -rf . .. && cd .. && docker compose build --no-cache web && docker compose up -d
```

This pulls the latest code from GitHub, copies it into the build folder,
rebuilds the `web` image, and restarts the containers.

Check it worked: open https://getpostforge.cloud/ — should load (HTTP 200).

## Notes

- **The panel's "Update" button does NOT rebuild** the image, and the source
  isn't kept in `/docker/money-worker`. So "Update" alone will not apply code
  changes. Always use the command above to deploy code.
- `git pull` only gets changes already pushed to GitHub. To publish local
  changes first (on your PC):
  ```bash
  git add -A && git commit -m "what changed" && git push upstream main
  ```
- Do **not** use the panel's **Delete** — it wipes the project and your panel
  env vars (API keys, SITE_HOST, DATABASE_URL, etc.).

## If the site 502s

Almost always means the `web` container is crash-looping. Check its logs in the
Docker Manager. A Django `SystemCheckError` on boot (missing dependency, bad
setting) will exit the container, and Caddy then returns 502 because it can't
reach `web`.
