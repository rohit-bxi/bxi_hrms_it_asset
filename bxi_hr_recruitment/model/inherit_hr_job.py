from odoo import models, fields

class HrJob(models.Model):
    _inherit = 'hr.job'

    location_id = fields.Many2one(
        'hr.location',
        string="Job Location"
    )