from odoo import models, fields


class EmployeeLetterWizard(models.TransientModel):
    _name = 'employee.letter.wizard'
    _description = 'Employee Letter Wizard'

    appraisal_id = fields.Many2one(
        'hr.employee.appraisal'
    )

    def action_send(self):
        print("SEND ACTION CALLED")

    def action_download(self):
        self.ensure_one()
        xmlid = "bxi_hr_performance_bonus.action_report_employee_bonus_letter"
        try:
            report = self.env.ref(xmlid)
        except ValueError:
            raise UserError(_("Bonus Letter Report Not Found."))
        return report.report_action(self.appraisal_id)

    # def action_download(self):
    #     print("DOWNLOAD ACTION CALLED")
