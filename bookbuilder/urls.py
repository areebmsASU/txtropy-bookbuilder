from django.urls import path
from gutenberg.views import subjects, subject_status, skip_book, clean_book, chunks


urlpatterns = [
    path("", subjects),
    path("<int:subject_id>/", subject_status),
    path("chunks/<int:gutenberg_id>/", chunks),
    path("book/skip/<int:gutenberg_id>/", skip_book),
    path("book/clean/<int:gutenberg_id>/", clean_book),
]
