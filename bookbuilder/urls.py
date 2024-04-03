from django.urls import path
from django.http import JsonResponse

from gutenberg.models import Subject, Chunk

from django.db.models import Count, Exists, OuterRef


def subjects(request):
    return JsonResponse(
        list(
            Subject.objects.annotate(raw_book_count=Count("raw_books")).values(
                "gutenberg_id", "label", "raw_book_count"
            )
        ),
        safe=False,
    )


def raw_books(request, subject_id):
    data = []
    for raw_book in (
        Subject.objects.get(gutenberg_id=subject_id)
        .raw_books.annotate(
            html_chunked=Exists(
                Chunk.objects.filter(book_gutenberg_id=OuterRef("gutenberg_id"))
            )
        )
        .select_related("book")
    ):
        data.append(
            {
                "id": raw_book.gutenberg_id,
                "title": raw_book.metadata and raw_book.metadata["title"][0],
                "skipped_reason": raw_book.skipped_reason
                and raw_book.get_skipped_reason_display(),
                "html_parsed": bool(raw_book.body and raw_book.html_stylesheet),
                "html_chunked": raw_book.html_chunked,
                "html_regenerated": hasattr(raw_book, "book")
                and bool(raw_book.book.html_map),
            }
        )
    return JsonResponse(data, safe=False)


urlpatterns = [
    path("", subjects),
    path("<int:subject_id>/", raw_books),
]
