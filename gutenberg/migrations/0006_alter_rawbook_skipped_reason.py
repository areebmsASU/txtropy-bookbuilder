# Generated by Django 5.0.2 on 2024-04-17 04:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gutenberg', '0005_book_last_modified_rawbook_date_chunked'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rawbook',
            name='skipped_reason',
            field=models.CharField(choices=[('NO_AUTHOR', 'Author Missing'), ('FORMAT', 'Not a text'), ('LANG', 'Not English'), ('DUPLICATE', 'Already Exists'), ('CHUNKS', 'Chunking Edge Case')], default=None, max_length=15, null=True),
        ),
    ]
