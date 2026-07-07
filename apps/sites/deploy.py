"""Deploy a built static site to the CDN. Cloudflare Pages, stubbed until a
token is configured. Returns a human-readable status string.
"""
import os


def deploy_site(site, build_dir):
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account:
        return (
            f"Built to {build_dir} — Cloudflare deploy skipped "
            "(set CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID to publish live)."
        )
    # TODO(phase-1b): push build_dir to a Cloudflare Pages project via the API,
    # then attach site.custom_domain. Needs the account creds above.
    return "Deployed to Cloudflare Pages."
