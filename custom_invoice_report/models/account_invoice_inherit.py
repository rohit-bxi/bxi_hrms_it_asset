from odoo import models, fields, api, _
from num2words import num2words

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_amount_in_words(self):
        for move in self:
            move.amount_total_in_words = num2words(move.amount_total, lang='en_IN').title()

    amount_total_in_words = fields.Char(compute=_get_amount_in_words)


    def action_custom_invoice_report_pdf(self):
        self.ensure_one()
        xmlid = "custom_invoice_report.action_custom_invoice_report_pdf"
        try:
            report = self.env.ref(xmlid)
        except ValueError:
            raise UserError(_(
                "Report Not Fount"))
        return report.report_action(self)
