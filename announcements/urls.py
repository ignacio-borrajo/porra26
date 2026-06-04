from django.urls import path

from .views import AnnouncementModalView, AnnouncementPreviewView, AnnouncementSeenView

app_name = "announcements"

urlpatterns = [
    path("preview/", AnnouncementPreviewView.as_view(), name="preview"),
    path("<int:pk>/", AnnouncementModalView.as_view(), name="modal"),
    path("<int:pk>/seen", AnnouncementSeenView.as_view(), name="seen"),
]
