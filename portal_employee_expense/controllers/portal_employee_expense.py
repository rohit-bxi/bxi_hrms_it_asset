from odoo import http
from odoo.http import request


class EmployeePortalExpense(http.Controller):

    def _get_employee(self):
        return request.env.user.employee_id