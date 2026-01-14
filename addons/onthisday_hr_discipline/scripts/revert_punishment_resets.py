# Run inside Odoo shell:
# odoo shell -c /etc/odoo/odoo.conf -d <db> < /mnt/extra-addons/onthisday_hr_discipline/scripts/revert_punishment_resets.py

try:
    _env = env  # noqa: F821 - provided by Odoo shell
except NameError as exc:
    raise RuntimeError("This script must be run in Odoo shell (env is not defined).") from exc

Ledger = _env["hr.discipline.point.ledger"].sudo()

reset_entries = Ledger.search(
    [
        ("reason", "ilike", "Reset after punishment for case"),
        ("points_change", "!=", 0),
    ]
)

reverted = 0
skipped = 0

for entry in reset_entries:
    marker = f"Revert reset after punishment (ledger #{entry.id})"
    exists = Ledger.search_count([("reason", "=", marker)]) > 0
    if exists:
        skipped += 1
        continue

    Ledger.create(
        {
            "date": entry.date,
            "employee_id": entry.employee_id.id,
            "points_change": -entry.points_change,
            "reason": marker,
            "case_id": entry.case_id.id if entry.case_id else False,
        }
    )

    if entry.case_id:
        entry.case_id.write({"reset_points": False})
        entry.case_id.message_post(
            body=(
                "ย้อนการรีเซ็ตคะแนนจาก ledger #%s (points_change=%s)"
                % (entry.id, entry.points_change)
            )
        )

    reverted += 1

print("Reverted reset entries:", reverted)
print("Skipped (already reverted):", skipped)
