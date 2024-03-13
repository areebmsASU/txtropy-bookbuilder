# Generated by Django 5.0.2 on 2024-03-03 19:40

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gutenberg_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.TextField()),
                ('life_span', models.TextField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Chunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_gutenberg_id', models.IntegerField()),
                ('text', models.TextField()),
                ('rel_i', models.IntegerField(default=None, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gutenberg_id', models.IntegerField(db_index=True, unique=True)),
                ('label', models.TextField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RawBook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('gutenberg_id', models.IntegerField(db_index=True, unique=True)),
                ('metadata_retrieved_date', models.DateTimeField(null=True)),
                ('metadata', models.JSONField(null=True)),
                ('text_retrieved_date', models.DateTimeField(null=True)),
                ('text', models.TextField(null=True)),
                ('skipped', models.BooleanField(default=False)),
                ('skipped_reason', models.CharField(choices=[('NO_AUTHOR', 'Author Missing'), ('FORMAT', 'Not a text'), ('LANG', 'Not English'), ('DUPLICATE', 'Already Exists')], default=None, max_length=15, null=True)),
                ('html_stylesheet', models.TextField(null=True)),
                ('authors', models.ManyToManyField(related_name='raw_books', to='gutenberg.author')),
                ('subjects', models.ManyToManyField(related_name='raw_books', to='gutenberg.subject')),
            ],
        ),
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gutenberg_id', models.IntegerField(db_index=True, unique=True)),
                ('title', models.TextField(null=True)),
                ('author', models.TextField()),
                ('html_map', models.JSONField(null=True)),
                ('html_stylesheet', models.TextField(null=True)),
                ('raw_book', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='gutenberg.rawbook')),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rel_i', models.IntegerField()),
                ('name', models.CharField(max_length=15)),
                ('source_i', models.IntegerField(null=True)),
                ('attrs', models.JSONField(null=True)),
                ('contents_text', models.TextField(default=None, null=True)),
                ('chunk', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tags', to='gutenberg.chunk')),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='gutenberg.tag')),
                ('raw_book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='gutenberg.rawbook')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='rawbook',
            name='body',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='gutenberg.tag'),
        ),
        migrations.CreateModel(
            name='Text',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rel_i', models.IntegerField()),
                ('value', models.TextField()),
                ('replaced', models.BooleanField(default=False)),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='texts', to='gutenberg.tag')),
                ('raw_book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='gutenberg.rawbook')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
