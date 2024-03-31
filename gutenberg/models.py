from django.db import models

BASE_URL = "https://gutenberg.org"


class BookList(models.Model):
    MAX_BOOK_IDS_PER_PAGE = 25
    gutenberg_id = models.IntegerField(unique=True, db_index=True)

    @property
    def url(self):
        raise NotImplementedError

    class Meta:
        abstract = True


class Subject(BookList):
    label = models.TextField()

    @property
    def url(self):
        return f"{BASE_URL}/ebooks/subject/{self.gutenberg_id}/"


class Author(BookList):
    name = models.TextField()
    life_span = models.TextField()

    @property
    def url(self):
        return f"{BASE_URL}/ebooks/author/{self.gutenberg_id}/"


class RawBook(models.Model):
    SKIPPED_CHOICES = {
        "NO_AUTHOR": "Author Missing",
        "FORMAT": "Not a text",
        "LANG": "Not English",
        "DUPLICATE": "Already Exists",
    }

    date_created = models.DateTimeField(auto_now_add=True)
    gutenberg_id = models.IntegerField(unique=True, db_index=True)

    metadata_retrieved_date = models.DateTimeField(null=True)
    metadata = models.JSONField(null=True)

    text_retrieved_date = models.DateTimeField(null=True)
    text = models.TextField(null=True)

    authors = models.ManyToManyField(Author, related_name="raw_books")
    subjects = models.ManyToManyField(Subject, related_name="raw_books")

    skipped = models.BooleanField(default=False)
    skipped_reason = models.CharField(
        null=True, default=None, choices=SKIPPED_CHOICES, max_length=15
    )

    body = models.ForeignKey("Tag", on_delete=models.SET_NULL, null=True, related_name="+")
    html_stylesheet = models.TextField(null=True)

    @property
    def metadata_url(self):
        return f"{BASE_URL}/ebooks/{self.gutenberg_id}/"

    @property
    def text_url(self):
        return f"{BASE_URL}/cache/epub/{self.gutenberg_id}/pg{self.gutenberg_id}-images.html"

    def skip(self, reason):
        self.skipped = True
        self.skipped_reason = reason
        self.save(update_fields=["skipped", "skipped_reason"])

    def __str__(self):
        return f"Raw Book ({self.gutenberg_id})"


class HTMLContent(models.Model):
    raw_book = models.ForeignKey(RawBook, on_delete=models.CASCADE, related_name="+")
    rel_i = models.IntegerField()

    class Meta:
        abstract = True


class Tag(HTMLContent):
    parent = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="tags", null=True)
    name = models.CharField(max_length=15)
    source_i = models.IntegerField(null=True)  # if Null, injected.
    attrs = models.JSONField(null=True)
    contents_text = models.TextField(null=True, default=None)
    chunk = models.ForeignKey(
        "Chunk", related_name="tags", null=True, default=None, on_delete=models.SET_NULL
    )


class Text(HTMLContent):
    parent = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="texts")
    value = models.TextField()
    replaced = models.BooleanField(default=False)


class Book(models.Model):
    raw_book = models.OneToOneField(RawBook, on_delete=models.CASCADE)
    gutenberg_id = models.IntegerField(unique=True, db_index=True)
    title = models.TextField(null=True)
    author = models.TextField()
    html_map = models.JSONField(null=True)
    html_stylesheet = models.TextField(null=True)

    def __str__(self):
        return f"Book {self.gutenberg_id}: {self.title}"


class Chunk(models.Model):
    CHUNK_SIZE = 250  # words
    book_gutenberg_id = models.IntegerField()
    text = models.TextField()
    rel_i = models.IntegerField()
