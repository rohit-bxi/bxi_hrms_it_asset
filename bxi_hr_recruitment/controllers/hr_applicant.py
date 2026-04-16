from odoo import http
from odoo.http import request


class ApplicantCreation(http.Controller):

    def _response(self, status, message, data=None):
        return {
            "status": status,
            "message": message,
            "data": data or {}
        }

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

    # @http.route('/api/recruitment/send_selection_notification', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    # def send_selection_notification(self, **kwargs):
    #     """API to send notification for selected candidates."""
    #     try:
    #         applicant_id = kwargs.get('applicant_id')
    #
    #         if not applicant_id:
    #             return {
    #                 "status": "error",
    #                 "message": "applicant_id is required"
    #             }
    #
    #         applicant = request.env['hr.applicant'].sudo().browse(applicant_id)
    #
    #         if not applicant.exists():
    #             return {
    #                 "status": "error",
    #                 "message": "Applicant not found"
    #             }
    #
    #         # Ensure candidate is selected
    #         if not applicant.stage_id.hired_stage:
    #             return {
    #                 "status": "error",
    #                 "message": "Notification can only be sent for selected candidates"
    #             }
    #
    #         applicant._send_selection_notification()
    #
    #         return {
    #             "status": "success",
    #             "message": "Notification sent successfully",
    #             "data": {
    #                 "applicant_id": applicant.id,
    #                 "candidate_name": applicant.partner_name or applicant.name,
    #                 "job_position": applicant.job_id.name if applicant.job_id else "",
    #                 "status": "selected"
    #             }
    #         }
    #
    #     except Exception as e:
    #         return {
    #             "status": "error",
    #             "message": str(e)
    #         }