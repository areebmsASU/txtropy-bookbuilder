# Generated by Django 5.0.2 on 2024-04-16 21:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gutenberg', '0004_remove_chunk_book_gutenberg_id_remove_chunk_rel_i'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='last_modified',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='rawbook',
            name='date_chunked',
            field=models.DateTimeField(null=True),
        ),
    ]
