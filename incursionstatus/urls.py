from django.urls import path

from . import views

app_name = "incursionstatus"

urlpatterns = [
    path("", views.index, name="index"),
]

