from django.urls import path
from .views import (
    AnalyzeView,
    AlignmentView,
    HealthView,
    PassageListView,
    PassageDetailView,
    PassageExtractView,
    PassageDeleteView,
)

urlpatterns = [
    path('analyze/', AnalyzeView.as_view(), name='analyze'),
    path('alignment/', AlignmentView.as_view(), name='alignment'),
    path('health/', HealthView.as_view(), name='health'),
    path('passages/', PassageListView.as_view(), name='passage-list'),
    path('passages/extract/', PassageExtractView.as_view(), name='passage-extract'),
    path('passages/<int:passage_id>/', PassageDetailView.as_view(), name='passage-detail'),
    path('passages/<int:passage_id>/delete/', PassageDeleteView.as_view(), name='passage-delete'),
]
