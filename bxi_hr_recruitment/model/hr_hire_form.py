import base64
import hashlib
from odoo import fields, models, _
from odoo import api
from odoo.exceptions import UserError
import json
import logging
import requests
from odoo.exceptions import UserError
import uuid


_logger = logging.getLogger(__name__)

class HrHire(models.Model):
    _inherit = 'hr.applicant'
    _description = "HR Applicant Extension for Offer Letter"

    first_interview_id = fields.Many2one('hr.employee',string="First Interviewer")
    second_interview_id = fields.Many2one('hr.employee',string="Second Interviewer")
    final_interview_id = fields.Many2one('hr.employee',string="Final Interviewer")
    first_interview_remark = fields.Text(string="First Interview Remark")
    second_interview_remark = fields.Text(string="Second Interview Remark")
    final_interview_remark = fields.Text(string="Final Interview Remark")
    resume_file = fields.Binary(
        string="Resume",
        attachment=True
    )

    resume_filename = fields.Char(
        string="File Name"
    )

    # OPTIONAL: prevent duplicate emails per stage
    stage_mail_sent_ids = fields.Many2many(
        'hr.recruitment.stage',
        string="Sent Stage Emails"
    )

    sign_request_id = fields.Many2one('sign.request', string="Sign Request")

    reporting_manager_id = fields.Many2one('res.users', string="Reporting Manager")
    hr_user_id = fields.Many2one('res.users', string="HR Responsible")

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

    revenue_type = fields.Selection([
        ('revenue', 'Revenue'),
        ('simple', 'Simple'),
        ('nonrevenue', 'Non Revenue'),
    ], string="Type", default='revenue', tracking=True)
    # Basic Info
    band = fields.Char("Band")

    # Monthly Components
    basic_salary = fields.Float("Basic Salary")
    flexible_allowance = fields.Float("Flexible Allowance", readonly=1, force_save="1")

    monthly_total = fields.Float(compute="_compute_salary", store=True, tracking=True)
    annual_fixed = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Retirals
    pf = fields.Float("Provident Fund", default=21600.0, tracking=True)
    insurance = fields.Float("Medical Insurance", default=50000.0, tracking=True)
    nps = fields.Float("NPS", default=15000, tracking=True)

    retiral_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Variable
    org_bonus = fields.Float("Org Bonus", compute="_compute_bonus", tracking=True)
    performance_bonus = fields.Float("Performance Bonus", compute="_compute_bonus", tracking=True)

    variable_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Final CTC
    ctc_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    location_ids = fields.Many2one(
        'hr.location',
        string="Job Location"
    )
    offer_letter_id = fields.Char(
        string="Document ID",
        readonly=True,
        copy=False
    )
    def _generate_offer_letter_id(self):
        BASE = "66c277d4-e4a-42fb-8a41-10488f7d59b67"
        self.env.cr.execute("""
            SELECT offer_letter_id
            FROM hr_applicant
            WHERE offer_letter_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
        """)
        row = self.env.cr.fetchone()

        if not row or not row[0]:
            return BASE

        last_id = row[0]
        parts = last_id.split('-')
        last_hex = parts[-1]
        new_int = int(last_hex, 16) + 1
        new_hex = format(new_int, 'x').zfill(len(last_hex))
        parts[-1] = new_hex
        return '-'.join(parts)

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
        for rec in self:
            if not rec.offer_letter_id:
                rec.offer_letter_id = rec._generate_offer_letter_id()

        if not self.partner_name:
            raise UserError("Please enter Full Name.")

        report = self.env.ref('bxi_hr_recruitment.action_report_offer_letter')

        pdf_content, _ = report._render_qweb_pdf(
            'bxi_hr_recruitment.action_report_offer_letter',
            res_ids=[self.id]
        )

        attachment = self.env['ir.attachment'].create({
            'name': f'Offer Letter - {self.partner_name}.pdf',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        self.offer_letter_attachment_id = attachment.id

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    # def action_generate_offer_letter(self):
    #     self.ensure_one()
    #
    #     if not self.partner_name:
    #         raise UserError(_("Please enter Full Name."))
    #
    #     report = self.env.ref('bxi_hr_recruitment.action_report_offer_letter')
    #
    #     pdf_content, _ = report._render_qweb_pdf(report.id, res_ids=[self.id])
    #
    #     attachment = self.env['ir.attachment'].create({
    #         'name': f'Offer Letter - {self.partner_name}.pdf',
    #         'type': 'binary',
    #         'datas': base64.b64encode(pdf_content),
    #         'res_model': self._name,
    #         'res_id': self.id,
    #         'mimetype': 'application/pdf',
    #     })
    #
    #     self.write({
    #         'offer_letter_attachment_id': attachment.id
    #     })
    #
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/{attachment.id}?download=true',
    #         'target': 'self',
    #     }


    def action_view_offer_letter(self):
        self.ensure_one()

        # Ensure latest values
        self._compute_salary()
        self._compute_bonus()

        report = self.env.ref('bxi_hr_recruitment.action_report_offer_letter')

        pdf_content, _ = report._render_qweb_pdf(
            'bxi_hr_recruitment.action_report_offer_letter',
            res_ids=[self.id]
        )
        attachment = self.env['ir.attachment'].create({
            'name': f'Offer Letter - {self.partner_name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })

        self.offer_letter_attachment_id = attachment.id

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=false',
            'target': 'self',
        }


    # def action_view_offer_letter(self):
    #     self.ensure_one()
    #
    #     if not self.offer_letter_attachment_id:
    #         raise UserError(_("Please generate the offer letter first."))
    #
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f'/web/content/{self.offer_letter_attachment_id.id}?download=false',
    #         'target': 'new',
    #     }


    def write(self, vals):
        if 'stage_id' in vals:
            new_stage = self.env['hr.recruitment.stage'].browse(vals.get('stage_id'))
            for rec in self:
                if new_stage.name == 'Second Interview':
                    if not rec.first_interview_remark:
                        raise UserError("⚠ Please fill First Interview Feedback before moving to Second Interview.")

                elif new_stage.name == 'Final Interview':
                    if not rec.second_interview_remark:
                        raise UserError("⚠ Please fill Second Interview Feedback before moving to Final Interview.")

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

                if rec.stage_id.name == 'Qualification':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_qualification')

                elif rec.stage_id.name == 'First Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_first_interview')

                elif rec.stage_id.name == 'Second Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_second_interview')

                elif rec.stage_id.name == 'Final Interview':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_final_interview')

                elif rec.stage_id.name == 'Make Proposal':
                    template = self.env.ref('bxi_hr_recruitment.email_stage_contract_proposal')

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
        # url = f"{base_url}?CJM_hired=1&app=16781&token=1b98ebf3dc38d1ede2186a983ebe2d78&odoo_id={self.id}"
        url = f"{base_url}?CJM_hired=1&odoo_id={self.id}"
        # Send email
        template = self.env.ref('bxi_hr_recruitment.email_template_application_form')
        template.with_context(application_url=url).send_mail(self.id, force_send=True)

        return True

    @api.onchange('basic_salary')
    def onchange_basic_salary(self):
        for data in self:
            if data.basic_salary:
                data.flexible_allowance = data.basic_salary * 0.70

    @api.depends('annual_fixed', 'retiral_total')
    def _compute_bonus(self):
        for rec in self:
            if rec.revenue_type in ['revenue','simple']:
                rec.org_bonus = (rec.annual_fixed + rec.retiral_total) * 0.10

                rec.performance_bonus = (
                    rec.annual_fixed + rec.retiral_total + rec.org_bonus
                ) * 0.10
            else:
                rec.org_bonus = (rec.annual_fixed + rec.retiral_total) * 0.25

                rec.performance_bonus = 0.00

    @api.depends(
        'basic_salary', 'flexible_allowance',
        'pf', 'insurance', 'nps',
        'performance_bonus', 'org_bonus'
    )
    def _compute_salary(self):
        for rec in self:

            # Monthly Total
            rec.monthly_total = rec.basic_salary + rec.flexible_allowance

            # Annual Fixed
            rec.annual_fixed = rec.monthly_total * 12

            # Retirals
            rec.retiral_total = rec.pf + rec.insurance + rec.nps

            # Variable
            rec.variable_total = rec.performance_bonus + rec.org_bonus

            # Final CTC
            rec.ctc_total = rec.annual_fixed + rec.retiral_total + rec.variable_total

    @api.onchange('performance_bonus')
    def onchange_performance_bonus(self):
        for data in self:
            if data.performance_bonus:
                data.variable_total = data.performance_bonus + data.org_bonus
                data.ctc_total = data.annual_fixed + data.retiral_total + data.variable_total


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
