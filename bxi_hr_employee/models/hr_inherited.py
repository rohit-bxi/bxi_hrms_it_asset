from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_code = fields.Char(string="Employee Code")
    pa_name = fields.Char(string="PA Name")  
    psa = fields.Char(string="PSA")
    disp = fields.Char(string="DISP")
    role_band = fields.Char(string="Role Band")  
    aadhar_card = fields.Char(string="Aadhar Card")
    emp_category = fields.Char(string="EMP Category")
    emp_skill_category = fields.Char(string="EMP Skill Category")
    manager_emp_code = fields.Char(string="Manager EMP Code")
    medical_insurance_no = fields.Char(string="Medical Insurance No.")
    nps_contribution = fields.Monetary(
        string="NPS Contribution",
        help="Employee NPS contribution amount",
        currency_field="currency_id"
    )  
    probation_period = fields.Selection(
        [
            ('yes', 'Yes'),
            ('no', 'No'),
        ],
        string="Probation Period",
        default='no'
    )
    trainee_category = fields.Selection(
        [
            ('yes', 'Yes'),
            ('no', 'No'),
        ],
        string="Trainee Category",
        default='no'
    )
    onsite_offshore = fields.Selection(
        [
            ('onsite', 'Onsite'),
            ('offshore', 'Offshore'),
        ],
        string="Onsite/Offshore"
    )
    company_code = fields.Char(string="Company Code")


    # You said you already have this field and it is calculated.
    # If it's already defined somewhere in your custom module, REMOVE this line.
    employee_ctc = fields.Float(string="Employee CTC (Annual)")

    def _fy_bounds_india(self, d):
        """Indian FY: Apr 1 to Mar 31"""
        if d.month <= 3:
            return date(d.year - 1, 4, 1), date(d.year, 3, 31)
        return date(d.year, 4, 1), date(d.year + 1, 3, 31)

    def _months_inclusive(self, d1, d2):
        """Months from d1-month to d2-month inclusive"""
        return (d2.year - d1.year) * 12 + (d2.month - d1.month) + 1

    def _new_regime_tax_fy_2025_26(self, annual_taxable):
        """
        New Tax Regime Slabs (FY 2025-26 / AY 2026-27):
        0-4L:0%, 4-8L:5%, 8-12L:10%, 12-16L:15%, 16-20L:20%, 20-24L:25%, >24L:30%
        """
        slabs = [
            (400000, 0.00),
            (800000, 0.05),
            (1200000, 0.10),
            (1600000, 0.15),
            (2000000, 0.20),
            (2400000, 0.25),
            (float("inf"), 0.30),
        ]
        tax = 0.0
        prev = 0.0
        for limit, rate in slabs:
            if annual_taxable <= prev:
                break
            part = min(annual_taxable, limit) - prev
            tax += part * rate
            prev = limit
        return tax

    def action_calculate_l10n_in_tds_new_regime(self):
        """
        Button:
        - Uses employee_ctc as annual base (17.2 LPA style)
        - Standard Deduction: 75,000 (salaried)
        - Rebate logic: no tax payable up to 12L taxable (rebate); so set tax to 0 if taxable <= 12,00,000
        - Adds 4% cess
        - Spreads tax over remaining months in FY (including current month)
        - Writes monthly amount to employee.l10n_in_tds
        """
        today = fields.Date.context_today(self)
        if isinstance(today, str):
            today = fields.Date.from_string(today)

        fy_start, fy_end = self._fy_bounds_india(today)
        months_left = self._months_inclusive(today, fy_end)
        if months_left <= 0:
            months_left = 1

        STANDARD_DEDUCTION = 75000.0
        REBATE_TAXABLE_LIMIT = 1200000.0  # taxable income threshold (after std deduction)

        for emp in self:
            if not emp.employee_ctc or emp.employee_ctc < 0:
                raise UserError(_("Employee CTC is missing or -. Please ensure employee_ctc is computed."))

            # Annual gross assumed from employee_ctc
            annual_gross = emp.employee_ctc

            # Taxable income after standard deduction
            annual_taxable = max(annual_gross - STANDARD_DEDUCTION, 0.0)

            # Compute slab tax (without cess)
            annual_tax = emp._new_regime_tax_fy_2025_26(annual_taxable)

            # Rebate => tax becomes 0 if taxable <= 12L
            if annual_taxable <= REBATE_TAXABLE_LIMIT:
                annual_tax = 0.0

            # Cess 4%
            annual_tax_total = annual_tax * 1.04

            # Monthly for remaining months
            monthly_tds = annual_tax_total / months_left

            # Update standard field
            emp.l10n_in_tds = round(monthly_tds, 2)

        return True