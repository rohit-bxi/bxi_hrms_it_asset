from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import base64



class EmployeePortalExpense(http.Controller):

    @http.route(['/my/employee-expenses'], type='http', auth='user', website=True)
    def portal_employee_expenses(self, **kwargs):
        user = request.env.user

        # Restrict to portal users only
        # if not user.has_group('base.group_portal'):
        #     raise AccessError("This page is only for portal users")

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        expenses = []
        if employee:
            expenses = request.env['hr.expense'].sudo().search([
                ('employee_id', '=', employee.id)
            ])
        values = {
            'expenses': expenses,
        }
        return request.render('portal_employee_expense.portal_my_expenses_template', values)

    @http.route('/my/submit-expenses', type='http', auth="user", website=True)
    def submit_expenses(self, **post):

        user = request.env.user

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        #  IF FORM SUBMITTED
        if post:
            request.env['hr.expense'].sudo().create({
                'name': post.get('name'),
                'date': post.get('date'),
                'description': post.get('description'),
                'total_amount': float(post.get('amount') or 0),
                'employee_id': employee.id,
            })

            return request.redirect('/my/employee-expenses')

        #  OTHERWISE OPEN FORM
        return request.render('portal_employee_expense.portal_submit_expense_template')