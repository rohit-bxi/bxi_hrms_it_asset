from odoo import http
from odoo.http import request


class EmployeeAPIController(http.Controller):

    @http.route('/api/employee/details',type='json',auth='public',methods=['POST'],csrf=False)
    def get_employee_details(self, **kwargs):
        try:
            employee_email = kwargs.get('employee_email')
            if not employee_email:
                return {
                    'status': False,
                    'message': 'employee_email is required'
                }
            employee = request.env['hr.employee'].sudo().search([
                ('work_email', '=', employee_email)
            ], limit=1)
            if not employee:
                return {
                    'status': False,
                    'message': 'Employee not found'
                }
            return {
                'status': True,
                'message': 'Employee details fetched successfully',
                'data': {
                    'employee_name': employee.name or '',
                    'employee_email': employee.work_email or '',
                    'employee_number': employee.private_phone or '',
                    'employee_code': employee.employee_code or '',
                    'job_title': employee.job_id.name or '',
                    'company_name': employee.company_id.name or '',
                    'manager_name': employee.parent_id.name or '',
                    'date_of_joining': str(employee.emp_date_of_joining or ''),
                }
            }
        except Exception as e:
            return {
                'status': False,
                'message': str(e)
            }
        
    @http.route('/api/employee/document/submit',type='json',auth='public',methods=['POST'],csrf=False)
    def employee_document_submit(self, **kwargs):
        try:
            data = kwargs
            employee_id = data.get("employee_id")
            if not employee_id:
                return {
                    "status": "error",
                    "message": "Missing employee_id"
                }
            employee = request.env['hr.employee'].sudo().browse(int(employee_id))
            if not employee.exists():
                return {
                    "status": "error",
                    "message": "Employee not found."
                }
            def create_attachment(file_obj):
                if not file_obj or not file_obj.get("data"):
                    return False
                attachment = request.env['ir.attachment'].sudo().create({
                    "name": file_obj.get("name") or "file",
                    "type": "binary",
                    "datas": file_obj.get("data"),
                    "res_model": "hr.employee",
                    "res_id": employee.id,
                })
                return attachment.id
            def m2m(file_obj):
                attachment_id = create_attachment(file_obj)
                if attachment_id:
                    return [(4, attachment_id)]
                return []
            employee.write({
                "doc_10th_id": m2m(data.get("doc_10th")),
                "doc_12th_id": m2m(data.get("doc_12th")),
                "doc_graduation_id": m2m(data.get("doc_graduation")),
                "doc_master_id": m2m(data.get("doc_master")),
                "any_certificate": m2m(data.get("any_certificate")),
                "photograph": m2m(data.get("photograph")),
                "adhar_card_front": m2m(data.get("adhar_card_front")),
                "adhar_card_back": m2m(data.get("adhar_card_back")),
                "pan_number_proof": m2m(data.get("pan_number_proof")),
            })
            def create_exp_attachment(file_obj, exp_record):
                if not file_obj or not file_obj.get("data"):
                    return False
                attachment = request.env["ir.attachment"].sudo().create({
                    "name": file_obj.get("name") or "file",
                    "type": "binary",
                    "datas": file_obj.get("data"),
                    "res_model": "hr.experience.employee",
                    "res_id": exp_record.id,
                })
                return attachment.id
            
            for exp in data.get("experience", []):
                exp_record = request.env[
                    "hr.experience.employee"
                ].sudo().create({
                    "employee_id": employee.id,
                    "company_name": exp.get("company_name"),
                    "years": exp.get("years"),
                    "experience_certificate":
                        (exp.get("experience_certificate") or {}).get("data"),
                    "joining_letter":
                        (exp.get("joining_letter") or {}).get("data"),
                    "relieving_letter":
                        (exp.get("relieving_letter") or {}).get("data"),
                    "other_certificate":
                        (exp.get("other_certificate") or {}).get("data"),
                })
                bank_attachment = create_exp_attachment(
                    exp.get("bank_statement"),
                    exp_record
                )
                if bank_attachment:
                    exp_record.write({
                        "bank_statement_id": [(4, bank_attachment)]
                    })
                salary_attachment = create_exp_attachment(
                    exp.get("salary_slip"),
                    exp_record
                )
                if salary_attachment:
                    exp_record.write({
                        "salary_slip_id": [(4, salary_attachment)]
                    })
            return {
                "status": "success",
                "message": "Employee documents submitted successfully.",
                "employee_id": employee.id,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }