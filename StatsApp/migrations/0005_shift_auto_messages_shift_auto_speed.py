# Generated by Django 4.2.6 on 2025-07-24 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('StatsApp', '0004_shiftlog_delete_useractionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='shift',
            name='auto_messages',
            field=models.IntegerField(default=0, verbose_name='Auto Messages'),
        ),
        migrations.AddField(
            model_name='shift',
            name='auto_speed',
            field=models.FloatField(default=0.0, verbose_name='Auto Speed (msg/min)'),
        ),
    ]
