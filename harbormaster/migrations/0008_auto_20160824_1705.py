# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-24 17:05
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('harbormaster', '0007_auto_20160824_1507'),
    ]

    operations = [
        migrations.RenameField(
            model_name='contact',
            old_name='speed',
            new_name='max_speed',
        ),
    ]
