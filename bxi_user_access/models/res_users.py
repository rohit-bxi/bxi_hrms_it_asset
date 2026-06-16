from odoo import models, fields,api

class ResUsers(models.Model):
    _inherit = 'res.users'

    vender_custmer_access = fields.Boolean(
        string="Is Vendor/Is Customer Access"
    )

    @api.constrains('group_ids')
    def _check_disjoint_groups(self):
        return
    
    @api.constrains('implied_ids', 'implied_by_ids')
    def _check_disjoint_groups(self):
        return