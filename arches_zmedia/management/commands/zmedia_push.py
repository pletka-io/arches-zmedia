from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand

from arches_zmedia import naming, sftp
from arches_zmedia.push import plan_push
from arches_zmedia.storage import remote_path


class Command(BaseCommand):
    help = "Upload legacy uploadedfiles/ files zmedia lacks, over the instance's SFTP account."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run=False, **opts):
        from arches.app.models.models import File

        cfg = settings.ZMEDIA
        rows = list(
            File.objects.filter(path__startswith=naming.LEGACY_DIR).values_list(
                "path", "tile__resourceinstance__graph__slug"
            )
        )
        local = FileSystemStorage()  # MEDIA_ROOT: where legacy names live on disk
        with sftp.connect(cfg) as s:
            specs = {spec or naming.UNLINKED for _, spec in rows}
            remote = {spec: sftp.listdir(s, f"/{cfg['ORG']}/{spec}") for spec in specs}
            todo, missing = plan_push(rows, remote, local.path)
            self.stdout.write(f"{len(rows)} rows, {len(todo)} to upload, {len(missing)} missing on disk")
            for name in missing[:20]:
                self.stdout.write(f"missing: {name}")
            for path, spec, rel in todo:
                target = remote_path(cfg, spec, rel)
                self.stdout.write(("would upload " if dry_run else "upload ") + target)
                if not dry_run:
                    sftp.ensure_dir(s, f"/{cfg['ORG']}/{spec}")
                    s.put(path, target)
