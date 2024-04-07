from django.urls import path
from gutenberg.views import subjects, raw_books


urlpatterns = [
    path("", subjects),
    path("<int:subject_id>/", raw_books),
]
