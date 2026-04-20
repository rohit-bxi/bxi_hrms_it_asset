from odoo import fields, models
from odoo.exceptions import UserError
import json
import logging
import requests
_logger = logging.getLogger(__name__)


class HrHire(models.Model):
    _inherit = 'hr.applicant'
    _description = "HR Applicant Extension for Offer Letter"

    first_interview_remark = fields.Text(string="First Interview Remark")
    second_interview_remark = fields.Text(string="Second Interview Remark")
    final_interview_remark = fields.Text(string="Final Interview Remark")


    # OPTIONAL: prevent duplicate emails per stage
    stage_mail_sent_ids = fields.Many2many(
        'hr.recruitment.stage',
        string="Sent Stage Emails"
    )



    # frontend_webhook_url = fields.Char(
    #     string="Frontend Webhook URL",
    #     help="Webhook URL to notify the frontend when a candidate is selected."
    # )
    #
    # notification_sent = fields.Boolean(
    #     string="Notification Sent",
    #     default=False,
    #     readonly=True
    # )

    father_name = fields.Char("Father Name")
    mother_name = fields.Char("Mother Name")
    contact_number = fields.Char("Contact Number")
    aadhar_number = fields.Char("Aadhar Number")
    pan_number = fields.Char("PAN Number")
    full_address = fields.Text("Full Address")
    joining_date = fields.Date(string="Joining Date")

    # Offer Letter Status
    offer_letter_generated = fields.Boolean(
        string="Offer Letter Generated",
        default=False,
        tracking=True
    )

    # Documents
    doc_10th = fields.Binary("10th Marksheet")
    doc_12th = fields.Binary("12th Marksheet")
    doc_graduation = fields.Binary("Graduation Certificate")
    doc_master = fields.Binary("Master Degree Certificate")

    # Other Documents
    form_16 = fields.Binary("Form 16")
    bank_statement = fields.Binary("Bank Statement")
    salary_slip = fields.Binary("Last 3 Month Salary Slip")
    photograph = fields.Binary("Photograph")

    # Experience
    experience_ids = fields.One2many(
        'hr.applicant.experience',
        'applicant_id',
        string="Experience"
    )
    stage_level = fields.Integer(compute="_compute_stage_level")

    def _compute_stage_level(self):
        for rec in self:
            if rec.stage_id:
                if rec.stage_id.name == 'First Interview':
                    rec.stage_level = 1
                elif rec.stage_id.name == 'Second Interview':
                    rec.stage_level = 2
                elif rec.stage_id.name == 'Final Interview':
                    rec.stage_level = 3
                else:
                    rec.stage_level = 0
            else:
                rec.stage_level = 0

    # def _send_selection_notification(self):
    #     """Send notification to frontend for selected candidates."""
    #     for record in self:
    #         # Ensure the candidate is selected (hired)
    #         if not record.stage_id or not record.stage_id.hired_stage:
    #             raise UserError(
    #                 _("Notification can only be sent for selected candidates.")
    #             )
    #
    #         if not record.frontend_webhook_url:
    #             raise UserError(_("Please configure the Frontend Webhook URL."))
    #
    #         payload = {
    #             "applicant_id": record.id,
    #             "candidate_name": record.partner_name or record.name,
    #             "email": record.email_from,
    #             "job_position": record.job_id.name if record.job_id else "",
    #             "status": "selected",
    #         }
    #
    #         headers = {"Content-Type": "application/json"}
    #
    #         try:
    #             response = requests.post(
    #                 record.frontend_webhook_url,
    #                 data=json.dumps(payload),
    #                 headers=headers,
    #                 timeout=10
    #             )
    #
    #             if response.status_code in [200, 201]:
    #                 record.notification_sent = True
    #                 _logger.info(
    #                     "Selection notification sent for applicant ID %s",
    #                     record.id
    #                 )
    #             else:
    #                 raise UserError(
    #                     _("Failed to send notification. Response: %s")
    #                     % response.text
    #                 )
    #
    #         except Exception as e:
    #             _logger.error("Notification Error: %s", str(e))
    #             raise UserError(_("Error sending notification: %s") % str(e))
    #
    # def action_send_selection_notification(self):
    #     """Button action to send notification."""
    #     self._send_selection_notification()

    # ---------------------------------------------------------
    # OFFER LETTER ACTIONS
    # ---------------------------------------------------------
    def action_generate_offer_letter(self):
        """Generate Offer Letter"""
        self.ensure_one()
        if not self.partner_name:
            raise UserError(_("Please enter Full Name."))

        self.offer_letter_generated = True
        return self.env.ref(
            'bxi_hr_recruitment.action_report_offer_letter'
        ).report_action(self)

    def action_view_offer_letter(self):
        """View Offer Letter"""
        self.ensure_one()
        if not self.offer_letter_generated:
            raise UserError(_("Please generate the offer letter first."))
        return self.env.ref(
            'bxi_hr_recruitment.action_report_offer_letter'
        ).report_action(self)

    # SEND EMAIL ON STAGE CHANGE
    # def write(self, vals):
    #
    #     # =========================
    #     # VALIDATION BEFORE STAGE CHANGE
    #     # =========================
    #     if 'stage_id' in vals:
    #
    #         new_stage = self.env['hr.recruitment.stage'].browse(vals.get('stage_id'))
    #
    #         for rec in self:
    #
    #             if new_stage.name == 'Second Interview':
    #                 if not rec.first_interview_remark:
    #                     raise UserError(
    #                         "⚠ Please fill First Interview Feedback before moving to Second Interview."
    #                     )
    #
    #             elif new_stage.name == 'Final Interview':
    #                 if not rec.second_interview_remark:
    #                     raise UserError(
    #                         "⚠ Please fill Second Interview Feedback before moving to Final Interview."
    #                     )
    #
    #             elif new_stage.name == 'Make Proposal':
    #                 if not rec.final_interview_remark:
    #                     raise UserError(
    #                         "⚠ Please fill Final Interview Feedback before moving to Make Proposal."
    #                     )
    #
    #     # =========================
    #     # STORE OLD STAGE BEFORE WRITE
    #     # =========================
    #     old_stages = {rec.id: rec.stage_id.id for rec in self}
    #
    #     res = super().write(vals)
    #
    #     # =========================
    #     # SEND EMAIL ONLY ON VALID FORWARD MOVE
    #     # =========================
    #     if 'stage_id' in vals:
    #
    #         for rec in self:
    #
    #             old_stage_id = old_stages.get(rec.id)
    #             old_stage = self.env['hr.recruitment.stage'].browse(old_stage_id)
    #
    #             # ❌ skip backward or same stage moves
    #             if old_stage and rec.stage_id.sequence <= old_stage.sequence:
    #                 continue
    #
    #             # ❌ prevent duplicate email for same stage
    #             if rec.stage_id in rec.stage_mail_sent_ids:
    #                 continue
    #
    #             template = None
    #
    #             if rec.stage_id.name == 'Qualification':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_qualification')
    #
    #             elif rec.stage_id.name == 'First Interview':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_first_interview')
    #
    #             elif rec.stage_id.name == 'Second Interview':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_second_interview')
    #
    #             elif rec.stage_id.name == 'Final Interview':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_final_interview')
    #
    #             elif rec.stage_id.name == 'Make Proposal':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_contract_proposal')
    #
    #             elif rec.stage_id.name == 'Contract Proposal':
    #                 template = self.env.ref('bxi_hr_recruitment.email_stage_offer_letter')
    #
    #             if template:
    #                 template.send_mail(rec.id, force_send=True)
    #
    #                 # mark email sent
    #                 rec.stage_mail_sent_ids = [(4, rec.stage_id.id)]
    #
    #     return res
    def write(self, vals):

        if 'stage_id' in vals:

            new_stage = self.env['hr.recruitment.stage'].browse(vals.get('stage_id'))
            for rec in self:
                # 3️⃣ Second Interview
                if new_stage.name == 'Second Interview':
                    if not rec.first_interview_remark:
                        raise UserError("⚠ Please fill First Interview Feedback before moving to Second Interview.")

                # 4️⃣ Final Interview
                elif new_stage.name == 'Final Interview':
                    if not rec.second_interview_remark:
                        raise UserError("⚠ Please fill Second Interview Feedback before moving to Final Interview.")

                # 5️⃣ Make Proposal
                elif new_stage.name == 'Make Proposal':
                    if not rec.final_interview_remark:
                        raise UserError("⚠ Please fill Final Interview Feedback before moving to Make Proposal.")

        #  STORE OLD STAGES
        old_stages = {rec.id: rec.stage_id.id for rec in self}

        res = super().write(vals)

        if 'stage_id' in vals:

            for rec in self:

                template = None

                old_stage_id = old_stages.get(rec.id)
                old_stage = self.env['hr.recruitment.stage'].browse(old_stage_id)

                if old_stage and rec.stage_id.sequence <= old_stage.sequence:
                    continue

                # 1️⃣ Qualification
                if rec.stage_id.name == 'Qualification':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_qualification')

                # 2️⃣ First Interview
                elif rec.stage_id.name == 'First Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_first_interview')

                # 3️⃣ Second Interview
                elif rec.stage_id.name == 'Second Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_second_interview')

                # 4️⃣ Final Interview
                elif rec.stage_id.name == 'Final Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_final_interview')

                # 5️⃣ Make Proposal
                elif rec.stage_id.name == 'Make Proposal':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_contract_proposal')

                # 6️⃣ Contract Proposal
                elif rec.stage_id.name == 'Contract Proposal':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_offer_letter')

                if template:
                    template.send_mail(rec.id, force_send=True)

        return res


class HrApplicantExperience(models.Model):
    _name = 'hr.applicant.experience'
    _description = 'Applicant Experience'

    applicant_id = fields.Many2one('hr.applicant')
    company_name = fields.Many2one('res.company', string='Company Name')
    years = fields.Float("Years")
    experience_certificate = fields.Binary(
        "Experience Certificate", attachment=True
    )
    experience_certificate_filename = fields.Char()

    joining_letter = fields.Binary(
        "Joining Letter", attachment=True
    )
    joining_letter_filename = fields.Char()

    relieving_letter = fields.Binary(
        "Relieving Letter", attachment=True
    )
    relieving_letter_filename = fields.Char()

    other_certificate = fields.Binary(
        "Other Certificate", attachment=True
    )
    other_certificate_filename = fields.Char()
