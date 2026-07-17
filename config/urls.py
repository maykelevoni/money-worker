"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.dashboard import onboarding as ob
from apps.leads import views as lead_views
from apps.sites import api_views as sites_api

onboarding_patterns = ([
    path('', ob.start, name='start'),
    path('influencer/', ob.influencer, name='influencer'),
    path('post/', ob.post, name='post'),
    path('share/', ob.share, name='share'),
    path('share/continue/', ob.share_continue, name='share_continue'),
    path('money/', ob.money, name='money'),
    path('finish/', ob.finish, name='finish'),
    path('skip/', ob.skip, name='skip'),
], 'onboarding')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('start/', include(onboarding_patterns)),
    path('', include('apps.dashboard.urls')),
    path('factory/', include('apps.videos.urls')),
    path('websites/', include('apps.sites.urls')),
    path('social/', include('apps.social.urls')),
    path('api/optin/', sites_api.optin_api, name='api_optin'),
    path('content/', include('apps.content.urls')),
    path('offers/', include('apps.offers.urls')),
    path('', include('apps.store.urls')),  # /buy/ checkout + /members/ area
    path('', include('apps.sequences.urls')),  # /emails/ /scheduler/ /automations/
    path('leads/', lead_views.lead_list, name='leads'),
    path('leads/lists/new/', lead_views.list_create, name='list_create'),
    path('leads/lists/<int:pk>/delete/', lead_views.list_delete, name='list_delete'),
    path('leads/<int:pk>/add-list/', lead_views.lead_add_list, name='lead_add_list'),
    path('leads/<int:pk>/remove-list/<int:list_id>/', lead_views.lead_remove_list, name='lead_remove_list'),
    # Capture pages — internal management + per-page public URLs
    path('capture-pages/', lead_views.capture_pages, name='capture_pages'),
    path('capture-pages/new/', lead_views.capture_page_create, name='capture_page_create'),
    path('capture-pages/<int:pk>/edit/', lead_views.capture_page_edit, name='capture_page_edit'),
    path('capture-pages/<int:pk>/links/add/', lead_views.page_link_add, name='page_link_add'),
    path('capture-pages/<int:pk>/links/<int:link_id>/delete/', lead_views.page_link_delete, name='page_link_delete'),
    path('p/<slug:slug>/', lead_views.page, name='capture_page'),  # public capture page
    path('free/', lead_views.capture, name='capture'),  # legacy → first active page
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
