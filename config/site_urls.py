"""URLconf swapped in for requests that resolve to a public Website host."""
from django.urls import path

from apps.sites import public_views as v

urlpatterns = [
    path("", v.live_home, name="site_home"),
    path("sitemap.xml", v.sitemap, name="site_sitemap"),
    path("robots.txt", v.robots, name="site_robots"),
    path("optin/", v.optin, name="site_optin"),
    path("blog/", v.live_blog, name="site_blog"),
    path("blog/<slug:slug>/", v.live_article, name="site_article"),
    path("<slug:slug>/", v.live_page, name="site_page"),
]
