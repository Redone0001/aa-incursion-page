from allianceauth import urls
from django.urls import include, path

urlpatterns = [
    path("", include(urls)),
]
