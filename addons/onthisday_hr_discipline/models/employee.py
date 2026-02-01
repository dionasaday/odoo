# models/employee.py
from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class HREmployee(models.Model):
    _inherit = "hr.employee"

    version_id = fields.Many2one(
        "hr.version",
        compute="_compute_version_id",
        search="_search_version_id",
        ondelete="cascade",
        required=True,
        store=False,
        compute_sudo=True,
        groups="base.group_user,hr.group_hr_user,onthisday_hr_discipline.group_discipline_hr,onthisday_hr_discipline.group_discipline_manager",
    )
    current_version_id = fields.Many2one(
        "hr.version",
        compute="_compute_current_version_id",
        store=True,
        groups="base.group_user,hr.group_hr_user,onthisday_hr_discipline.group_discipline_hr,onthisday_hr_discipline.group_discipline_manager",
    )

    discipline_points_year = fields.Integer(
        compute="_compute_discipline_points_year", store=False)
    
    # Token balance fields (Policy 002/2025)
    current_token_balance = fields.Integer(
        string="Current Token Balance",
        compute="_compute_current_token_balance",
        store=True,
        compute_sudo=True,
        help="Current token balance for the current period (starting tokens - deductions)."
    )
    token_period_start = fields.Date(
        string="Token Period Start",
        compute="_compute_current_token_balance",
        store=True,
        compute_sudo=True,
        help="Start date of current token period."
    )
    token_period_end = fields.Date(
        string="Token Period End",
        compute="_compute_current_token_balance",
        store=True,
        compute_sudo=True,
        help="End date of current token period."
    )
    tokens_deducted_this_period = fields.Integer(
        string="Tokens Deducted (This Period)",
        compute="_compute_current_token_balance",
        store=True,
        compute_sudo=True,
        help="Total tokens deducted in current period."
    )
    company_management_review_threshold = fields.Integer(
        string="Management Review Threshold",
        related="company_id.lateness_repeat_threshold",
        store=False,
        readonly=True,
    )

    # Token balance fields for historical period view (context-driven)
    token_balance_period = fields.Integer(
        string="Token Balance (Period)",
        compute="_compute_token_balance_period",
        store=False,
        help="Token balance for the selected period in context (token_period_date)."
    )
    tokens_deducted_period = fields.Integer(
        string="Tokens Deducted (Period)",
        compute="_compute_token_balance_period",
        store=False,
        help="Total tokens deducted in selected period."
    )
    token_period_start_period = fields.Date(
        string="Token Period Start (Period)",
        compute="_compute_token_balance_period",
        store=False,
    )
    token_period_end_period = fields.Date(
        string="Token Period End (Period)",
        compute="_compute_token_balance_period",
        store=False,
    )

    @api.depends()
    def _compute_discipline_points_year(self):
        # Initialize first
        for emp in self:
            emp.discipline_points_year = 0
        
        # Only compute if we have valid records
        if not self:
            return
        
        # Only compute if model exists and env is ready
        try:
            if not hasattr(self, 'env') or not self.env:
                return
            # Check if model exists in registry
            if 'hr.discipline.point.ledger' not in self.env:
                return
        except (AttributeError, KeyError, Exception):
            return
        
        try:
            Ledger = self.env['hr.discipline.point.ledger'].sudo()
            for emp in self:
                try:
                    if not emp.id:
                        continue
                        
                    year = fields.Date.today().year
                    start = getattr(emp.company_id, 'discipline_start_date', False)

                    domain = [
                        ('employee_id', '=', emp.id),
                        ('year', '=', year),
                    ]
                    # ตัดคะแนนก่อนวันเริ่มนโยบายออกจากผลรวม (เพื่อให้สอดคล้องทุกจอ)
                    if start:
                        domain.append(('date', '>=', start))

                    total = sum(Ledger.search(domain).mapped('points_change'))
                    emp.discipline_points_year = int(total or 0)
                except Exception:
                    emp.discipline_points_year = 0
        except Exception:
            # Silently fail - defaults already set
            pass

    @api.depends('company_id')
    def _compute_current_token_balance(self):
        """Compute current token balance for the current period (Policy 002/2025)."""
        today = fields.Date.today()
        self._compute_token_balance_for_date(
            today,
            target_fields=(
                "current_token_balance",
                "tokens_deducted_this_period",
                "token_period_start",
                "token_period_end",
            ),
        )

    def _compute_token_balance_for_date(self, date_value, target_fields):
        """Compute token balance for a given date and write to target field names."""
        for emp in self:
            setattr(emp, target_fields[0], 0)
            setattr(emp, target_fields[1], 0)
            setattr(emp, target_fields[2], False)
            setattr(emp, target_fields[3], False)

        if not self:
            return

        try:
            if not any(emp.id for emp in self if hasattr(emp, "id") and emp.id):
                return
        except Exception:
            pass

        try:
            if not hasattr(self, "env") or not self.env:
                return
            if "hr.discipline.point.ledger" not in self.env:
                return
        except (AttributeError, KeyError, Exception):
            return

        try:
            Ledger = self.env["hr.discipline.point.ledger"].sudo()
            for emp in self:
                try:
                    if not emp.id:
                        continue

                    try:
                        if hasattr(emp, "_origin") and emp._origin and not emp._origin.id:
                            continue
                    except Exception:
                        pass

                    company = emp.company_id
                    if not company or not hasattr(company, "token_period_type"):
                        continue

                    try:
                        period_start = emp._get_token_period_start(company, date_value)
                        period_end = emp._get_token_period_end(company, date_value)
                    except Exception:
                        continue

                    if not period_start or not period_end:
                        continue

                    setattr(emp, target_fields[2], period_start)
                    setattr(emp, target_fields[3], period_end)

                    starting_tokens = getattr(company, "tokens_starting_per_period", 0) or 0
                    domain = [
                        ("employee_id", "=", emp.id),
                        ("date", ">=", period_start),
                        ("date", "<=", period_end),
                    ]
                    ledger_records = Ledger.search(domain)
                    deducted = sum(
                        abs(rec.points_change)
                        for rec in ledger_records
                        if rec.points_change < 0
                    )
                    setattr(emp, target_fields[1], deducted)
                    setattr(emp, target_fields[0], starting_tokens - deducted)
                except Exception:
                    pass
        except Exception:
            pass

    @api.depends_context("token_period_date")
    def _compute_token_balance_period(self):
        """Compute token balance for selected period in context (token_period_date)."""
        ctx_date = self.env.context.get("token_period_date")
        if ctx_date:
            date_value = fields.Date.to_date(ctx_date)
        else:
            date_value = fields.Date.today()
        self._compute_token_balance_for_date(
            date_value,
            target_fields=(
                "token_balance_period",
                "tokens_deducted_period",
                "token_period_start_period",
                "token_period_end_period",
            ),
        )

    def _get_token_period_start(self, company, date):
        """Get start date of current token period."""
        try:
            date_obj = fields.Date.to_date(date)
            period_type = getattr(company, 'token_period_type', 'monthly') or 'monthly'
            
            if period_type == "weekly":
                start_day = getattr(company, 'token_period_start_day', 0) or 0  # 0=Monday
                days_since_monday = date_obj.weekday()
                days_to_subtract = (days_since_monday - start_day) % 7
                return date_obj - timedelta(days=days_to_subtract)
            else:
                # Monthly: start from reset_day_of_month
                reset_day = getattr(company, 'token_reset_day_of_month', 1) or 1
                if date_obj.day >= reset_day:
                    try:
                        return date_obj.replace(day=reset_day)
                    except ValueError:
                        # Handle invalid day (e.g., Feb 30 -> use last day of month)
                        if date_obj.month == 2:
                            # February
                            if reset_day > 28:
                                return date_obj.replace(day=28)
                        return date_obj.replace(day=1)
                else:
                    # Previous month
                    if date_obj.month == 1:
                        prev_month = date_obj.replace(year=date_obj.year - 1, month=12, day=1)
                    else:
                        prev_month = date_obj.replace(month=date_obj.month - 1, day=1)
                    try:
                        return prev_month.replace(day=reset_day)
                    except ValueError:
                        # Handle invalid day
                        return prev_month
        except Exception:
            # Fallback to today if any error
            return fields.Date.today()

    def _get_token_period_end(self, company, date):
        """Get end date of current token period."""
        try:
            date_obj = fields.Date.to_date(date)
            period_type = getattr(company, 'token_period_type', 'monthly') or 'monthly'
            
            if period_type == "weekly":
                period_start = self._get_token_period_start(company, date)
                if period_start:
                    return period_start + timedelta(days=6)
                return date_obj
            else:
                # Monthly: end of month or day before next reset
                reset_day = getattr(company, 'token_reset_day_of_month', 1) or 1
                try:
                    if date_obj.month == 12:
                        next_reset = date_obj.replace(year=date_obj.year + 1, month=1, day=reset_day)
                    else:
                        next_reset = date_obj.replace(month=date_obj.month + 1, day=reset_day)
                    return next_reset - timedelta(days=1)
                except (ValueError, AttributeError):
                    # Handle invalid day (e.g., Feb 30) or missing attributes
                    try:
                        if date_obj.month == 12:
                            next_reset = date_obj.replace(year=date_obj.year + 1, month=1, day=1)
                        else:
                            next_reset = date_obj.replace(month=date_obj.month + 1, day=1)
                        return next_reset - timedelta(days=1)
                    except Exception:
                        return date_obj
        except Exception:
            # Fallback to today if any error
            return fields.Date.today()

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Override to remove restricted fields from view if user doesn't have access."""
        # Use sudo() to get view if it's our custom token balance view to avoid access errors
        is_token_balance_view = False
        
        # IMPORTANT: Check view_id first (this works even after refresh)
        # When refresh happens, Odoo will pass the view_id that was used to open the page
        if view_id:
            try:
                view = self.env['ir.ui.view'].browse(view_id)
                if view.exists():
                    # Check by xml_id (most reliable)
                    if view.xml_id == 'onthisday_hr_discipline.view_employee_my_token_balance':
                        is_token_balance_view = True
                    # Also check by name as fallback
                    elif view.name == 'hr.employee.my.token.balance':
                        is_token_balance_view = True
            except Exception:
                pass
        
        # Also check context for token balance view (in case of refresh)
        # Check multiple context flags to ensure we can identify token balance view even after refresh
        if not is_token_balance_view:
            if (self._context.get('view_id') == 'onthisday_hr_discipline.view_employee_my_token_balance' or
                self._context.get('token_balance_view') or
                self._context.get('default_token_balance_view')):
                is_token_balance_view = True
        
        # Last resort: If no view_id and no context, but we're viewing a single employee record
        # that matches current user, assume it might be token balance view
        # This helps when refresh loses all context
        if not is_token_balance_view and view_type == 'form':
            # Check if we're viewing a single record that belongs to current user
            # This is a heuristic but helps with refresh scenarios
            try:
                active_id = self._context.get('active_id')
                if active_id:
                    employee = self.env['hr.employee'].browse(active_id)
                    if employee.exists() and employee.user_id == self.env.user:
                        # We're viewing our own employee record without view_id
                        # This might be token balance view (heuristic)
                        is_token_balance_view = True
            except Exception:
                pass
        
        # For token balance view, use sudo() to bypass field access restrictions
        if is_token_balance_view:
            # Use sudo() to bypass field access rights when getting view metadata
            result = self.env[self._name].sudo().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        else:
            result = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        
        # Remove restricted fields if user doesn't have HR access or if it's our custom view
        restricted_fields = ['version_id', 'current_leave_id']
        if is_token_balance_view or self._hide_version_id():
            # Remove restricted fields from fields metadata to prevent them from being loaded
            fields_meta = result.get('fields') or {}
            for field_name in restricted_fields:
                if field_name in fields_meta:
                    fields_meta.pop(field_name, None)
            # Update fields metadata
            if isinstance(fields_meta, dict):
                result['fields'] = fields_meta
            
            # Remove restricted fields from arch if they exist
            arch = result.get('arch', '')
            if arch and any(field in arch for field in restricted_fields):
                try:
                    from lxml import etree
                    root = etree.fromstring(arch.encode() if isinstance(arch, str) else arch)
                    for field_name in restricted_fields:
                        for field in root.xpath(f'.//field[@name="{field_name}"]'):
                            parent = field.getparent()
                            if parent is not None:
                                parent.remove(field)
                    result['arch'] = etree.tostring(root, encoding='unicode')
                except Exception as e:
                    # If XML parsing fails, try simple string replacement as fallback
                    try:
                        import re
                        # Remove field tags containing restricted fields
                        for field_name in restricted_fields:
                            result['arch'] = re.sub(rf'<field[^>]*name=["\']{field_name}["\'][^>]*/>', '', result['arch'])
                            result['arch'] = re.sub(rf'<field[^>]*name=["\']{field_name}["\'][^>]*>.*?</field>', '', result['arch'], flags=re.DOTALL)
                    except Exception:
                        # If all else fails, continue with original arch
                        pass
        
        return result

    def _hide_version_id(self):
        """Check if user should hide version_id field."""
        # Hide version_id if user doesn't have HR permissions
        # But always hide in our custom token balance view context
        if self._context.get('view_id') == 'onthisday_hr_discipline.view_employee_my_token_balance' or \
           self._context.get('token_balance_view'):
            return True
        # Check if user has HR permissions - if not, hide version_id
        # Note: Even if user is in 'Employees / Officer: Manage all employees' group,
        # they may not have access to version_id field which requires hr.group_hr_user
        try:
            return not self._has_hr_access()
        except Exception:
            # If check fails, assume user doesn't have access (safer)
            return True

    def _get_access_user(self):
        """Return the real user for access checks, even in sudo context."""
        if self.env.su:
            origin_user_id = self._context.get('origin_user_id')
            if origin_user_id:
                return self.env['res.users'].browse(origin_user_id)
        return self.env.user

    def _has_hr_access(self):
        """Return True if user has HR or system access."""
        try:
            user = self._get_access_user()
            return (
                user.has_group('onthisday_hr_discipline.group_discipline_hr')
                or user.has_group('hr.group_hr_user')
                or user.has_group('hr.group_hr_manager')
                or user.has_group('base.group_system')
            )
        except Exception:
            return False

    # ---------------------------------------------------------------------
    # Automation: Sync Discipline Manager group based on hierarchy
    # ---------------------------------------------------------------------
    @api.model
    def _cron_sync_discipline_manager_group(self):
        """Assign/remove Discipline Manager group based on direct subordinates."""
        group = self.env.ref(
            "onthisday_hr_discipline.group_discipline_manager",
            raise_if_not_found=False,
        )
        if not group:
            _logger.warning("Discipline Manager group not found; skipping sync.")
            return

        Employee = self.env["hr.employee"].sudo()
        manager_emps = Employee.search([("user_id", "!=", False), ("active", "=", True)])
        if not manager_emps:
            return

        subordinate_data = Employee.read_group(
            [("parent_id", "in", manager_emps.ids), ("active", "=", True)],
            ["parent_id"],
            ["parent_id"],
        )
        manager_emp_ids = {
            row["parent_id"][0] for row in subordinate_data if row.get("parent_id")
        }
        manager_users = Employee.browse(list(manager_emp_ids)).mapped("user_id")
        all_users = manager_emps.mapped("user_id")

        users_to_add = manager_users.filtered(lambda u: group not in u.group_ids)
        if users_to_add:
            users_to_add.sudo().write({"group_ids": [(4, group.id)]})
            _logger.info("Added Discipline Manager group to %d users.", len(users_to_add))

        users_to_remove = (all_users - manager_users).filtered(
            lambda u: group in u.group_ids
        )
        if users_to_remove:
            users_to_remove.sudo().write({"group_ids": [(3, group.id)]})
            _logger.info(
                "Removed Discipline Manager group from %d users.", len(users_to_remove)
            )

    # ---------------------------------------------------------------------
    # Automation: Recompute token balance when date changes (new period)
    # ---------------------------------------------------------------------
    @api.model
    def _cron_recompute_token_balance(self):
        """Legacy cron: token balance fields are now store=False, so they compute
        fresh on every read and always reflect today's period. This cron is kept
        for backwards compatibility but does nothing.
        """
        _logger.debug(
            "Token balance cron ran (fields are store=False, no action needed). Date: %s",
            fields.Date.today(),
        )

    def _allowed_employee_domain(self, user):
        """Return domain for employees visible to this user (non-HR)."""
        domain = [("user_id", "=", user.id)]
        company_domain = None
        if user.company_id:
            company_domain = ("company_id", "=", user.company_id.id)
        try:
            if user.has_group("onthisday_hr_discipline.group_discipline_manager"):
                if user.employee_id:
                    domain = [("id", "child_of", user.employee_id.id)]
                else:
                    domain = [("id", "=", 0)]
        except Exception:
            pass
        if company_domain:
            domain = [company_domain] + domain
        return domain

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Remove restricted fields from fields_get if user doesn't have access."""
        # List of restricted fields that may cause access errors
        restricted_fields = ['version_id', 'current_leave_id']
        
        # Always try to get fields metadata first, then remove restricted fields if needed
        # This prevents access errors during fields_get itself
        try:
            result = super().fields_get(allfields=allfields, attributes=attributes)
        except Exception:
            # If access error occurs, use sudo() to get fields metadata
            result = self.env[self._name].sudo().fields_get(allfields=allfields, attributes=attributes)
        
        # Always hide restricted fields for non-HR users (more aggressive approach)
        # This ensures fields are never exposed even if context is lost during refresh
        should_hide = False
        if self._context.get('view_id') == 'onthisday_hr_discipline.view_employee_my_token_balance' or \
           self._context.get('token_balance_view'):
            should_hide = True
        elif self._hide_version_id():
            should_hide = True
        
        # Remove restricted fields from result if needed
        if should_hide:
            for field_name in restricted_fields:
                if field_name in result:
                    result.pop(field_name, None)
        
        return result

    def read(self, fields=None, load='_classic_read'):
        """Avoid accessing restricted fields for non-HR users."""
        # List of restricted fields that may cause access errors
        restricted_fields = ['version_id', 'current_leave_id']

        access_user = self._get_access_user()
        has_hr_access = self._has_hr_access()
        if not has_hr_access and self:
            allowed_ids = self.env["hr.employee"].sudo().search(
                self._allowed_employee_domain(access_user)
            ).ids
            if not allowed_ids:
                raise AccessError(_('คุณไม่มีสิทธิ์เข้าถึงข้อมูลพนักงาน'))
            if any(record.id not in allowed_ids for record in self):
                raise AccessError(_('คุณไม่มีสิทธิ์เข้าถึงข้อมูลพนักงานท่านอื่น'))
            self = self.filtered(lambda record: record.id in allowed_ids)
        
        # Check if we're already in sudo context to prevent recursion
        if self._context.get('_skip_restricted_fields_check'):
            # Skip our custom logic and call parent directly to prevent recursion
            return super().read(fields=fields, load=load)
        
        # Always exclude restricted fields for non-HR users (aggressive approach)
        # This ensures fields are never accessed even if context is lost during refresh
        # IMPORTANT: When refresh happens, context may be lost, so we check _hide_version_id() first
        # This ensures non-HR users always exclude restricted fields regardless of context
        should_exclude = (
            self._context.get('view_id') == 'onthisday_hr_discipline.view_employee_my_token_balance' or
            self._context.get('token_balance_view') or
            self._context.get('default_token_balance_view') or
            self._hide_version_id()  # This checks HR permissions - works even without context
        )
        
        # Additional check: If viewing single record that belongs to current user, exclude restricted fields
        # This helps with refresh scenarios where context is lost
        if not should_exclude:
            try:
                # Check if we're viewing a single record
                if len(self) == 1:
                    employee = self[0]
                    # If viewing our own employee record and don't have HR access, exclude restricted fields
                    if employee.user_id == self.env.user and self._hide_version_id():
                        should_exclude = True
            except Exception:
                pass
        
        if should_exclude:
            # For token balance view or non-HR users, exclude restricted fields from fields to read
            if fields is None:
                fields = [name for name in self._fields if name not in restricted_fields]
            else:
                fields = [name for name in fields if name not in restricted_fields]
            # Use sudo() with context flag to bypass field access rights and prevent recursion
            # This is safe because we've already verified user can only see their own record in action_view_my_token_balance
            return self.with_context(
                _skip_restricted_fields_check=True,
                origin_user_id=access_user.id
            ).sudo().read(fields=fields, load=load)
        
        # For HR users, try normal read first, but use sudo() if access error occurs
        try:
            return super().read(fields=fields, load=load)
        except Exception as e:
            # If access error occurs for restricted fields, use sudo() as fallback
            from odoo.exceptions import AccessError
            error_str = str(e)
            # Check if error is AccessError and related to restricted fields
            # More aggressive check: catch any AccessError related to hr.employee fields
            if isinstance(e, AccessError) or 'Access' in str(type(e).__name__):
                # Check if error is related to restricted fields (more aggressive check)
                # Also check if error mentions hr.employee and field access
                # This catches errors even if field name is not explicitly in error message
                if any(field in error_str for field in restricted_fields) or \
                   'current_leave_id' in error_str or \
                   'version_id' in error_str or \
                   ('hr.employee' in error_str and 'field' in error_str.lower()) or \
                   ('Employee' in error_str and 'field' in error_str.lower() and 'access' in error_str.lower()):
                    # Exclude restricted fields and use sudo() if needed
                    if fields is None:
                        fields = [name for name in self._fields if name not in restricted_fields]
                    else:
                        fields = [name for name in fields if name not in restricted_fields]
                    # Use context flag to prevent recursion
                    return self.with_context(
                        _skip_restricted_fields_check=True,
                        origin_user_id=access_user.id
                    ).sudo().read(fields=fields, load=load)
            raise
    
    def action_view_my_token_balance(self):
        """Action to view my token balance (read-only)."""
        self.ensure_one()
        
        # Security check: Ensure user can only view their own employee record
        if self.user_id and self.user_id != self.env.user:
            raise AccessError(_('คุณสามารถดู Token Balance ของตัวเองเท่านั้น'))
        
        # Add context to exclude restricted fields and identify token balance view
        custom_context = {
            'form_view_initial_mode': 'readonly',
            'no_create': True,
            'create': False,
            'edit': False,
            'readonly': True,
            'view_id': 'onthisday_hr_discipline.view_employee_my_token_balance',
            'token_balance_view': True,  # Flag to identify token balance view (for refresh scenarios)
        }
        
        try:
            view_id = self.env.ref('onthisday_hr_discipline.view_employee_my_token_balance', raise_if_not_found=False)
            if not view_id:
                # Fallback: try to get view by name
                view_id = self.env['ir.ui.view'].search([
                    ('model', '=', 'hr.employee'),
                    ('name', '=', 'hr.employee.my.token.balance')
                ], limit=1)
                if not view_id:
                    # Final fallback to standard form view if custom view not found
                    return {
                        'name': _('Token Balance ของฉัน'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'hr.employee',
                        'res_id': self.id,
                        'view_mode': 'form',
                        'target': 'current',
                        'context': custom_context,
                    }
            return {
                'name': _('Token Balance ของฉัน'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.employee',
                'res_id': self.id,
                'view_mode': 'form',
                'views': [(view_id.id, 'form')],  # Use views list to ensure view_id is preserved on refresh
                'view_id': view_id.id,
                'target': 'current',
                'context': custom_context,
            }
        except Exception:
            # Fallback to standard form view
            return {
                'name': _('Token Balance ของฉัน'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.employee',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
                'context': custom_context,
            }

    @api.model
    def action_open_token_balance_summary(self):
        """Open token balance summary list for HR/Manager."""
        user = self.env.user
        action = self.env.ref(
            "onthisday_hr_discipline.action_token_balance_summary",
            raise_if_not_found=False,
        )
        if not action:
            raise AccessError(_("ไม่พบเมนูสรุป Token กรุณาอัปเกรดโมดูล"))

        action_data = action.sudo().read()[0]
        view = self.env.ref(
            "onthisday_hr_discipline.view_employee_token_balance_summary_tree",
            raise_if_not_found=False,
        )
        if view:
            view = view.sudo()
        search_view = self.env.ref(
            "onthisday_hr_discipline.view_employee_token_balance_summary_search",
            raise_if_not_found=False,
        )
        if search_view:
            search_view = search_view.sudo()
        domain = []
        if user.company_id:
            domain.append(("company_id", "=", user.company_id.id))

        if user.has_group("onthisday_hr_discipline.group_discipline_hr"):
            pass
        elif user.has_group("onthisday_hr_discipline.group_discipline_manager"):
            if user.employee_id:
                domain.append(("id", "child_of", user.employee_id.id))
            else:
                domain.append(("id", "=", 0))
        else:
            raise AccessError(_("คุณไม่มีสิทธิ์เข้าถึงเมนูนี้"))

        context = action_data.get("context") or {}
        if isinstance(context, str):
            try:
                context = safe_eval(context, {"user": user, "uid": user.id})
            except Exception:
                context = {}
        if not isinstance(context, dict):
            context = {}

        action_data.update(
            {
                "domain": domain,
                "context": dict(context, token_balance_summary=True),
            }
        )
        if view:
            action_data["views"] = [(view.id, "list")]
            action_data["view_id"] = view.id
        if search_view:
            action_data["search_view_id"] = search_view.id
        action_data.pop("id", None)
        return action_data

    @api.model
    def action_open_token_balance_summary_with_period(self, months_back=0):
        """Open token balance summary for a specific period (for historical view).
        months_back: 0=current month, 1=last month, 2=2 months ago, etc.
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        action_data = self.action_open_token_balance_summary()
        if months_back <= 0:
            return action_data

        ref_date = (datetime.now() + relativedelta(months=-months_back)).replace(day=1)
        period_date = ref_date.strftime("%Y-%m-%d")
        ctx = action_data.get("context") or {}
        ctx["token_period_date"] = period_date
        action_data["context"] = ctx
        # Update title to show period
        month_names = [
            "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
            "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
        ]
        be_year = ref_date.year + 543
        action_data["name"] = _("สรุป Token คงเหลือ (%s %s)") % (
            month_names[ref_date.month],
            be_year,
        )
        return action_data

    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Allow sorting by non-stored token balance in summary view."""
        kwargs.pop("access_rights_uid", None)
        kwargs.pop("count", None)
        if self._context.get("token_balance_summary") and order:
            order_l = order.lower()
            if "current_token_balance" in order_l or "token_balance_period" in order_l:
                ids = super()._search(
                    domain,
                    offset=0,
                    limit=None,
                    order="name",
                    **kwargs,
                )
                records = self.browse(ids)
                descending = "desc" in order_l
                key_attr = "token_balance_period" if "token_balance_period" in order_l else "current_token_balance"
                records = records.sorted(
                    key=lambda r: (getattr(r, key_attr, 0), r.name or ""),
                    reverse=descending,
                )
                ids = records.ids
                if offset:
                    ids = ids[offset:]
                if limit:
                    ids = ids[:limit]
                return ids

        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            **kwargs,
        )

    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        """Sort by non-stored token balance in summary view without SQL order."""
        if self._context.get("token_balance_summary") and order:
            order_l = order.lower()
            if "current_token_balance" in order_l or "token_balance_period" in order_l:
                descending = "desc" in order_l
                key_attr = "token_balance_period" if "token_balance_period" in order_l else "current_token_balance"
                records = self.search(domain, order="name")
                if descending:
                    records = records.sorted(
                        key=lambda r: (-getattr(r, key_attr, 0), r.name or "")
                    )
                else:
                    records = records.sorted(
                        key=lambda r: (getattr(r, key_attr, 0), r.name or "")
                    )
                if offset:
                    records = records[offset:]
                if limit:
                    records = records[:limit]
                return records

        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)
