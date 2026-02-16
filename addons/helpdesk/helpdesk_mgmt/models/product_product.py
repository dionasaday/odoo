from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    def name_get(self):
        if not self.env.context.get("show_sku_name"):
            return super().name_get()
        base_names = dict(super().name_get())
        result = []
        for product in self:
            name = base_names.get(product.id, product.name or "")
            if product.default_code:
                name = f"[{product.default_code}] {name}"
            result.append((product.id, name))
        return result

    def _name_search(
        self, name="", args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        if not self.env.context.get("show_sku_name") or not name:
            return super()._name_search(
                name,
                args=args,
                operator=operator,
                limit=limit,
                name_get_uid=name_get_uid,
            )
        args = args or []
        domain = expression.AND(
            [args, ["|", "|", ("default_code", operator, name), ("name", operator, name), ("barcode", operator, name)]]
        )
        return self._search(domain, limit=limit, access_rights_uid=name_get_uid)
