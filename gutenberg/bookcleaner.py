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
        self.chunk_count = 0

    def parse(self, force=False):

        if force:
            self.html_stylesheet = None
            Tag.objects.filter(raw_book=self.raw_book.id).delete()
            self.raw_book.save(update_fields=["html_stylesheet"])

        elif self.raw_book.body and self.raw_book.html_stylesheet:
            return

        html_element = BeautifulSoup(self.raw_book.text, "html.parser").html
        html_element.find(attrs={"id": "pg-footer"}).decompose()
        html_element.find(attrs={"id": "pg-header"}).decompose()

        self.raw_book.body = Tag.objects.create(
            rel_i=0,
            raw_book=self.raw_book,
            name="div",
            contents_text=html_element.body.get_text(strip=True, separator=" ") or None,
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
                    contents_text=element.get_text(strip=True, separator=" ") or None,
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
        else:
            raise Exception(f"Tag-Element mismatch. Elements={element_count}; Tags={tag_count}")

    def chunk(self):
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
        texts = {text.rel_i: text for text in tag.texts.all()}
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

    def _rec_get_chunks(self, tag, num_words=None):
        num_words = num_words or len(
            [word for word in " ".join(tag.contents_text.split("\r\n")).split() if word]
        )
        num_chunks = num_words // Chunk.CHUNK_SIZE
        subtags = list(tag.tags.exclude(contents_text=None))

        if num_chunks <= 1:
            print(tag.id, "Tiny chunk created.")
            self._create_chunk([tag])
        else:
            if subtags:
                print(
                    tag.id,
                    f"Combine subtags ({len(subtags)}) if consecutive subtags are too small.",
                )
                # Combine subtags if consecutive subtags are too small
                group_num_words = 0
                subtag_group = []

                for subtag in subtags:
                    subtag_num_words = len(
                        [
                            word
                            for word in " ".join(subtag.contents_text.split("\r\n")).split()
                            if word
                        ]
                    )
                    ratio = 1
                    if round(subtag_num_words / Chunk.CHUNK_SIZE, 2) > ratio:
                        print(
                            tag.id,
                            subtag.id,
                            f"Subtag too big ({subtag_num_words}). Intiating recursion.",
                        )
                        if subtag_group:
                            self._create_chunk(subtag_group)
                            subtag_group = []
                            group_num_words = 0

                        self.executor_futures.append(
                            self.executor.submit(self._rec_get_chunks, subtag, subtag_num_words)
                        )

                    elif round((group_num_words + subtag_num_words) / Chunk.CHUNK_SIZE, 2) > ratio:
                        print(
                            tag.id,
                            subtag.id,
                            f"Subtag too big ({subtag_num_words}) for existing group {group_num_words}. Starting new group.",
                        )
                        self._create_chunk(subtag_group)
                        subtag_group = [subtag]
                        group_num_words = subtag_num_words
                    else:
                        print(
                            tag.id,
                            subtag.id,
                            f"Subtag ({subtag_num_words}) added to existing group {group_num_words}.",
                        )
                        group_num_words += subtag_num_words
                        subtag_group.append(subtag)

                if subtag_group:
                    self._create_chunk(subtag_group)
            else:
                print(
                    tag.id,
                    f"No subtags found ({len(subtags)}). Create spans and then break into chunks",
                )
                # create spans and then break into chunks
                texts = list(tag.texts.all())
                if len(texts) != 1:
                    print([t.value for t in texts])
                    raise Exception(len(texts))

                lines = texts[0].value.split("\r\n")
                lines_per_chunk = len(lines) // num_chunks
                for i in range(num_chunks):
                    span_text = "\r\n".join(lines[i * lines_per_chunk : (i + 1) * lines_per_chunk])

                    new_tag = tag.tags.create(
                        rel_i=i,
                        book_id=tag.book_id,
                        name="span",
                        contents_text=span_text.strip(),
                    )

                    new_tag.texts.create(book_id=tag.book_id, rel_i=0, value=span_text)

                    texts[0].replaced = True
                    texts[0].save(update_fields=["replaced"])
                    self._create_chunk([new_tag])

    def _create_chunk(self, tags):
        text = []
        for tag in tags:
            if tag.chunk:
                raise Exception("Tag may not belong to more than one chunk.")
            for word in " ".join(tag.contents_text.split("\r\n")).split():
                if word:
                    text.append(word)
        gutenberg_id = int(tags[0].raw_book.gutenberg_id)
        chunk = Chunk.objects.create(
            book_gutenberg_id=gutenberg_id, text=" ".join(text), rel_i=self.chunk_count
        )
        self.chunk_count += 1
        chunk.tags.add(*tags)

        print(f"Chunk (Sized {len(text)}) created for tag group (sized {len(tags)})")
