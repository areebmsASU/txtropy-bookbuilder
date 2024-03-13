from collections import defaultdict
from time import sleep

from bs4 import BeautifulSoup
from django.utils import timezone
import requests as r

from gutenberg.models import Subject, Author


class BookScraper:
    def __init__(self, raw_book) -> None:
        self.raw_book = raw_book

    def get_raw_metadata(self, force_refresh=False):
        if self.raw_book.metadata and not force_refresh:
            return False

        metadata = defaultdict(list)
        for tr in (
            BeautifulSoup(r.get(self.raw_book.metadata_url).content, "html.parser")
            .find("table", class_="bibrec")
            .find_all("tr")
        ):
            key = tr.find("th")
            if key is not None:
                value = tr.find("td")
                a = value.find("a")
                href = a["href"] if a else None
                key = (
                    key.text.lower()
                    .replace(" ", "-")
                    .replace(".", "")
                    .replace("-", "_")
                )
                for line in tr.find("td").get_text(separator="\n").split("\n"):
                    if line:
                        metadata[key].append(line)
                if href:
                    metadata[key + "_link"].append(href)

        self.raw_book.metadata = dict(metadata)
        self.raw_book.metadata_retrieved_date = timezone.now()

        update_fields = ["metadata", "metadata_retrieved_date"]
        if self.raw_book.skipped:
            self.raw_book.skipped = False
            self.raw_book.skipped_reason = None
            update_fields.extend(["skipped", "skipped_reason"])

        self.raw_book.save(update_fields=update_fields)
        return True

    def add_authors(self):
        authors = self.raw_book.metadata.get("author", [])
        for i in range(len(authors)):
            life_span = authors[i].split(", ")[-1]
            if "-" not in life_span:
                continue
            name = authors[i].replace(", " + life_span, "")
            gutenberg_id = self.raw_book.metadata["author_link"][i].split("/")[-1]
            author, _ = Author.objects.get_or_create(
                name=name, gutenberg_id=gutenberg_id, life_span=life_span
            )
            self.raw_book.authors.add(author)

    def add_subjects(self):
        subjects = self.raw_book.metadata.get("subject", [])
        for i in range(len(subjects)):
            subject, _ = Subject.objects.get_or_create(
                label=subjects[i],
                gutenberg_id=self.raw_book.metadata["subject_link"][i].split("/")[-1],
            )
            self.raw_book.subjects.add(subject)

    def get_metadata(self, force_refresh=False):
        new = self.get_raw_metadata(force_refresh)
        if new:
            self.add_authors()
            self.add_subjects()
            sleep(1)

    def get_text(self):
        if self.raw_book.authors.count() == 0:
            self.raw_book.skip("NO_AUTHOR")
        elif "English" not in self.raw_book.metadata["language"]:
            self.raw_book.skip("LANG")
        elif self.raw_book.metadata["category"] != ["Text"]:
            self.raw_book.skip("FORMAT")
        else:
            self.raw_book.text = r.get(self.raw_book.text_url).text
            self.raw_book.text_retrieved_date = timezone.now()
            self.raw_book.save(update_fields=["text", "text_retrieved_date"])
            sleep(1)


class BookListScraper:
    def __init__(self, book_list) -> None:
        self.book_list = book_list

    def get_books(self):
        created_book_ids = []
        page_book_ids = []
        num_book_ids = -1
        while num_book_ids == -1 or (
            len(page_book_ids) != num_book_ids
            and len(page_book_ids) % self.book_list.MAX_BOOK_IDS_PER_PAGE == 0
        ):
            sleep(1)
            num_book_ids = len(page_book_ids)
            book_list_page = r.get(
                self.book_list.url + f"?start_index={num_book_ids+1}"
            )
            for link in BeautifulSoup(book_list_page.text, "html.parser").find_all("a"):
                if (
                    "ebooks" in link.get("href", "")
                    and link["href"].split("/")[2].isdigit()
                    and link["href"].split("/")[2] not in page_book_ids
                ):
                    book, created = self.book_list.raw_books.get_or_create(
                        gutenberg_id=link["href"].split("/")[2]
                    )
                    if created:
                        created_book_ids.append(book.id)
                    page_book_ids.append(link["href"].split("/")[2])
        return created_book_ids
