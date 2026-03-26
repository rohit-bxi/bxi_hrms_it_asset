from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError



class TravelRequest(http.Controller):

    @http.route(['/my/travel-request'], type='http', auth='user', website=True)
    def travel_request(self, **kwargs):
        user = request.env.user
        T_Request = request.env['travel.request'].sudo()
        if user.has_group('base.group_user'):
            t_request = T_Request.search([])
        else:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            t_request = []
            if employee:
                t_request = T_Request.search([
                    ('employee_id', '=', employee.id)
                ])
        values = {
            'requests': t_request,
        }
        return request.render('bxi_travel_request.bxi_travel_request_template', values)
   
    @http.route('/my/submit-travel-request', type='http', auth="user", website=True, methods=['GET', 'POST'])
    def submit_request(self, **post):
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
        
        if request.httprequest.method == 'POST':
            records = request.env['travel.request'].sudo().create({
                'name': 'New',
                'employee_id': employee.id,
                'manager_id': employee.parent_id.id if employee.parent_id else False,
                'department_id': employee.department_id.id if employee.department_id else False,
                'travel_purpose': post.get('travel_purpose'),
                'departure_date': post.get('departure_date'),
                'return_date': post.get('return_date'),
            })
            return request.redirect(f'/my/travel-request/{records.id}')
        values = {
            'employee': employee,
        }
        return request.render('bxi_travel_request.submit_travel_template', values)
    
    @http.route(['/my/travel-request/<int:rec_id>'], type='http', auth='user', website=True)
    def travel_request_detail(self, rec_id):
        record = request.env['travel.request'].sudo().browse(rec_id)
        return request.render('bxi_travel_request.travel_request_detail_template', {
            'record': record
        })