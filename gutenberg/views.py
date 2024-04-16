from celery import shared_task
from django.db.models import Count
from django.http import JsonResponse

from gutenberg.models import Subject, RawBook
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
def async_clean_book(gutenberg_id):
    print("Initiated.")
    book_cleaner = BookCleaner(raw_book=RawBook.objects.get(gutenberg_id=gutenberg_id))
    book_cleaner.refresh()
    print(f"{gutenberg_id} refreshed.")
    book_cleaner.parse()
    print(f"{gutenberg_id} parsed.")
    book_cleaner.chunk()
    print(f"{gutenberg_id} chunked.")
    book_cleaner.clean()
    print(f"{gutenberg_id} cleaned.")


def subjects(request):
    return JsonResponse(
        list(
            Subject.objects.annotate(raw_book_count=Count("raw_books"))
            .values("gutenberg_id", "label", "raw_book_count")
            .order_by("-raw_book_count")
        ),
        safe=False,
    )


def raw_books(request, subject_id):
    data = []
    for raw_book in (
        Subject.objects.get(gutenberg_id=subject_id)
        .raw_books.annotate(chunk_count=Count("chunks"))
        .select_related("book")
        .order_by("skipped", "gutenberg_id")
    ):
        data.append(
            {
                "id": raw_book.gutenberg_id,
                "title": raw_book.metadata and raw_book.metadata["title"][0],
                "skipped_reason": raw_book.skipped_reason and raw_book.get_skipped_reason_display(),
                "css": bool(raw_book.html_stylesheet),
                "chunks": raw_book.chunk_count,
                "html_regenerated": hasattr(raw_book, "book") and bool(raw_book.book.html_map),
            }
        )
    return JsonResponse(data, safe=False)


def skip_book(request, gutenberg_id):
    if request.method == "POST":
        raw_book = RawBook.objects.get(gutenberg_id=gutenberg_id)
        raw_book.skip("FORMAT")
        return JsonResponse({})


def clean_book(request, gutenberg_id):
    task = None
    if request.method == "POST":
        try:
            raw_book = RawBook.objects.get(gutenberg_id=gutenberg_id)
            raw_book.body = None
            raw_book.html_stylesheet = None
            raw_book.chunks.all().delete()
            if hasattr(raw_book, "book"):
                raw_book.book.delete()
            raw_book.save(update_fields=["body", "html_stylesheet"])
            task = async_clean_book.delay(gutenberg_id)
        except Exception as e:
            raise print(e.args)
    return JsonResponse({"task": str(task)})


def chunks(request, gutenberg_id):
    i = request.GET.get("i", 0)

    book = RawBook.objects.filter(gutenberg_id=gutenberg_id).first()
    if book is None:
        return JsonResponse({"error": "Book not found."}, status=404)

    data = {"chunks": list(book.chunks.filter(pk__gte=i).order_by("id")[:251].values("id", "text"))}

    if len(data["chunks"]) > 250:
        base_url = request.build_absolute_uri().split("?")[0]
        next_chunk_id = data["chunks"].pop()["id"]
        data["next_page"] = f"{base_url}?i={next_chunk_id}"

    return JsonResponse(data)
