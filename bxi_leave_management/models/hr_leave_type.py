from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    time_off_code = fields.Char(
        string="Time Off Code",
        help="Unique code for Time Off Type"
    )

    _sql_constraints = [
        ('time_off_code_unique', 'unique(time_off_code)', 'Time Off Code must be unique!')
    ]

    @api.onchange('time_off_code')
    def _onchange_time_off_code(self):
        if self.time_off_code:
            self.time_off_code = self.time_off_code.upper()