from odoo import fields, models


class HrHire(models.Model):
    _inherit = 'hr.applicant'

    father_name = fields.Char("Father Name")
    mother_name = fields.Char("Mother Name")
    contact_number = fields.Char("Contact Number")
    aadhar_number = fields.Char("Aadhar Number")
    pan_number = fields.Char("PAN Number")
    full_address = fields.Text("Full Address")

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


class HrApplicantExperience(models.Model):
    _name = 'hr.applicant.experience'
    _description = 'Applicant Experience'

    applicant_id = fields.Many2one('hr.applicant')
    company_name = fields.Char("Company Name")
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
