from django.urls import path

from .views import RestructureTextView, home, tts_speech


urlpatterns = [
    path("", home, name="home"),
    path("restructure/", RestructureTextView.as_view(), name="restructure-text"),
    path("tts-speech/", tts_speech, name="tts-speech"),
]
