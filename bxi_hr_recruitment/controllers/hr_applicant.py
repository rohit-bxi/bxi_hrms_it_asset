from odoo import http
from odoo.http import request
import base64


class ApplicantCreation(http.Controller):

    # =========================
    # RESPONSE WRAPPER
    # =========================
    def _response(self, status, message, data=None):
        return {
            "status": status,
            "message": message,
            "data": data or {}
        }

    # =========================
    # SAFE BASE64 DECODER
    # =========================
    def safe_b64decode(self, value):
        if not value:
            return None

        try:
            if "," in value:
                value = value.split(",")[1]

            missing_padding = len(value) % 4
            if missing_padding:
                value += "=" * (4 - missing_padding)

            return base64.b64decode(value)

        except Exception:
            return None

    # =========================
    # CREATE APPLICANT
    # =========================
    @http.route('/api/applicant/create', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def create_applicant(self, **kwargs):
        try:

            partner_name = kwargs.get('partner_name')
            email = kwargs.get('email_from')
            phone = kwargs.get('partner_phone')
            job_id = kwargs.get('job_id')

            if not partner_name:
                return self._response("error", "Applicant name is required")

            job = request.env['hr.job'].sudo().browse(int(job_id)) if job_id else False

            if job_id and not job.exists():
                return self._response("error", "Invalid Job ID")

            applicant = request.env['hr.applicant'].sudo().create({
                'partner_name': partner_name,
                'email_from': email,
                'partner_phone': phone,
                'job_id': job.id if job else False,
            })

            return self._response(
                "success",
                "Applicant created successfully",
                {"applicant_id": applicant.id}
            )

        except Exception as e:
            return self._response("error", str(e))

    # =========================
    # SUBMIT / UPDATE APPLICATION
    # =========================
    @http.route('/api/application/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_application(self, **kwargs):
        try:
            data = kwargs

            odoo_id = data.get('odoo_id')
            if not odoo_id:
                return {"status": "error", "message": "Missing odoo_id"}

            applicant = request.env['hr.applicant'].sudo().browse(int(odoo_id))

            if not applicant.exists():
                return {"status": "error", "message": "Invalid applicant"}

            # =====================
            # BASIC FIELDS
            # =====================
            applicant.write({
                'partner_name': data.get('partner_name'),
                'contact_number': data.get('contact_number'),
                'email_from': data.get('email_from'),
                'father_name': data.get('father_name'),
                'mother_name': data.get('mother_name'),
                'aadhar_number': data.get('aadhar_number'),
                'pan_number': data.get('pan_number'),
                'full_address': data.get('full_address'),
                'joining_date': data.get('joining_date'),
            })

            # =====================
            # SAFE ATTACHMENT CREATOR
            # =====================
            def create_attachment(file_obj):
                if not file_obj or not file_obj.get('data'):
                    return False

                try:
                    data_b64 = file_obj.get('data')

                    return request.env['ir.attachment'].sudo().create({
                        'name': file_obj.get('name') or 'file',
                        'type': 'binary',
                        'datas': data_b64,
                        'res_model': 'hr.applicant',
                        'res_id': applicant.id,
                    }).id

                except:
                    return False

            def m2m(file_obj):
                attachment_id = create_attachment(file_obj)
                if attachment_id:
                    return [(4, attachment_id)]
                return False

            # =====================
            # DOCUMENTS (FIXED FIELD NAMES)
            # =====================
            applicant.write({
                'doc_10th_id': m2m(data.get('doc_10th')),
                'doc_12th_id': m2m(data.get('doc_12th')),
                'doc_graduation_id': m2m(data.get('doc_graduation')),
                'doc_master_id': m2m(data.get('doc_master')),

                'form_16_id': m2m(data.get('form_16')),
                'bank_statement_id': m2m(data.get('bank_statement')),
                'salary_slip_id': m2m(data.get('salary_slips')),
                'photograph': m2m(data.get('photograph')),
            })

            # =====================
            # EXPERIENCE
            # =====================
            for exp in data.get('experience', []):

                request.env['hr.applicant.experience'].sudo().create({
                    'applicant_id': applicant.id,
                    'company_name': exp.get('company_name'),
                    'years': exp.get('years'),
                })

            return {
                "status": "success",
                "message": "Application updated successfully",
                "applicant_id": applicant.id
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }