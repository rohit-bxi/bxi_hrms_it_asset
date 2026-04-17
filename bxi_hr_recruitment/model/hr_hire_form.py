from odoo import fields, models
from odoo.exceptions import UserError
import json
import logging
import requests
import base64
import hashlib
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

    father_name = fields.Char("Father Name")
    mother_name = fields.Char("Mother Name")
    contact_number = fields.Char("Contact Number")
    aadhar_number = fields.Char("Aadhar Number")
    pan_number = fields.Char("PAN Number")
    full_address = fields.Text("Full Address")
    joining_date = fields.Date(string="Joining Date")

    # Documents
    doc_10th_id = fields.Many2many(
    'ir.attachment',
    'hr_applicant_doc_10th_rel',
    'applicant_id',
    'attachment_id',
    string="10th Marksheet"
    )

    doc_12th_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_doc_12th_rel',
        'applicant_id',
        'attachment_id',
        string="12th Marksheet"
    )

    doc_graduation_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_doc_grad_rel',
        'applicant_id',
        'attachment_id',
        string="Graduation Certificate"
    )

    doc_master_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_doc_master_rel',
        'applicant_id',
        'attachment_id',
        string="Master Degree Certificate"
        )

    form_16_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_form_16_rel',
        'applicant_id',
        'attachment_id',
        string="Form 16"
    )

    bank_statement_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_bank_stmt_rel',
        'applicant_id',
        'attachment_id',
        string="Bank Statement"
    )

    salary_slip_id = fields.Many2many(
        'ir.attachment',
        'hr_applicant_salary_slip_rel',
        'applicant_id',
        'attachment_id',
        string="Last 3 Month Salary Slip"
    )

    photograph = fields.Many2many(
        'ir.attachment',
        'hr_applicant_photo_rel',
        'applicant_id',
        'attachment_id',
        string="Photograph"
    )

    # Experience
    experience_ids = fields.One2many(
        'hr.applicant.experience',
        'applicant_id',
        string="Experience"
    )
    stage_level = fields.Integer(compute="_compute_stage_level")
    offer_letter_attachment_id = fields.Many2one('ir.attachment', string="Offer Letter Attachment")
    externals_form_token = fields.Char("External Form Token")


    def create_attachment(self, name, data, res_model, res_id):
        if not data:
            return False

        return self.env['ir.attachment'].create({
            'name': name,
            'type': 'binary',
            'datas': data,
            'res_model': res_model,
            'res_id': res_id,
        })


    def _compute_stage_level(self):
        for rec in self:
            if rec.stage_id:
                if rec.stage_id.name == 'First Interview':
                    rec.stage_level = 1
                elif rec.stage_id.name == 'Second Interview':
                    rec.stage_level = 2
                elif rec.stage_id.name == 'Final Interview':
                    rec.stage_level = 3
                elif rec.stage_id.id >= int(3):
                    rec.stage_level = 4
                else:
                    rec.stage_level = 0
            else:
                rec.stage_level = 0



    # ---------------------------------------------------------
    # OFFER LETTER ACTIONS
    # ---------------------------------------------------------
    def action_generate_offer_letter(self):
        self.ensure_one()

        if not self.partner_name:
            raise UserError(_("Please enter Full Name."))

        report = self.env.ref('bxi_hr_recruitment.action_report_offer_letter')

        # ✅ CORRECT CALL
        pdf_content, _ = report._render_qweb_pdf(report.id, res_ids=[self.id])

        attachment = self.env['ir.attachment'].create({
            'name': f'Offer Letter - {self.partner_name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        self.write({
            'offer_letter_attachment_id': attachment.id
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


    def action_view_offer_letter(self):
        self.ensure_one()

        if not self.offer_letter_attachment_id:
            raise UserError(_("Please generate the offer letter first."))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.offer_letter_attachment_id.id}?download=false',
            'target': 'new',
        }


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

    def action_send_application_form(self):
        self.ensure_one()

        if not self.email_from:
            raise UserError(_("Applicant email is missing."))

        base_url = "https://dev.careers.bxiventures.com/application-form/"

        # Generate secure token (optional for your side)
        token_string = f"{self.id}-{self.create_date}"
        token = hashlib.md5(token_string.encode()).hexdigest()

        # Store token (fix typo also)
        self.externals_form_token = token

        # ✅ FIXED URL (string values)
        url = f"{base_url}?CJM_hired=1&app=16781&token=1b98ebf3dc38d1ede2186a983ebe2d78&odoo_id={self.id}"

        # Send email
        template = self.env.ref('bxi_hr_recruitment.email_template_application_form')
        template.with_context(application_url=url).send_mail(self.id, force_send=True)

        return True


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
