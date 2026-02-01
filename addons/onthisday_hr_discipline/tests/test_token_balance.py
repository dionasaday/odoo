# -*- coding: utf-8 -*-
"""Smoke tests for token balance and period computation."""
from datetime import date

from odoo.tests import common


class TestTokenBalance(common.TransactionCase):
    """Smoke tests for token balance fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env["hr.employee"].with_context(tracking_disable=True)
        cls.Company = cls.env["res.company"].with_context(tracking_disable=True)
        cls.company = cls.Company.search([], limit=1)
        cls.employee = cls.Employee.search([("company_id", "!=", False)], limit=1)
        if not cls.employee:
            cls.employee = cls.Employee.create({
                "name": "Test Employee Token",
                "company_id": cls.company.id,
            })

    def test_token_balance_compute_returns_valid_values(self):
        """Token balance fields compute and return valid values."""
        emp = self.employee
        self.assertTrue(emp.company_id, "Employee must have company")
        self.assertIsInstance(emp.current_token_balance, int)
        self.assertIsInstance(emp.tokens_deducted_this_period, int)
        self.assertGreaterEqual(emp.current_token_balance, 0)
        self.assertGreaterEqual(emp.tokens_deducted_this_period, 0)
        if emp.token_period_start and emp.token_period_end:
            self.assertLessEqual(
                emp.token_period_start,
                emp.token_period_end,
                "Period start must be <= period end",
            )

    def test_token_period_uses_today(self):
        """Token period reflects current date (store=False ensures fresh compute)."""
        emp = self.employee
        today = date.today()
        if emp.token_period_start and emp.token_period_end:
            self.assertLessEqual(
                emp.token_period_start,
                today,
                "Period start should be <= today",
            )
            self.assertGreaterEqual(
                emp.token_period_end,
                today,
                "Period end should be >= today",
            )

    def test_token_balance_list_loads_without_error(self):
        """Token balance summary list view loads without error."""
        employees = self.Employee.search([
            ("company_id", "!=", False),
        ], limit=5)
        self.assertTrue(employees, "Need at least one employee")
        # Read fields used by token balance summary view
        data = employees.read([
            "name",
            "current_token_balance",
            "token_period_start",
            "token_period_end",
            "tokens_deducted_this_period",
        ])
        self.assertEqual(len(data), len(employees))
        for row in data:
            self.assertIn("current_token_balance", row)
            self.assertIn("token_period_start", row)
            self.assertIn("token_period_end", row)
