from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.website_list, name="list"),
    path("new/", views.website_create, name="create"),
    path("<int:pk>/edit/", views.website_edit, name="edit"),
    path("<int:pk>/delete/", views.website_delete, name="delete"),
    # Pages
    path("<int:website_pk>/pages/new/", views.page_create, name="page_create"),
    path("pages/<int:pk>/edit/", views.page_edit, name="page_edit"),
    path("pages/<int:pk>/delete/", views.page_delete, name="page_delete"),
    # Blog articles
    path("<int:website_pk>/articles/attach/", views.article_attach, name="article_attach"),
    path("articles/<int:pk>/toggle/", views.article_toggle, name="article_toggle"),
    # Sections (page builder)
    path("pages/<int:page_pk>/sections/add/", views.section_add, name="section_add"),
    path("sections/<int:pk>/edit/", views.section_edit, name="section_edit"),
    path("sections/<int:pk>/move/<str:direction>/", views.section_move, name="section_move"),
    path("sections/<int:pk>/delete/", views.section_delete, name="section_delete"),
    # In-app preview (no DNS)
    path("<int:pk>/preview/", views.preview_home, name="preview_home"),
    path("<int:pk>/preview/blog/", views.preview_blog, name="preview_blog"),
    path("<int:pk>/preview/blog/<slug:slug>/", views.preview_article, name="preview_article"),
    path("<int:pk>/preview/<slug:slug>/", views.preview_page, name="preview_page"),
]
