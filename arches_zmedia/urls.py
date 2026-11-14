from django.conf import settings
from django.urls import re_path

from .views import FileView

uuid_regex = settings.UUID_REGEX

urlpatterns = [
    re_path(r"^files/(?P<fileid>%s)$" % uuid_regex, FileView.as_view(), name="zmedia_file_access"),
]
