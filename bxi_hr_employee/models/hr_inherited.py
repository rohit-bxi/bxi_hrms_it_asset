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
    bank_ifsc = fields.Char(string="IFSC Code")
    bank_document = fields.Binary(string="Cancelled Cheque/Passbook Front Page")  
    bank_account_number = fields.Char(string="Bank Acoount Number")
    bank_name = fields.Char(string="Bank Name")
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
            data.employee_ctc = (data.wage)*12

    # def _compute_monthly_tds_new_regime(self, annual_ctc):
    #     if not annual_ctc:
    #         return 0.0

    #     STANDARD_DEDUCTION = 75000.0
    #     taxable_income = max(annual_ctc - STANDARD_DEDUCTION, 0.0)

    #     if taxable_income <= 1200000:
    #         return 0.0

    #     slabs = [
    #         (400000, 0.00),
    #         (800000, 0.05),
    #         (1200000, 0.10),
    #         (1600000, 0.15),
    #         (2000000, 0.20),
    #         (2400000, 0.25),
    #         (float("inf"), 0.30),
    #     ]

    #     tax = 0.0
    #     prev = 0.0

    #     for limit, rate in slabs:
    #         if taxable_income <= prev:
    #             break
    #         amount = min(taxable_income, limit) - prev
    #         tax += amount * rate
    #         prev = limit

    #     tax = tax * 1.04

    #     monthly_tds = tax / 12.0
    #     return round(monthly_tds, 2)

    def _compute_monthly_tds_new_regime(self, annual_ctc):

        if not annual_ctc:
            return 0.0

        STANDARD_DEDUCTION = 75000.0

        # Calculate taxable income
        taxable_income = max(annual_ctc - STANDARD_DEDUCTION, 0.0)

        # Section 87A Rebate: No tax if taxable income is up to ₹12,00,000
        if taxable_income <= 1200000:
            return 0.0

        # New Tax Regime Slabs (FY 2025-26)
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
        previous_limit = 0.0

        # Calculate tax based on slabs
        for limit, rate in slabs:
            if taxable_income > previous_limit:
                taxable_amount = min(taxable_income, limit) - previous_limit
                tax += taxable_amount * rate
                previous_limit = limit
            else:
                break

        # Apply surcharge if applicable
        surcharge = 0.0
        if taxable_income > 50000000:  # Above ₹5 Cr
            surcharge = tax * 0.37
        elif taxable_income > 20000000:  # Above ₹2 Cr
            surcharge = tax * 0.25
        elif taxable_income > 10000000:  # Above ₹1 Cr
            surcharge = tax * 0.15
        elif taxable_income > 5000000:  # Above ₹50 Lakh
            surcharge = tax * 0.10

        tax += surcharge

        # Apply Health & Education Cess (4%)
        tax *= 1.04

        annual_tax = round(tax, 2)
        monthly_tds = round(annual_tax / 12.0, 2)

        return monthly_tds

    def action_calculate_l10n_in_tds_new_regime(self):
        self.get_employee_earning()
        for emp in self:
            emp.l10n_in_tds = emp._compute_monthly_tds_new_regime(emp.employee_ctc)

    def action_open_appraisal(self):
        self.ensure_one()
        appraisal = self.env[
            'hr.employee.appraisal'
        ].search([
            ('employee_id', '=', self.id)
        ], limit=1)
        if not appraisal:
            appraisal = self.env[
                'hr.employee.appraisal'
            ].create({
                'employee_id': self.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Appraisal',
            'res_model': 'hr.employee.appraisal',
            'view_mode': 'form',
            'res_id': appraisal.id,
            'target': 'current',
        }
    
