# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools.safe_eval import safe_eval
from odoo.osv.expression import AND
from odoo.tools import html2plaintext


class KnowledgeArticle(models.Model):
    _inherit = "knowledge.article"

    @api.model
    def search_articles_server(self, query="", filters=None, sort="recent", limit=10, offset=0):
        """
        Server-side search with filters and sorting to reduce frontend payload.
        """
        filters = filters or {}
        parts = []
        terms = [t for t in (query or "").split() if t]
        for term in terms:
            parts.append(["|", ("name", "ilike", term), ("content", "ilike", term)])

        # Filters: category, tags (any), responsible, date range
        if filters.get("category_id"):
            parts.append([("category_id", "=", filters["category_id"])])
        if filters.get("tag_ids"):
            parts.append([("tag_ids", "in", filters["tag_ids"])])
        if filters.get("responsible_id"):
            parts.append([("responsible_id", "=", filters["responsible_id"])])
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        if date_from:
            parts.append([("write_date", ">=", date_from)])
        if date_to:
            parts.append([("write_date", "<=", date_to)])

        domain = AND(parts) if parts else []

        # Sorting
        if sort == "name":
            order = "name asc, write_date desc"
        elif sort == "views":
            # If no view_count field, fallback to write_date
            order = "view_count desc nulls last, write_date desc" if "view_count" in self._fields else "write_date desc"
        else:
            order = "write_date desc"

        total = self.search_count(domain)
        records = self.search(domain, order=order, limit=limit, offset=offset)

        def _strip_html(content):
            return html2plaintext(content or "")

        results = []
        for rec in records:
            clean = _strip_html(rec.content)
            results.append({
                "id": rec.id,
                "name": rec.name,
                "content": rec.content,
                "category_name": rec.category_id.name or "",
                "responsible_name": rec.responsible_id.name or "",
                "responsible_avatar": rec.responsible_id.image_128 or "",
                "write_date": rec.write_date and rec.write_date.strftime("%Y-%m-%d %H:%M:%S") or "",
                "create_date": rec.create_date and rec.create_date.strftime("%Y-%m-%d %H:%M:%S") or "",
                "clean_content": clean,
            })

        return {"total": total, "results": results}
