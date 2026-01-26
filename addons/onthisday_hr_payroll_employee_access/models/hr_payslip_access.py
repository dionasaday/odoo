# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class IrModelAccess(models.Model):
    """Inherit ir.model.access to create access rights for employees"""
    _inherit = 'ir.model.access'

    @api.model
    def _create_employee_payslip_access(self):
        """Create access rights and security rules for employees to view their own payslips"""
        IrRule = self.env['ir.rule']
        
        # ลบ security rules ที่มีอยู่แล้วสำหรับ payslip lines, worked days, และ inputs (ถ้ามี)
        # เพื่อให้ Payroll Officer/Manager สามารถสร้าง records ได้
        # ต้องลบ rule นี้ก่อนเพื่อแก้ปัญหา Access Error
        existing_rules = IrRule.search([
            ('name', 'in', [
                'Employee: Own Payslip Lines Only',
                'Employee: Own Payslip Worked Days Only',
                'Employee: Own Payslip Inputs Only'
            ])
        ])
        if existing_rules:
            rule_names = existing_rules.mapped('name')
            _logger.info(f"Deleting problematic security rules: {rule_names}")
            existing_rules.unlink()
            _logger.info(f"Successfully deleted {len(existing_rules)} security rules")
        else:
            _logger.info("No problematic security rules found to delete")
        
        # Get models
        payslip_model = self.env['ir.model'].search([('model', '=', 'hr.payslip')], limit=1)
        payslip_line_model = self.env['ir.model'].search([('model', '=', 'hr.payslip.line')], limit=1)
        payslip_worked_days_model = self.env['ir.model'].search([('model', '=', 'hr.payslip.worked.days')], limit=1)
        payslip_input_model = self.env['ir.model'].search([('model', '=', 'hr.payslip.input')], limit=1)
        employee_group = self.env.ref('base.group_user', raise_if_not_found=False)
        
        if not payslip_model or not payslip_line_model or not employee_group:
            return
        
        # Create or update access rights for hr.payslip
        access_payslip = self.search([
            ('name', '=', 'hr.payslip.employee.user'),
            ('model_id', '=', payslip_model.id),
            ('group_id', '=', employee_group.id)
        ], limit=1)
        
        if not access_payslip:
            self.create({
                'name': 'hr.payslip.employee.user',
                'model_id': payslip_model.id,
                'group_id': employee_group.id,
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })
        else:
            access_payslip.write({
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })
        
        # Create or update access rights for hr.payslip.line
        access_payslip_line = self.search([
            ('name', '=', 'hr.payslip.line.employee.user'),
            ('model_id', '=', payslip_line_model.id),
            ('group_id', '=', employee_group.id)
        ], limit=1)
        
        if not access_payslip_line:
            self.create({
                'name': 'hr.payslip.line.employee.user',
                'model_id': payslip_line_model.id,
                'group_id': employee_group.id,
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })
        else:
            access_payslip_line.write({
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })
        
        # Create or update access rights for hr.payslip.worked.days
        if payslip_worked_days_model:
            access_payslip_worked_days = self.search([
                ('name', '=', 'hr.payslip.worked.days.employee.user'),
                ('model_id', '=', payslip_worked_days_model.id),
                ('group_id', '=', employee_group.id)
            ], limit=1)
            
            if not access_payslip_worked_days:
                self.create({
                    'name': 'hr.payslip.worked.days.employee.user',
                    'model_id': payslip_worked_days_model.id,
                    'group_id': employee_group.id,
                    'perm_read': True,
                    'perm_write': False,
                    'perm_create': False,
                    'perm_unlink': False,
                })
            else:
                access_payslip_worked_days.write({
                    'perm_read': True,
                    'perm_write': False,
                    'perm_create': False,
                    'perm_unlink': False,
                })
        
        # Create or update access rights for hr.payslip.input
        if payslip_input_model:
            access_payslip_input = self.search([
                ('name', '=', 'hr.payslip.input.employee.user'),
                ('model_id', '=', payslip_input_model.id),
                ('group_id', '=', employee_group.id)
            ], limit=1)
            
            if not access_payslip_input:
                self.create({
                    'name': 'hr.payslip.input.employee.user',
                    'model_id': payslip_input_model.id,
                    'group_id': employee_group.id,
                    'perm_read': True,
                    'perm_write': False,
                    'perm_create': False,
                    'perm_unlink': False,
                })
            else:
                access_payslip_input.write({
                    'perm_read': True,
                    'perm_write': False,
                    'perm_create': False,
                    'perm_unlink': False,
                })
        
        # Create or update security rules
        # Security Rule: พนักงานสามารถดูสลิปเงินเดือนของตัวเองได้เท่านั้น
        # แต่ยกเว้น Payroll Officer/Manager (พวกเขามี rule ของตัวเองอยู่แล้ว)
        # วิธีแก้: ใช้ domain ที่เช็คว่า user ไม่ได้อยู่ใน payroll officer/manager group
        # โดยใช้ domain ที่ exclude payroll groups
        payroll_officer_group = self.env.ref('hr_payroll_community.group_hr_payroll_community_user', raise_if_not_found=False)
        payroll_manager_group = self.env.ref('hr_payroll_community.group_hr_payroll_community_manager', raise_if_not_found=False)
        
        rule_payslip = IrRule.search([
            ('name', '=', 'Employee: Own Payslips Only'),
            ('model_id', '=', payslip_model.id)
        ], limit=1)
        
        # Domain: ดูได้เฉพาะของตัวเอง
        # หมายเหตุ: ใช้ global=False เพื่อให้ payroll officer/manager rule (จาก hr_payroll_community) 
        # มี priority สูงกว่าและ override rule นี้
        domain_force = "[('employee_id.user_id', '=', user.id)]"
        
        if not rule_payslip:
            IrRule.create({
                'name': 'Employee: Own Payslips Only',
                'model_id': payslip_model.id,
                'domain_force': domain_force,
                'groups': [(6, 0, [employee_group.id])],
                'global': False,  # ไม่ใช่ global rule เพื่อให้ payroll officer/manager rule มี priority สูงกว่า
            })
        else:
            rule_payslip.write({
                'domain_force': domain_force,
                'groups': [(6, 0, [employee_group.id])],
                'global': False,
            })
        
        # ไม่สร้าง security rules สำหรับ payslip lines, worked days, และ inputs เพราะ:
        # 1. Payroll Officer/Manager มี rule ของตัวเองอยู่แล้ว (จาก hr_payroll_community)
        # 2. พนักงานทั่วไปจะถูกจำกัดด้วย access rights (read only, no create) อยู่แล้ว
        # 3. Security rules เหล่านี้จะทำให้ Payroll Officer/Manager ไม่สามารถสร้าง records ได้
        # 
        # พนักงานทั่วไปจะสามารถดู payslip lines, worked days, และ inputs ของตัวเองได้
        # ผ่าน payslip record ที่มี security rule อยู่แล้ว (Employee: Own Payslips Only)
        # และ access rights จำกัดให้ read only อยู่แล้ว
