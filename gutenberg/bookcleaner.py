from concurrent.futures import ThreadPoolExecutor, wait

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag as bs4Tag, Comment
from django.db.transaction import atomic

from gutenberg.models import Text, Tag, Chunk, Book


class BookCleaner:
    def __init__(self, raw_book) -> None:
        self.raw_book = raw_book
        self.executor = ThreadPoolExecutor()
        self.executor_futures = []
        self.changed = False

    def refresh(self):
        self.raw_book.html_stylesheet = None
        Tag.objects.filter(raw_book=self.raw_book.id).delete()
        self.raw_book.save(update_fields=["html_stylesheet"])
        self.changed = True

    def parse(self):
        if (not self.changed) and hasattr(self.raw_book, "body") and self.raw_book.html_stylesheet:
            return

        html_element = BeautifulSoup(self.raw_book.text, "html.parser").html
        html_element.find(attrs={"id": "pg-footer"}).decompose()
        html_element.find(attrs={"id": "pg-header"}).decompose()

        self.raw_book.body = Tag.objects.create(
            rel_i=0,
            raw_book=self.raw_book,
            name="div",
            contents_text=self._get_contents_text(html_element.body),
        )

        tag_by_id = {id(html_element.body): self.raw_book.body}
        elements = list(html_element.body.find_all())
        for element in elements:
            with atomic():
                tag_by_id[id(element)] = Tag.objects.create(
                    raw_book_id=self.raw_book.id,
                    parent=tag_by_id[id(element.parent)],
                    rel_i=element.parent.contents.index(element),
                    source_i=element.sourceline,
                    name=element.name,
                    attrs=element.attrs or None,
                    contents_text=self._get_contents_text(element),
                )
                for rel_i, child in enumerate(element.contents):
                    if type(child) is NavigableString:
                        Text.objects.create(
                            raw_book_id=self.raw_book.id,
                            parent=tag_by_id[id(element)],
                            rel_i=rel_i,
                            value=child.string,
                        )

        self.raw_book.html_stylesheet = "\r\n".join(
            [s.text for s in html_element.head.findAll("style")]
        )

        # Checks:
        element_count = len(html_element.body.find_all()) + 1  # + 1 for body itself
        tag_count = Tag.objects.filter(raw_book=self.raw_book.id).count()
        if element_count == tag_count:
            self.raw_book.save(update_fields=["body", "html_stylesheet"])
            self.changed = True
        else:
            raise Exception(f"Tag-Element mismatch. Elements={element_count}; Tags={tag_count}")

    def chunk(self):
        if (
            not self.changed
            and Chunk.objects.filter(book_gutenberg_id=self.raw_book.gutenberg_id).exists()
        ):
            return
        Chunk.objects.filter(book_gutenberg_id=self.raw_book.gutenberg_id).delete()
        self._rec_get_chunks(self.raw_book.body)
        wait(self.executor_futures)
        self.executor.shutdown()
        self.executor = ThreadPoolExecutor()

    def clean(self):
        html_map_future = self.executor.submit(self._rec_generate_htmlmap, self.raw_book.body)
        book = Book.objects.update_or_create(
            gutenberg_id=self.raw_book.gutenberg_id,
            raw_book=self.raw_book,
            title=self.raw_book.metadata["title"][0].strip(),
            author=self.raw_book.authors.all().first().name,
            html_stylesheet=self.raw_book.html_stylesheet,
        )[0]

        wait([html_map_future])
        self.executor.shutdown()

        book.html_map = html_map_future.result()
        book.save(update_fields=["html_map", "html_stylesheet"])
        return book

    @staticmethod
    def _rec_generate_htmlmap(tag):
        data = {"tag": tag.name}

        if tag.attrs or tag.chunk:
            data["attrs"] = {}

            if tag.chunk:
                data["attrs"]["data-txtrpy-id"] = tag.chunk_id

            if tag.attrs:
                for k, v in tag.attrs.items():
                    if type(v) is list:
                        v = " ".join(v)
                    data["attrs"][k] = v

        tags = {_tag.rel_i: _tag for _tag in tag.tags.all()}
        texts = {text.rel_i: text for text in tag.texts.filter(replaced=False)}
        if tags or texts:
            data["contents"] = []
            for i in range(max(list(tags) + list(texts)) + 1):
                if i in tags and i in texts:
                    raise Exception("Malformed htmlmap")
                elif i in tags:
                    data["contents"].append(BookCleaner._rec_generate_htmlmap(tags[i]))
                elif i in texts:
                    data["contents"].append(texts[i].value)
        return data

    @staticmethod
    def _get_contents_text(element):
        return (
            " ".join(
                [
                    word
                    for word in " ".join(
                        element.get_text(strip=True, separator=" ").split("\r\n")
                    ).split()
                    if word
                ]
            )
            or None
        )

    def _rec_get_chunks(self, tag):

        subtags = list(tag.tags.exclude(contents_text=None))

        if len(tag.contents_text.split()) // Chunk.CHUNK_SIZE < 1:
            print(tag.id, f"Tiny chunk created for '{tag.contents_text}")
            self._create_chunk([tag])
        elif len(tag.contents_text.split()) // Chunk.CHUNK_SIZE == 1:
            self._create_chunk([tag])

        elif subtags:
            # Combine subtags if consecutive subtags are too small
            group_num_words = 0
            subtag_group = []

            for subtag in subtags:
                num_words = len(subtag.contents_text.split())
                if (num_words / Chunk.CHUNK_SIZE) > 1:
                    if subtag_group:
                        self._create_chunk(subtag_group)
                        subtag_group = []
                        group_num_words = 0

                    self.executor_futures.append(self.executor.submit(self._rec_get_chunks, subtag))

                elif ((group_num_words + num_words) / Chunk.CHUNK_SIZE) > 1:
                    self._create_chunk(subtag_group)
                    subtag_group = [subtag]
                    group_num_words = num_words
                else:
                    group_num_words += num_words
                    subtag_group.append(subtag)

            if subtag_group:
                self._create_chunk(subtag_group)
        else:
            # create spans and then break into chunks
            text = list(tag.texts.all())
            if len(text) != 1:
                print([t.value for t in text])
                raise Exception("Tag has more than one text.")

            text = text.pop()

            lines = text.value.split("\r\n")
            chunks_to_create = 1 + (len(tag.contents_text.split()) // Chunk.CHUNK_SIZE)
            lines_per_chunk = len(lines) // chunks_to_create

            for i in range(chunks_to_create):
                span_text = "\r\n".join(lines[i * lines_per_chunk : (i + 1) * lines_per_chunk])

                new_tag = tag.tags.create(
                    rel_i=i,
                    raw_book_id=self.raw_book.id,
                    name="span",
                    contents_text=span_text.strip(),
                )

                new_tag.texts.create(raw_book_id=self.raw_book.id, rel_i=0, value=" " + span_text)

                text.replaced = True
                text.save(update_fields=["replaced"])

    def _create_chunk(self, tags):
        text = []
        for tag in tags:
            if tag.chunk:
                raise Exception("Tag may not belong to more than one chunk.")
            text.append(tag.contents_text)
        self.raw_book.chunks.create(text=" ".join(text))
        chunk.tags.add(*tags)
        return chunk
