from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    appraisal_count = fields.Integer(
        string="Performance/Bonus",
        compute="_compute_appraisal_count"
    )

    def _compute_appraisal_count(self):
        for rec in self:
            rec.appraisal_count = self.env[
                'hr.employee.appraisal'
            ].search_count([
                ('employee_id', '=', rec.id)
            ])

    def action_open_appraisals(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Performance / Bonus',
            'res_model': 'hr.employee.appraisal',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id
            },
            'target': 'current',
        }