"""Arches' FileView, with ?thumbnail=true / ?size=<n> sent to a zmedia thumbnail (spec §4).
Arches' permission checks run first, unchanged: only its redirect is replaced."""
from django.conf import settings
from django.shortcuts import redirect
from arches.app.models.models import File
from arches.app.views.file import FileView as ArchesFileView

from .derivatives import redirect_target


class FileView(ArchesFileView):
    def get(self, request, fileid=None):
        response = super().get(request, fileid=fileid)
        if response.status_code != 302:
            return response
        f = File.objects.filter(pk=fileid).first()
        if f is None:
            return response
        target = redirect_target(f.path.name, f.path.storage, request.GET, settings.ZMEDIA)
        return redirect(target) if target else response
