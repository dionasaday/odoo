from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def action_clear_menu_groups(self, menu_ids):
        """Clear group restrictions for given menu IDs via SQL."""
        if not menu_ids:
            return
        menus = self.browse(menu_ids).exists()
        if not menus:
            return
        try:
            self.env.cr.execute(
                "DELETE FROM ir_ui_menu_group_rel WHERE menu_id IN %s",
                (tuple(menus.ids),)
            )
        except Exception:
            # If the relation table is missing in this Odoo version, skip silently.
            return
