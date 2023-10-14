# Generated by Django 4.2.5 on 2023-10-13 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0006_room_gender'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='room',
            name='gender',
        ),
        migrations.AddField(
            model_name='room',
            name='ChatGPT',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='room',
            name='Claude2',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='room',
            name='LLaMA',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='room',
            name='PaLM2',
            field=models.BooleanField(default=False),
        ),
    ]