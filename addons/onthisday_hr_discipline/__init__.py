from . import models
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    ลบ ir.asset records จากโมดูล om_account_asset ที่ถูก disable แล้ว
    เพื่อแก้ปัญหา SCSS compilation error
    และลบ groups restriction ออกจากเมนู Token Balance
    """
    # ลบ ir.asset records
    env.cr.execute("""
        DELETE FROM ir_asset 
        WHERE path LIKE '/om_account_asset/static/%'
        AND (name = 'Account Assets' OR name = 'aAccount Assets SCSS')
    """)
    
    # ลบ groups restriction ออกจากเมนู Token Balance โดยใช้ SQL
    # ใช้ ir_model_data เป็นหลักเพื่อห menu_id
    env.cr.execute("""
        SELECT res_id FROM ir_model_data 
        WHERE module = 'onthisday_hr_discipline' 
        AND name = 'menu_my_token_balance'
        AND model = 'ir.ui.menu'
    """)
    result = env.cr.fetchone()
    
    if result:
        menu_id = result[0]
        _logger.info(f"Found menu_my_token_balance with ID: {menu_id}")
        
        # ลบ groups restriction
        env.cr.execute("""
            DELETE FROM ir_ui_menu_group_rel
            WHERE menu_id = %s
        """, (menu_id,))
        
        deleted_count = env.cr.rowcount
        _logger.info(f"Removed {deleted_count} group restrictions from menu_my_token_balance")
        
        # Commit เพื่อให้การเปลี่ยนแปลงมีผลทันที
        env.cr.commit()
    else:
        _logger.warning("menu_my_token_balance not found in ir_model_data")
    
    # อัปเดต Case No. สำหรับ case ที่มี name = "/" หรือไม่มี name
    try:
        Case = env['hr.discipline.case']
        cases_without_name = Case.search([
            '|', ('name', '=', '/'), ('name', '=', False)
        ])
        
        if cases_without_name:
            _logger.info(f"Found {len(cases_without_name)} cases without Case No. Updating...")
            
            # Group cases by company_id for better sequence handling
            cases_by_company = {}
            for case in cases_without_name:
                company_id = case.company_id.id if case.company_id else False
                if company_id not in cases_by_company:
                    cases_by_company[company_id] = []
                cases_by_company[company_id].append(case)
            
            # Process each company group
            for company_id, cases in cases_by_company.items():
                _logger.info(f"Processing {len(cases)} cases for company_id={company_id}")
                
                # Ensure sequence exists for this company
                # Search for sequence with matching company_id or no company_id
                sequence = env['ir.sequence'].search([
                    ('code', '=', 'hr.discipline.case'),
                    '|',
                    ('company_id', '=', company_id),
                    ('company_id', '=', False)
                ], limit=1)
                
                if not sequence:
                    # Create sequence for this company
                    _logger.warning(f"Sequence 'hr.discipline.case' not found for company_id={company_id}. Creating...")
                    sequence_vals = {
                        'name': 'Discipline Case',
                        'code': 'hr.discipline.case',
                        'prefix': 'DISC/%(year)s/',
                        'padding': 4,
                        'number_next': 1,
                        'number_increment': 1,
                    }
                    if company_id:
                        sequence_vals['company_id'] = company_id
                    sequence = env['ir.sequence'].create(sequence_vals)
                    _logger.info(f"Created sequence 'hr.discipline.case' with ID={sequence.id} for company_id={company_id}")
                    env.cr.commit()
                
                # Update cases for this company
                for case in cases:
                    try:
                        # Use with_company to ensure correct sequence is used
                        new_name = env['ir.sequence'].with_company(company_id).next_by_code('hr.discipline.case') or "/"
                        if new_name != "/":
                            case.write({'name': new_name})
                            _logger.info(f"Updated case ID={case.id} (company_id={company_id}, employee={case.employee_id.name if case.employee_id else 'N/A'}) name from '/' to '{new_name}'")
                        else:
                            _logger.warning(f"Failed to generate Case No. for case ID={case.id} (company_id={company_id})")
                    except Exception as case_error:
                        _logger.error(f"Error updating case ID={case.id}: {case_error}")
            
            _logger.info(f"Completed updating {len(cases_without_name)} cases with Case No.")
            env.cr.commit()
        else:
            _logger.info("No cases found without Case No.")
    except Exception as e:
        _logger.error(f"Error updating Case No.: {e}", exc_info=True)
    
    # Force update menu name for menu_hr_discipline_root
    try:
        # Method 1: Try using ORM first
        try:
            menu_data = env['ir.model.data'].search([
                ('module', '=', 'onthisday_hr_discipline'),
                ('name', '=', 'menu_hr_discipline_root'),
                ('model', '=', 'ir.ui.menu')
            ], limit=1)
            
            if menu_data:
                menu = env['ir.ui.menu'].browse(menu_data.res_id)
                old_name = menu.name
                menu.write({'name': 'วินัยและมาตรฐานการทำงาน'})
                env.cr.commit()
                _logger.info(f"Updated menu_hr_discipline_root via ORM: '{old_name}' -> '{menu.name}'")
            else:
                _logger.warning("menu_hr_discipline_root not found in ir.model.data (ORM method)")
        except Exception as orm_error:
            _logger.warning(f"ORM method failed: {orm_error}. Trying SQL method...")
            
            # Method 2: Fallback to SQL
            env.cr.execute("""
                SELECT res_id FROM ir_model_data 
                WHERE module = 'onthisday_hr_discipline' 
                AND name = 'menu_hr_discipline_root'
                AND model = 'ir.ui.menu'
            """)
            result = env.cr.fetchone()
            
            if result:
                menu_id = result[0]
                _logger.info(f"Found menu_hr_discipline_root with ID: {menu_id}")
                
                # Get current name
                env.cr.execute("SELECT name FROM ir_ui_menu WHERE id = %s", (menu_id,))
                old_name = env.cr.fetchone()[0] if env.cr.rowcount > 0 else "N/A"
                
                # Force update menu name
                env.cr.execute("""
                    UPDATE ir_ui_menu
                    SET name = 'วินัยและมาตรฐานการทำงาน'
                    WHERE id = %s
                """, (menu_id,))
                
                updated_count = env.cr.rowcount
                _logger.info(f"Updated menu_hr_discipline_root via SQL: '{old_name}' -> 'วินัยและมาตรฐานการทำงาน'. Rows affected: {updated_count}")
                
                # Commit เพื่อให้การเปลี่ยนแปลงมีผลทันที
                env.cr.commit()
            else:
                _logger.warning("menu_hr_discipline_root not found in ir_model_data (SQL method)")
    except Exception as e:
        _logger.error(f"Error updating menu name: {e}", exc_info=True)