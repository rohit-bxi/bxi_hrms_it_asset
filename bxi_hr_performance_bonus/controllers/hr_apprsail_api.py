from odoo import http
from odoo.http import request


class EmployeeAppraisalAPI(http.Controller):

    @http.route('/api/employee/appraisal',type='json',auth='public',methods=['POST'], csrf=False)
    def get_employee_appraisal(self, **kwargs):
        email = kwargs.get('employee_email')
        letter_type = kwargs.get('letter_type')
        if not email:
            return {
                'status': False,
                'message': 'Employee email is required'
            }

        if not letter_type:
            return {
                'status': False,
                'message': 'Letter type is required'
            }

        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', email)
        ], limit=1)

        if not employee:
            return {
                'status': False,
                'message': 'Employee not found'
            }

        appraisal = request.env['hr.employee.appraisal'].sudo().search([
            ('employee_id', '=', employee.id),
        ], limit=1)

        if not appraisal:
            return {
                'status': False,
                'message': 'No appraisal record found'
            }

        company = appraisal.company_id
        company_address = ", ".join(filter(None, [
            company.street,
            company.street2,
            company.city,
            company.state_id.name if company.state_id else '',
            company.zip,
            company.country_id.name if company.country_id else ''
        ]))

        response = {
            'status': True,
            'employee_details': {
                'employee_name': employee.name,
                'employee_code': appraisal.employee_code,
                'employee_email': employee.work_email,
                'mobile': employee.mobile_phone,
                'department': appraisal.department_id.name if appraisal.department_id else '',
                'designation': employee.job_id.name if employee.job_id else '',
                'band': appraisal.band,
            },
            'company_details': {
                'company_name': company.name,
                'company_email': company.email,
                'company_phone': company.phone,
                'company_website': company.website,
                'company_address': company_address,
            },
            'appraisal_details': {
                'state': appraisal.state,
                'letter_type': appraisal.letter_type,
                'release_date': appraisal.release_date,
                'effective_date': appraisal.effective_date,
            }
        }

        if appraisal.letter_type == 'bonus_letter':
            response['bonus_details'] = {
                'bonus_amount': appraisal.bonus_amount,
                'payout_month': appraisal.payout_month,
            }
        if appraisal.letter_type in [
            'promotion_letter',
            'appraisal_promotion_letter'
        ]:
            response['promotion_details'] = {
                'promoted_department':
                    appraisal.promoted_department_id.name
                    if appraisal.promoted_department_id else '',
                'promoted_designation':
                    appraisal.promoted_job_id.name
                    if appraisal.promoted_job_id else '',
                'promoted_position':
                    appraisal.promoted_position,
                'promotion_to_role':
                    appraisal.promotion_job_id.name
                    if appraisal.promotion_job_id else '',
            }

        if appraisal.letter_type in [
            'appraisal_letter',
            'appraisal_promotion_letter'
        ]:

            response['salary_details'] = {
                'current_salary': {
                    'current_band': appraisal.current_band,
                    'current_basic_salary':
                        appraisal.current_basic_salary,

                    'current_flexible_allowance':
                        appraisal.current_flexible_allowance,

                    'current_monthly_total':
                        appraisal.current_monthly_total,

                    'current_annual_fixed':
                        appraisal.current_annual_fixed,

                    'current_pf':
                        appraisal.current_pf,

                    'current_insurance':
                        appraisal.current_insurance,

                    'current_nps':
                        appraisal.current_nps,

                    'current_retiral_total':
                        appraisal.current_retiral_total,

                    'current_performance_bonus':
                        appraisal.current_performance_bonus,

                    'current_org_bonus':
                        appraisal.current_org_bonus,

                    'current_variable_total':
                        appraisal.current_variable_total,

                    'current_ctc_total':
                        appraisal.current_ctc_total,
                },

                'proposed_salary': {

                    'revenue_type':
                        appraisal.revenue_type,

                    'appraisal_percentage':
                        appraisal.appraisal_percentage,

                    'basic_salary':
                        appraisal.basic_salary,

                    'flexible_allowance':
                        appraisal.flexible_allowance,

                    'monthly_total':
                        appraisal.monthly_total,

                    'annual_fixed':
                        appraisal.annual_fixed,

                    'pf':
                        appraisal.pf,

                    'insurance':
                        appraisal.insurance,

                    'nps':
                        appraisal.nps,

                    'retiral_total':
                        appraisal.retiral_total,

                    'performance_bonus':
                        appraisal.performance_bonus,

                    'performance_bonus_percentage':
                        appraisal.performance_bonus_percentage,

                    'org_bonus':
                        appraisal.org_bonus,

                    'variable_total':
                        appraisal.variable_total,

                    'ctc_total':
                        appraisal.ctc_total,
                }
            }
        return response