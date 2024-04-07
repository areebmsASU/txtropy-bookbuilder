from celery import shared_task
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse

from gutenberg.models import Subject, RawBook, Book, Chunk
from gutenberg.bookscraper import BookListScraper, BookScraper
from gutenberg.bookcleaner import BookCleaner


@shared_task
def scrape_subject_book_list(subject_id):
    BookListScraper(book_list=Subject.objects.get(gutenberg_id=subject_id)).get_books()


@shared_task
def scrape_book(gutenberg_id):
    book_scraper = BookScraper(raw_book=RawBook.objects.get(gutenberg_id=gutenberg_id))
    book_scraper.get_metadata()
    book_scraper.get_text()


@shared_task
def clean_book(gutenberg_id):
    book_cleaner = BookCleaner(raw_book=RawBook.objects.get(gutenberg_id=gutenberg_id))
    book_cleaner.parse()
    book_cleaner.chunk()
    book_cleaner.clean()


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
            html_chunked=Exists(Chunk.objects.filter(book_gutenberg_id=OuterRef("gutenberg_id")))
        )
        .select_related("book")
    ):
        data.append(
            {
                "id": raw_book.gutenberg_id,
                "title": raw_book.metadata and raw_book.metadata["title"][0],
                "skipped_reason": raw_book.skipped_reason and raw_book.get_skipped_reason_display(),
                "html_parsed": bool(raw_book.body and raw_book.html_stylesheet),
                "html_chunked": raw_book.html_chunked,
                "html_regenerated": hasattr(raw_book, "book") and bool(raw_book.book.html_map),
            }
        )
    return JsonResponse(data, safe=False)


def skip_book(gutenberg_id):
    pass
