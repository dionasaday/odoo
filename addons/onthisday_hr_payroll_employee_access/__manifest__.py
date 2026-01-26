# -*- coding: utf-8 -*-
{
    'name': 'OnThisDay HR Payroll Employee Access',
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'summary': 'ให้พนักงานสามารถดูสลิปเงินเดือนของตัวเองได้',
    'description': """
        ฟีเจอร์:
        - เพิ่มสิทธิ์ให้พนักงานทั่วไปสามารถดูสลิปเงินเดือนของตัวเองได้ (read only)
        - เพิ่ม security rule เพื่อจำกัดให้พนักงานดูได้เฉพาะสลิปของตัวเอง
        - เพิ่มเมนูสำหรับพนักงานดูสลิปเงินเดือนของตัวเอง
    """,
    'author': 'On This Day',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_payroll_community',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_version_rules.xml',
        'views/report_payslipdetails_inherit.xml',
        'views/payslip_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
