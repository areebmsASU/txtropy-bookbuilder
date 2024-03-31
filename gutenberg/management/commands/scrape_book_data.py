from django.core.management.base import BaseCommand

from gutenberg.models import Subject, RawBook, Book
from gutenberg.bookscraper import BookListScraper, BookScraper
from gutenberg.bookcleaner import BookCleaner


class Command(BaseCommand):
    help = "Economics URL was scraped to get all of the gutenberg book_ids."

    def handle(self, *args, **options):
        econ_book_list, created = Subject.objects.get_or_create(
            label="Economics", gutenberg_id=1301
        )
        list_scraper = BookListScraper(book_list=econ_book_list)
        list_scraper.get_books()

        RawBook.objects.get(gutenberg_id=38194).skip("DUPLICATE")

        for raw_book in RawBook.objects.filter(text=None, skipped=False).order_by("gutenberg_id"):
            book_scraper = BookScraper(raw_book=raw_book)
            book_scraper.get_metadata()
            book_scraper.get_text()

        for raw_book in RawBook.objects.filter(book=None, skipped=False).order_by("gutenberg_id"):
            book_cleaner = BookCleaner(raw_book=raw_book)
            book_cleaner.parse()
            print(raw_book.gutenberg_id, "page parsed.")
            book_cleaner.chunk()
            print(raw_book.gutenberg_id, "page chunked.")
            book_cleaner.clean()
            print(raw_book.gutenberg_id, "book cleaned.")
