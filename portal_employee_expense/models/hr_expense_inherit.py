from odoo import models, fields, api
from datetime import date as py_date

class HrExpense(models.Model):
    _inherit = 'hr.expense'

    reimbursement_date = fields.Date(
        string="Reimbursement Date",
        compute="_compute_reimbursement_date",
        store=True
    )

    @api.depends('date')
    def _compute_reimbursement_date(self):
        for rec in self:
            if rec.date:
                expense_date = rec.date

                # Calculate next month
                if expense_date.month == 12:
                    next_month = 1
                    year = expense_date.year + 1
                else:
                    next_month = expense_date.month + 1
                    year = expense_date.year

                # Set to 15th of next month
                rec.reimbursement_date = py_date(year, next_month, 15)
            else:
                rec.reimbursement_date = False