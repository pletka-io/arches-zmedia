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


# One string value, the same on every run: English first, then by language,
# tile sortorder and tileid; empty values skipped. (The name node has many: see below.)
_FIRST_VALUE = """(SELECT v->>'value' FROM tiles t, jsonb_each(t.tiledata->%({key})s) x(l, v)
         WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.tiledata ? %({key})s
           AND COALESCE(v->>'value', '') <> ''
         ORDER BY (x.l = 'en') DESC, x.l, t.sortorder, t.tileid LIMIT 1)"""

_DO_SQL = f"""
SELECT ri.resourceinstanceid::text,
       {_FIRST_VALUE.format(key="ident")},
       ARRAY(SELECT DISTINCT v->>'value' FROM tiles t, jsonb_each(t.tiledata->%(name)s) x(l, v)
              WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.tiledata ? %(name)s
                AND COALESCE(v->>'value', '') <> '' ORDER BY 1),
       (SELECT COALESCE(jsonb_object_agg(t.tileid::text, t.tiledata->%(image)s), '{{}}'::jsonb)
          FROM tiles t WHERE t.resourceinstanceid = ri.resourceinstanceid AND t.nodegroupid = %(image_ng)s::uuid)
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
                                "image": str(image.nodeid), "image_ng": str(image.nodegroup_id),
                                "graph": str(image.graph_id)})
            # has_image: an image tile we did not write, or ours edited since (our own unedited tile does not count)
            dos = [link.Do(rid, ident, tuple(names or ()), link.has_foreign_image(rid, tiles, cfg["ORG"], spec),
                           link.has_our_tile(rid, tiles))
                   for rid, ident, names, tiles in c.fetchall()]
        pairs, unmatched = link.match(dos, inventory, pattern, partial=bool(since))
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
        cleared = sum(1 for _, row in pairs if row["status"] == "deleted")
        self.stdout.write(f"matched {len(pairs) - cleared}; cleared (file deleted) {cleared}; "
                          f"digital objects unmatched {do_unmatched}; files unmatched {len(unmatched) - do_unmatched}; "
                          f"cursor {cursor}")
