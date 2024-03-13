from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag as bs4Tag, Comment

from gutenberg.models import Text, Tag, Chunk, Book

from concurrent.futures import ThreadPoolExecutor, wait


class BookCleaner:
    def __init__(self, raw_book) -> None:
        self.raw_book = raw_book
        self.executor = ThreadPoolExecutor()
        self.executor_futures = []
        self.chunk_count = 0

    def parse(self):
        if self.raw_book.body and self.raw_book.html_stylesheet:
            return

        html_element = BeautifulSoup(self.raw_book.text, "html.parser").html
        self.raw_book.body = Tag.objects.create(
            rel_i=0,
            raw_book=self.raw_book,
            name="div",
            contents_text=html_element.body.get_text(strip=True, separator=" ") or None,
        )

        for rel_i, child in enumerate(html_element.body.children):
            self._rec_populate_subcontents(self.raw_book.body, child, rel_i)

        wait(self.executor_futures)

        self.raw_book.html_stylesheet = "\r\n".join(
            [s.text for s in html_element.head.findAll("style")]
        )

        self.executor.shutdown()
        self.executor = ThreadPoolExecutor()

        self.raw_book.save(update_fields=["body", "html_stylesheet"])

        print(
            len(html_element.body.find_all()) - 1,
            Tag.objects.filter(raw_book__gutenberg_id=3300).count(),
        )

        # print(html_element.body.find_all()[0].name)
        # print(html_element.body.find_all()[0])

        assert (
            len(html_element.body.find_all())
            == Tag.objects.filter(raw_book__gutenberg_id=3300).count()
        )

    def chunk(self):
        self._rec_get_chunks(self.raw_book.body)
        wait(self.executor_futures)
        self.executor.shutdown()
        self.executor = ThreadPoolExecutor()

    def clean(self):
        html_map_future = self.executor.submit(
            self._rec_generate_htmlmap, self.raw_book.body
        )
        book = Book.objects.create(
            gutenberg_id=self.raw_book.gutenberg_id,
            raw_book=self.raw_book,
            title=self.raw_book.metadata["title"][0].strip(),
            author=self.raw_book.authors.all().first().name,
            html_stylesheet=self.raw_book.html_stylesheet,
        )

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

    def _rec_populate_subcontents(self, parent_tag, element, rel_i):
        if type(element) is NavigableString:
            if not str(element.string).replace("\n", "").strip():
                return
            Text.objects.create(
                raw_book_id=parent_tag.raw_book_id,
                rel_i=rel_i,
                parent=parent_tag,
                value=element.string,
            )
            return

        if type(element) is Comment:
            return

        if type(element) is not bs4Tag:
            raise Exception(str(type(element)))

        tag = Tag.objects.create(
            parent=parent_tag,
            rel_i=rel_i,
            source_i=element.sourceline,
            raw_book_id=parent_tag.raw_book_id,
            name=element.name,
            attrs=element.attrs or None,
            contents_text=element.get_text(strip=True, separator=" ") or None,
        )

        for rel_i, content in enumerate(element.contents):
            self.executor_futures.append(
                self.executor.submit(
                    self._rec_populate_subcontents,
                    parent_tag=tag,
                    element=content,
                    rel_i=rel_i,
                )
            )

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
                            for word in " ".join(
                                subtag.contents_text.split("\r\n")
                            ).split()
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
                            self.executor.submit(
                                self._rec_get_chunks, subtag, subtag_num_words
                            )
                        )

                    elif (
                        round(
                            (group_num_words + subtag_num_words) / Chunk.CHUNK_SIZE, 2
                        )
                        > ratio
                    ):
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
                    span_text = "\r\n".join(
                        lines[i * lines_per_chunk : (i + 1) * lines_per_chunk]
                    )

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
