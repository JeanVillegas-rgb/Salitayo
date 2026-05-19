from django.urls import path
from .views_wp import (
    ImportWordsView,
    StartSessionView,
    SubmitAttemptView,
    EndSessionView,
    SessionStatusView,
    WordStatusView,
    SyncPosTagsView,
    WordDetailView,
    TrainModelView,
    SessionHistoryView,
)

urlpatterns = [
    path("words/import/",       ImportWordsView.as_view(),   name="import-words"),
    path("words/",              WordStatusView.as_view(),    name="word-status"),
    path("words/sync-pos/",     SyncPosTagsView.as_view(),   name="sync-pos-tags"),
    path("words/<str:word>/",   WordDetailView.as_view(),    name="word-detail"),
    path("session/start/",      StartSessionView.as_view(),  name="session-start"),
    path("session/attempt/",    SubmitAttemptView.as_view(), name="session-attempt"),
    path("session/end/",        EndSessionView.as_view(),    name="session-end"),
    path("session/status/",     SessionStatusView.as_view(), name="session-status"),
    path("session/history/",    SessionHistoryView.as_view(), name="session-history"),
    path("train/",              TrainModelView.as_view(),    name="train-model"),
]
