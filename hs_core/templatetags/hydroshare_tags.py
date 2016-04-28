from __future__ import absolute_import, division, unicode_literals
from future.builtins import int, open, str

from hashlib import md5
from json import loads
import os
#from dublincore.models import AbstractQualifiedDublinCoreTerm
import re

try:
    from urllib.request import urlopen
    from urllib.parse import urlencode, quote, unquote
except ImportError:
    from urllib import urlopen, urlencode, quote, unquote

from django.contrib import admin
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.sites.models import Site
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse, resolve, NoReverseMatch
from django.db.models import Model
from django.template.base import (Context, Node, TextNode, Template,
    TemplateSyntaxError, TOKEN_TEXT, TOKEN_VAR, TOKEN_COMMENT, TOKEN_BLOCK)
from django.template.defaultfilters import escape
from django.template.loader import get_template
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.text import capfirst

# Try to import PIL in either of the two ways it can end up installed.
try:
    from PIL import Image, ImageFile, ImageOps
except ImportError:
    import Image
    import ImageFile
    import ImageOps

from mezzanine.conf import settings
from mezzanine.core.fields import RichTextField
from mezzanine.core.forms import get_edit_form
from mezzanine.utils.cache import nevercache_token, cache_installed
from mezzanine.utils.html import decode_entities
from mezzanine.utils.importing import import_dotted_path
from mezzanine.utils.sites import current_site_id, has_site_permission
from mezzanine.utils.urls import admin_url
from mezzanine.utils.views import is_editable
from mezzanine import template


register = template.Library()

@register.filter
def user_permission(content, arg):
    user_pk = arg
    permission = "None"
    res_obj = content.get_content_model()
    if res_obj.raccess.owners.filter(pk=user_pk).exists():
        permission = "Owner"
    elif res_obj.raccess.edit_users.filter(pk=user_pk).exists():
        permission = "Edit"
    elif res_obj.raccess.view_users.filter(pk=user_pk).exists():
        permission = "View"

    if permission == "None":
        if res_obj.raccess.published or res_obj.raccess.discoverable or res_obj.raccess.public:
            permission = "Open Access"
    return permission

@register.filter
def resource_type(content):
    return content.get_content_model()._meta.verbose_name

@register.filter
def contact(content):
    """
    Takes a value edited via the WYSIWYG editor, and passes it through
    each of the functions specified by the RICHTEXT_FILTERS setting.
    """
    if not content:
        return ''

    if not content.is_authenticated():
        content = "Anonymous"
    elif content.first_name:
        content = """<a href='/user/{uid}/'>{fn} {ln}<a>""".format(fn=content.first_name, ln=content.last_name, uid=content.pk)
    else:
        content = """<a href='/user/{uid}/'>{un}<a>""".format(uid=content.pk, un=content.username)

    return content

@register.filter
def best_name(content):
    """
    Takes a value edited via the WYSIWYG editor, and passes it through
    each of the functions specified by the RICHTEXT_FILTERS setting.
    """

    if not content.is_authenticated():
        content = "Anonymous"
    elif content.first_name:
        content = """{fn} {ln}""".format(fn=content.first_name, ln=content.last_name, un=content.username)
    else:
        content = content.username

    return content

@register.filter
def clean_pagination_url(content):
    if "?q=" not in content:
        content += "?q="
    if "&page=" not in content:
        return content
    else:
        clean_content = ''
        parsed_content = content.split("&")
        for token in parsed_content:
            if "page=" not in token:
                clean_content += token + '&'
        clean_content = clean_content[:-1]
        return clean_content

@register.filter
def to_int(value):
    return int(value)