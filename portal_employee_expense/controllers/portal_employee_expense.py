from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError


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
    
        names = post.getlist('expense_name[]')
        dates = post.getlist('date[]')
        amounts = post.getlist('amount[]')
        descriptions = post.getlist('description[]')
    
        for i in range(len(names)):
    
            request.env['hr.expense'].sudo().create({
    
                'name': names[i],
    
                'employee_id': employee.id,
    
                'date': dates[i],
    
                'total_amount': amounts[i],
    
                'description': descriptions[i],
    
            })
    
        return request.redirect('/my/employee-expenses')