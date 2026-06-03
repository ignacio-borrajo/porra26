from django.urls import path

from .views import AnnouncementModalView, AnnouncementSeenView

app_name = "announcements"

urlpatterns = [
    path("<int:pk>/", AnnouncementModalView.as_view(), name="modal"),
    path("<int:pk>/seen", AnnouncementSeenView.as_view(), name="seen"),
]
