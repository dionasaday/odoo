"""Manual maintenance tasks for onthisday_hr_discipline.

Usage (inside Odoo container or host with odoo-bin):
  odoo shell -d <dbname> -c /etc/odoo/odoo.conf < addons/onthisday_hr_discipline/scripts/manual_post_init_tasks.py
"""
from odoo import SUPERUSER_ID


def run(env):
    env = env.sudo()

    # 1) Remove legacy assets from om_account_asset (if any)
    env.cr.execute(
        """
        DELETE FROM ir_asset
        WHERE path LIKE '/om_account_asset/static/%'
        AND (name = 'Account Assets' OR name = 'aAccount Assets SCSS')
        """
    )
    print(f"[manual] removed ir_asset rows: {env.cr.rowcount}")

    # 2) Clear group restrictions for Token Balance and root menus
    menu_xmlids = [
        "onthisday_hr_discipline.menu_my_token_balance",
        "onthisday_hr_discipline.menu_hr_discipline_root",
        "onthisday_hr_discipline.menu_my_discipline_root",
    ]
    menu_ids = []
    for xmlid in menu_xmlids:
        data = env["ir.model.data"].search(
            [("module", "=", xmlid.split(".")[0]), ("name", "=", xmlid.split(".")[1])],
            limit=1,
        )
        if data:
            menu_ids.append(data.res_id)
    if menu_ids:
        env["ir.ui.menu"].action_clear_menu_groups(menu_ids)
        print(f"[manual] cleared menu groups for menu_ids={menu_ids}")

    # 3) Ensure Case No. exists (name != '/' and != False)
    Case = env["hr.discipline.case"]
    cases_without_name = Case.search(["|", ("name", "=", "/"), ("name", "=", False)])
    if cases_without_name:
        print(f"[manual] found {len(cases_without_name)} cases without Case No.")
        cases_by_company = {}
        for case in cases_without_name:
            company_id = case.company_id.id if case.company_id else False
            cases_by_company.setdefault(company_id, []).append(case)

        for company_id, cases in cases_by_company.items():
            sequence = env["ir.sequence"].search(
                [
                    ("code", "=", "hr.discipline.case"),
                    "|",
                    ("company_id", "=", company_id),
                    ("company_id", "=", False),
                ],
                limit=1,
            )
            if not sequence:
                vals = {
                    "name": "Discipline Case",
                    "code": "hr.discipline.case",
                    "prefix": "DISC/%(year)s/",
                    "padding": 4,
                    "number_next": 1,
                    "number_increment": 1,
                }
                if company_id:
                    vals["company_id"] = company_id
                sequence = env["ir.sequence"].create(vals)
                print(f"[manual] created sequence id={sequence.id} for company_id={company_id}")

            for case in cases:
                new_name = env["ir.sequence"].with_company(company_id).next_by_code(
                    "hr.discipline.case"
                )
                if new_name and new_name != "/":
                    case.write({"name": new_name})
                    print(f"[manual] updated case id={case.id} name={new_name}")

    # 4) Force update root menu name
    menu_data = env["ir.model.data"].search(
        [
            ("module", "=", "onthisday_hr_discipline"),
            ("name", "=", "menu_hr_discipline_root"),
            ("model", "=", "ir.ui.menu"),
        ],
        limit=1,
    )
    if menu_data:
        menu = env["ir.ui.menu"].browse(menu_data.res_id)
        if menu.exists():
            menu.write({"name": "วินัยและมาตรฐานการทำงาน"})
            print("[manual] updated menu_hr_discipline_root name")

    env.cr.commit()
    print("[manual] done")


if "env" in globals():
    run(env)
