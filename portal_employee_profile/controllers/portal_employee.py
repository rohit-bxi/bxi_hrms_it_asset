from odoo import http
from odoo.http import request


class EmployeePortal(http.Controller):

    def _get_employee(self):
        return request.env.user.employee_id

    @http.route(['/my/employee-profile'],type='http',auth='user',website=True)
    def employee_profile(self, **kw):
        employee = self._get_employee()
        return request.render(
            'portal_employee_profile.portal_employee_profile',
            {
                'employee': employee
            }
        )

    @http.route(['/my/employee-profile/update'], type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def employee_profile_update(self, **post):
        employee = self._get_employee()
        if not employee:
            return request.redirect('/my/employee-profile')

        vals = {}

        # ===== PRIVATE CONTACT =====
        if post.get('private_email'):
            vals['private_email'] = post.get('private_email')
        if post.get('phone'):
            vals['phone'] = post.get('phone')
        if post.get('medical_insurance_no'):
            vals['medical_insurance_no'] = post.get('medical_insurance_no')

        # ===== PERSONAL INFORMATION =====
        if post.get('name'):
            vals['name'] = post.get('name')
        if post.get('birthday'):
            vals['birthday'] = post.get('birthday')

        # ===== EMERGENCY CONTACT =====
        if post.get('emergency_contact'):
            vals['emergency_contact'] = post.get('emergency_contact')
        if post.get('l10n_in_relationship'):
            vals['l10n_in_relationship'] = post.get('l10n_in_relationship')
        if post.get('emergency_phone'):
            vals['emergency_phone'] = post.get('emergency_phone')

        # ===== CITIZENSHIP =====
        if 'is_non_resident' in post:
            vals['is_non_resident'] = True
        else:
            vals['is_non_resident'] = False
        if post.get('passport_id'):
            vals['passport_id'] = post.get('passport_id')

        # ===== FAMILY =====
        if post.get('children'):
            vals['children'] = int(post.get('children'))
        if 'disabled' in post:
            vals['disabled'] = True
        else:
            vals['disabled'] = False

        # ===== LOCATION / ADDRESS =====
        if post.get('street'):
            vals['private_street'] = post.get('street')
        if post.get('city'):
            vals['private_city'] = post.get('city')
        if post.get('zip'):
            vals['private_zip'] = post.get('zip')

        # ===== PERSONAL INFO (UAN / ESIC / PAN) =====
        if post.get('l10n_in_uan'):
            vals['l10n_in_uan'] = post.get('l10n_in_uan')
        if post.get('l10n_in_esic_number'):
            vals['l10n_in_esic_number'] = post.get('l10n_in_esic_number')
        if post.get('l10n_in_pan'):
            vals['l10n_in_pan'] = post.get('l10n_in_pan')

        if vals:
            employee.sudo().write(vals)

        return request.redirect('/?profile_updated=1')