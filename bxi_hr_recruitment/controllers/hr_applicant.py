from odoo import http
from odoo.http import request
import base64
import datetime



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

            resume_file = kwargs.get('resume_file')


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

            # -----------------------------
            #  ADD RESUME (IMPORTANT BLOCK)
            # -----------------------------
            if resume_file:
                applicant_vals.update({
                    'resume_file': resume_file,

                    'resume_filename': f"Resume_{partner_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                })

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


    @http.route(
        '/api/application/submit',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def submit_application(self, **kwargs):
        try:
            # =====================================================
            # GET BASIC DATA
            # =====================================================

            # If frontend sends JSON string inside form-data
            # key name = data
            raw_data = kwargs.get('data')

            if raw_data:
                data = json.loads(raw_data)
            else:
                # fallback if fields sent directly
                data = kwargs

            odoo_id = data.get('odoo_id')

            if not odoo_id:
                return request.make_response(json.dumps({
                    "status": "error",
                    "message": "Missing odoo_id"
                }), headers=[('Content-Type', 'application/json')])

            applicant = request.env['hr.applicant'].sudo().browse(int(odoo_id))

            if not applicant.exists():
                return request.make_response(json.dumps({
                    "status": "error",
                    "message": "Invalid applicant"
                }), headers=[('Content-Type', 'application/json')])

            # =====================================================
            # BASIC FIELDS UPDATE
            # =====================================================

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

            # =====================================================
            # FILE FIELD MAPPING
            # =====================================================

            file_field_map = {
                'doc_10th': 'doc_10th_id',
                'doc_12th': 'doc_12th_id',
                'doc_graduation': 'doc_graduation_id',
                'doc_master': 'doc_master_id',
                'form_16': 'form_16_id',
                'bank_statement': 'bank_statement_id',
                'salary_slips': 'salary_slip_id',
                'photograph': 'photograph',
            }

            update_vals = {}

            # =====================================================
            # HANDLE FILE UPLOADS (multipart/form-data)
            # =====================================================

            for input_name, field_name in file_field_map.items():
                uploaded_file = request.httprequest.files.get(input_name)

                if uploaded_file:
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': uploaded_file.filename,
                        'type': 'binary',
                        'datas': base64.b64encode(uploaded_file.read()),
                        'res_model': 'hr.applicant',
                        'res_id': applicant.id,
                    })

                    update_vals[field_name] = [(4, attachment.id)]

            if update_vals:
                applicant.write(update_vals)

            # =====================================================
            # EXPERIENCE
            # =====================================================

            experience_data = data.get('experience', [])

            if isinstance(experience_data, str):
                experience_data = json.loads(experience_data)

            exp_vals = []

            for exp in experience_data:
                exp_vals.append({
                    'applicant_id': applicant.id,
                    'company_name': exp.get('company_name'),
                    'years': exp.get('years'),
                })

            if exp_vals:
                request.env['hr.applicant.experience'].sudo().create(exp_vals)

            # =====================================================
            # SUCCESS RESPONSE
            # =====================================================

            return request.make_response(json.dumps({
                "status": "success",
                "message": "Application updated successfully",
                "applicant_id": applicant.id
            }), headers=[('Content-Type', 'application/json')])

        except Exception as e:
            return request.make_response(json.dumps({
                "status": "error",
                "message": str(e)
            }), headers=[('Content-Type', 'application/json')])

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
