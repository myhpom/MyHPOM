# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myhpom', '0017_ad_thumbnail'),
    ]

    operations = [
        migrations.AlterField(
            model_name='advancedirective',
            name='thumbnail',
            field=models.FileField(help_text=b"The first-page thumbnail image of the user's Advance Directive.", null=True, upload_to=b'myhpom/advance_directives', blank=True),
        ),
    ]
