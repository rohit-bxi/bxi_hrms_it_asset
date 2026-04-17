from odoo import models, fields, api

class HrJob(models.Model):
    _inherit = 'hr.job'

    location_id = fields.Many2one(
        'hr.location',
        string="Job Location"
    )

    requisition_id = fields.Char(
        string="Requisition ID",
        copy=False,
        readonly=True,
        index=True,
        default='New'
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('requisition_id') or vals.get('requisition_id') == 'New':
                vals['requisition_id'] = sequence.next_by_code(
                    'hr.job.requisition'
                ) or 'New'
        return super().create(vals_list)