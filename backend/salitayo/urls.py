from django.contrib import admin
from django.urls import path, include

from restructurer.views import home


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("restructurer.urls")),
    path("api/", include("assistive_writing_coach.urls")),
    path("api/auth/", include("profiles.urls")),
    path("api/system/", include("system.urls")),
]
