from odoo import models, fields, api, _

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'


    category_id = fields.Many2one(
        'helpdesk.category',
        string='Category'
    )
    sub_category_id = fields.Many2one(
        'helpdesk.sub.category',
        string='Sub Category'
    )

    escalation_level_id = fields.Many2one(
        "helpdesk.escalation.level",
        string="Escalation Level",
        domain="[('team_id', '=', team_id)]"
    )

    escalation_assignee_ids = fields.Many2many(
        related="escalation_level_id.assignee_ids",
        string="Escalation Assignees",
        readonly=True
    )


    @api.onchange('team_id')
    def _onchange_team_id_category(self):
        self.category_id = False
        self.sub_category_id = False
        return {
            'domain': {
                'category_id': [('team_id', '=', self.team_id.id)]
            }
        }

    @api.onchange('category_id')
    def _onchange_category_id_subcategory(self):
        self.sub_category_id = False
        return {
            'domain': {
                'sub_category_id': [('category_id', '=', self.category_id.id)]
            }
        }


