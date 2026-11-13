import os
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from arches_zmedia import link


def _inventory(cfg, spec, since):
    url = f"{cfg['INVENTORY_URL'].rstrip('/')}/{cfg['ORG']}/{spec}" + (f"?since={since}" if since else "")
    token = open(cfg["INVENTORY_TOKEN_FILE"]).read().strip()
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        raise CommandError(f"inventory {url}: HTTP {e.code}") from e
    with resp:
        return link.read_inventory(resp), resp.headers.get("X-Zmedia-Cursor", "")


_DO_SQL = """
SELECT ri.resourceinstanceid::text,
       (SELECT v->>'value' FROM tiles t, jsonb_each(t.tiledata->%(ident)s) x(l, v)
         WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.tiledata ? %(ident)s LIMIT 1),
       (SELECT v->>'value' FROM tiles t, jsonb_each(t.tiledata->%(name)s) x(l, v)
         WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.tiledata ? %(name)s LIMIT 1),
       EXISTS (SELECT 1 FROM tiles t WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.nodegroupid = %(image_ng)s::uuid)
  FROM resource_instances ri
 WHERE ri.graphid = %(graph)s::uuid
 ORDER BY 1
"""


class Command(BaseCommand):
    help = "Link Digital Objects to their files on zmedia: write loader JSONL (load with delta_sync('tile'))."

    def add_arguments(self, parser):
        parser.add_argument("spec")
        parser.add_argument("--pattern", required=True)
        parser.add_argument("--identifier-node", required=True)
        parser.add_argument("--name-node", required=True)
        parser.add_argument("--image-node", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--since")

    def handle(self, *args, spec, pattern, identifier_node, name_node, image_node, out, since=None, **opts):
        from arches.app.models.models import Node

        cfg = settings.ZMEDIA
        if not cfg.get("INVENTORY_URL"):
            raise CommandError("ZMEDIA['INVENTORY_URL'] is not set")
        nodes = {}
        for alias in (identifier_node, name_node, image_node):
            node = Node.objects.filter(graph__slug=spec, graph__source_identifier=None, alias=alias).first()
            if node is None:
                raise CommandError(f"graph {spec} has no node {alias}")
            nodes[alias] = node
        image = nodes[image_node]
        inventory, cursor = _inventory(cfg, spec, since)  # fails before anything is written
        with connection.cursor() as c:
            c.execute(_DO_SQL, {"ident": str(nodes[identifier_node].nodeid), "name": str(nodes[name_node].nodeid),
                                "image_ng": str(image.nodegroup_id), "graph": str(image.graph_id)})
            dos = [link.Do(*row) for row in c.fetchall()]
        if since:
            # an incremental run only re-links Digital Objects whose file changed; their earlier
            # image tile is ours, so it does not count as "has an image already"
            dos = [d._replace(has_image=False) for d in dos]
        pairs, unmatched = link.match(dos, inventory, pattern)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "link.jsonl"), "w") as f:
            for do, row in pairs:
                value = None if row["status"] == "deleted" else link.file_value(cfg["ORG"], spec, row)
                f.write(link.image_line(do, str(image.graph_id), str(image.nodegroup_id), str(image.nodeid), value) + "\n")
        with open(os.path.join(out, "unmatched.tsv"), "w") as f:
            f.write("kind\tkey\treason\n")
            f.writelines(f"{k}\t{key}\t{r}\n" for k, key, r in unmatched)
        with open(os.path.join(out, "cursor"), "w") as f:
            f.write(cursor)
        do_unmatched = sum(1 for u in unmatched if u[0] == "do")
        self.stdout.write(f"matched {len(pairs)}; digital objects unmatched {do_unmatched}; files unmatched {len(unmatched) - do_unmatched}; cursor {cursor}")
