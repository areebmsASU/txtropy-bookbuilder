from django.urls import path
from django.http import JsonResponse
from django.db.models import Count, Exists, OuterRef

from gutenberg.views import subjects, raw_books


urlpatterns = [
    path("", subjects),
    path("<int:subject_id>/", raw_books),
]
