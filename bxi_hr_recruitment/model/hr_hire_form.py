from odoo import fields, models


class HrHire(models.Model):
    _inherit = 'hr.applicant'

    father_name = fields.Char("Father Name")
   