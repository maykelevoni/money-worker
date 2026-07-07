from django.conf import settings

from .models import Website


class SiteMiddleware:
    """Routes a request to a public Website when it arrives on a site host.

    App host (SITE_HOST) → normal app. A `<subdomain>.<SITE_HOST>` or a matching
    `custom_domain` → sets `request.site` and swaps in the site urlconf so only
    the public site routes are reachable there.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.app_host = settings.SITE_HOST.split(":")[0].lower()

    def __call__(self, request):
        request.site = None
        host = request.get_host().split(":")[0].lower()
        if host and host not in (self.app_host, "127.0.0.1"):
            site = self._match(host)
            if site is not None:
                request.site = site
                request.urlconf = settings.SITE_URLCONF
        return self.get_response(request)

    def _match(self, host):
        site = Website.objects.filter(
            custom_domain__iexact=host, status="published"
        ).first()
        if site:
            return site
        suffix = "." + self.app_host
        if host.endswith(suffix):
            sub = host[: -len(suffix)]
            return Website.objects.filter(subdomain=sub, status="published").first()
        return None
