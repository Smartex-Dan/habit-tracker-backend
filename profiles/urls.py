from django.urls import path

from .views import AvatarUploadView

urlpatterns = [
    path("profile/avatar", AvatarUploadView.as_view(), name="profile-avatar-upload"),
]