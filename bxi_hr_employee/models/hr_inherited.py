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
    employee_ctc = fields.Float(string="Employee Earning (Annual)")

    def get_employee_earning(self):
        for data in self:
            data.employee_ctc = data.wage

    def _compute_monthly_tds_new_regime(self, annual_ctc):
        if not annual_ctc:
            return 0.0

        STANDARD_DEDUCTION = 75000.0
        taxable_income = max(annual_ctc - STANDARD_DEDUCTION, 0.0)

        if taxable_income <= 1200000:
            return 0.0

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
            if taxable_income <= prev:
                break
            amount = min(taxable_income, limit) - prev
            tax += amount * rate
            prev = limit

        tax = tax * 1.04

        monthly_tds = tax / 12.0

        return round(monthly_tds, 2)

    def action_calculate_l10n_in_tds_new_regime(self):
        self.get_employee_earning()
        for emp in self:
            emp.l10n_in_tds = emp._compute_monthly_tds_new_regime(emp.employee_ctc)