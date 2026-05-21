from django.urls import path
from .views import (
    RegisterView, VerifyEmailView, LoginView, LogoutView,
    MeView, UpdateFCMTokenView, ResendVerificationView,
    StudentProfileView, TeacherProfileView,
)

urlpatterns = [   
    # auth
    path('register/',             RegisterView.as_view(),          name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(),   name='verify-email'),
    path('login/',                LoginView.as_view(),             name='login'),
    path('logout/',               LogoutView.as_view(),            name='logout'),
    path('resend-verification/',  ResendVerificationView.as_view(),name='resend-verification'),

    # user
    path('me/',                   MeView.as_view(),                name='user-me'),
    path('me/fcm-token/',         UpdateFCMTokenView.as_view(),    name='update-fcm-token'),

    # profiles
    path('profile/student/',      StudentProfileView.as_view(),    name='student-profile'),
    path('profile/teacher/',      TeacherProfileView.as_view(),    name='teacher-profile'),
]