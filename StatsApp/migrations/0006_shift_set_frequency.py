# Generated by Django 4.2.6 on 2025-07-24 10:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('StatsApp', '0005_shift_auto_messages_shift_auto_speed'),
    ]

    operations = [
        migrations.AddField(
            model_name='shift',
            name='set_frequency',
            field=models.FloatField(default=0.0, verbose_name='Set Frequency (msg/min)'),
        ),
    ]
