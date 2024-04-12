from django.urls import path
from gutenberg.views import subjects, raw_books, skip_book, clean_book


urlpatterns = [
    path("", subjects),
    path("<int:subject_id>/", raw_books),
    path("book/skip/<int:gutenberg_id>/", skip_book),
    path("book/clean/<int:gutenberg_id>/", clean_book),
]
