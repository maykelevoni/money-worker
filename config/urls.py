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

from apps.leads import views as lead_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('factory/', include('apps.videos.urls')),
    path('websites/', include('apps.sites.urls')),
    path('content/', include('apps.content.urls')),
    path('offers/', include('apps.offers.urls')),
    path('', include('apps.sequences.urls')),  # /emails/ /scheduler/ /automations/
    path('leads/', lead_views.lead_list, name='leads'),
    # Capture pages — internal management + per-page public URLs
    path('capture-pages/', lead_views.capture_pages, name='capture_pages'),
    path('capture-pages/new/', lead_views.capture_page_create, name='capture_page_create'),
    path('capture-pages/<int:pk>/edit/', lead_views.capture_page_edit, name='capture_page_edit'),
    path('p/<slug:slug>/', lead_views.page, name='capture_page'),  # public capture page
    path('free/', lead_views.capture, name='capture'),  # legacy → first active page
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
