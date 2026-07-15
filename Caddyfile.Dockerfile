# Bakes the Caddyfile into the image instead of bind-mounting it. Hostinger's
# Docker Manager runs compose from a dir that only holds the compose file (not
# the repo), so a runtime `./Caddyfile` mount fails — but the build context has
# every repo file, so COPY works.
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
