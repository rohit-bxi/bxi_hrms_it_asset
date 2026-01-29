from odoo import models, fields, api, _
import re

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
        string="Escalation Assignees"
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

    # @api.model
    # def message_new(self, msg_dict, custom_values=None):
    #     subject = msg_dict.get("subject", "") or ""
    #     body = msg_dict.get("body", "") or ""
    #     content = subject + " " + body

    #     ticket_pattern = r"""
    #     (?i)
    #     (
    #         TKT[-\s]*\d+ |
    #         TICKET\s*(NO\.?|NUMBER)?\s*[:\-]?\s*\d+ |
    #         TICKET\s+\d+ |
    #         \b\d{3,7}\b
    #     )
    #     """

    #     match = re.search(ticket_pattern, content, re.VERBOSE)

    #     if match:
    #         raw_ref = match.group(0)

    #         number = re.findall(r"\d+", raw_ref)[0]
    #         ticket = self.search([
    #             ("name", "ilike", number)
    #         ], limit=1)

    #         if ticket:
    #             ticket.message_post(
    #                 body=body,
    #                 subject=subject,
    #                 message_type="email",
    #                 subtype_xmlid="mail.mt_comment",
    #             )
    #             return ticket

    #     return super().message_new(msg_dict, custom_values)



