from odoo import models, fields

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    category = fields.Selection(
        selection=[
            ('workplace', 'Workplace'),
            ('cloud_infra_share', 'Cloud and Infra Share'),
            ('cyber_security_network_erp', 'Cyber Security Network and ERP'),
            ('network', 'Network'),
        ],
        string='Category',
        tracking=True
    )
