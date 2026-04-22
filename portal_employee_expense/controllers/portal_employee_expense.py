<<<<<<< HEAD
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import base64



class EmployeePortalExpense(http.Controller):

    @http.route(['/my/employee-expenses'], type='http', auth='user', website=True)
    def portal_employee_expenses(self, **kwargs):
        user = request.env.user
        Expense = request.env['hr.expense'].sudo()

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        expenses = []
        if employee:
            expenses = Expense.search([
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

        # Render form (GET request)
        if not post:
            products = request.env['product.product'].sudo().search([])
            return request.render(
                'portal_employee_expense.portal_submit_expense_template',
                {'products': products}
            )

        # Handle form submission (POST)
        form = request.httprequest.form
        files = request.httprequest.files.getlist('receipt[]')

        names = form.getlist('name[]')
        product_ids = form.getlist('product_id[]')
        dates = form.getlist('date[]')
        amounts = form.getlist('total_amount[]')
        # amounts = form.getlist('amount[]')

        for name, product, date, amount in zip(names, product_ids, dates, amounts):

            if not name:
                continue

            product_id = int(product) if product else False

            expense = request.env['hr.expense'].sudo().create({
                'name': name,
                'date': date,
                'product_id': product_id,
                # 'total_amount': float(amount or 0),
                'total_amount': float(amount) if amount else 0.0,
                'employee_id': employee.id,
            })
            # (SAVE MULTIPLE FILES)
            for file in files:
                if file and file.filename:
                    file_content = file.read()
                    if file_content:
                        request.env['ir.attachment'].sudo().create({
                            'name': file.filename,
                            'datas': base64.b64encode(file_content),
                            'res_model': 'hr.expense',
                            'res_id': expense.id,
                            'mimetype': file.mimetype,
                        })
            
            if expense:
                expense.state = 'hr_approval'
                
            expense._send_state_email()  

=======
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import base64



class EmployeePortalExpense(http.Controller):

    @http.route(['/my/employee-expenses'], type='http', auth='user', website=True)
    def portal_employee_expenses(self, **kwargs):
        user = request.env.user
        Expense = request.env['hr.expense'].sudo()

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        expenses = []
        if employee:
            expenses = Expense.search([
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

        # Render form (GET request)
        if not post:
            products = request.env['product.product'].sudo().search([])
            return request.render(
                'portal_employee_expense.portal_submit_expense_template',
                {'products': products}
            )

        # Handle form submission (POST)
        form = request.httprequest.form
        files = request.httprequest.files.getlist('receipt[]')

        names = form.getlist('name[]')
        product_ids = form.getlist('product_id[]')
        dates = form.getlist('date[]')
        amounts = form.getlist('total_amount[]')
        # amounts = form.getlist('amount[]')

        for name, product, date, amount in zip(names, product_ids, dates, amounts):

            if not name:
                continue

            product_id = int(product) if product else False

            expense = request.env['hr.expense'].sudo().create({
                'name': name,
                'date': date,
                'product_id': product_id,
                # 'total_amount': float(amount or 0),
                'total_amount': float(amount) if amount else 0.0,
                'employee_id': employee.id,
            })
            # (SAVE MULTIPLE FILES)
            for file in files:
                if file and file.filename:
                    file_content = file.read()
                    if file_content:
                        request.env['ir.attachment'].sudo().create({
                            'name': file.filename,
                            'datas': base64.b64encode(file_content),
                            'res_model': 'hr.expense',
                            'res_id': expense.id,
                            'mimetype': file.mimetype,
                        })
            
            if expense:
                expense.state = 'hr_approval'

>>>>>>> b4b58eed977dae983760003d3b20de481869c20f
        return request.redirect('/my/employee-expenses')