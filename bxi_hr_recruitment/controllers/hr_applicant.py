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

            job = request.env['hr.job'].sudo().browse(job_id)

            if not job.exists():
                return self._response("error", "Invalid Job ID")

            applicant_vals = {
                'partner_name': partner_name,
                'email_from': email,
                'partner_phone': phone,
                'job_id': job_id,
            }

            applicant = request.env['hr.applicant'].sudo().create(applicant_vals)

            return self._response(
                "success",
                "Applicant created successfully",
                {
                    "applicant_id": applicant.id,
                    "partner_name": applicant.partner_name
                }
            )

        except Exception as e:
            return self._response("error", str(e))

    @http.route('/api/applicant/list', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def applicant_list(self, job_id=None):
        try:
            if not job_id:
                return {
                    "status": "error",
                    "message": "job_id is required"
                }
            job = request.env['hr.job'].sudo().browse(int(job_id))
            if not job.exists():
                return {
                    "status": "error",
                    "message": "Job position not found"
                }
            applicants = request.env['hr.applicant'].sudo().search([
                ('job_id', '=', job.id)
            ])
            result = []
            for rec in applicants:
                result.append({
                    "id": rec.id,
                    "applicant_name": rec.partner_name,
                    "email": rec.email_from,
                    "phone": rec.partner_phone,
                    "job_position": rec.job_id.name,
                })

            return {
                "status": "success",
                "message": "Applicants fetched successfully",
                "job_position": job.name,
                "total_applicants": len(result),
                "data": result
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
