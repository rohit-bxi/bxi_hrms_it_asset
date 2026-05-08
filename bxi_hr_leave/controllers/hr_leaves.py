from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from datetime import datetime, time

class HrLeaveAPI(http.Controller):

    @http.route('/leave/apply',type='json',auth='public',methods=['POST'],csrf=False)
    def apply_leave(self, **data):

        employee_email = data.get('employee_email')
        x_time_off_code = data.get('x_time_off_code')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        reason = data.get('reason')

        if not employee_email:
            return {
                'status': 'failed',
                'error': 'employee_email is required'
            }

        if not x_time_off_code:
            return {
                'status': 'failed',
                'error': 'x_time_off_code is required'
            }

        if not date_from or not date_to:
            return {
                'status': 'failed',
                'error': 'date_from and date_to are required'
            }

        try:

            request_date_from = datetime.strptime(
                date_from,
                '%Y-%m-%d'
            ).date()

            request_date_to = datetime.strptime(
                date_to,
                '%Y-%m-%d'
            ).date()

        except Exception as e:

            return {
                'status': 'failed',
                'error': str(e)
            }
        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', employee_email)
        ], limit=1)

        if not employee:

            return {
                'status': 'failed',
                'error': 'Employee not found'
            }
        leave_type = request.env['hr.leave.type'].sudo().search([
            ('x_time_off_code', '=', x_time_off_code)
        ], limit=1)

        if not leave_type:

            return {
                'status': 'failed',
                'error': 'Invalid leave type'
            }
        overlap_leave = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'not in', ['cancel', 'refuse']),
            ('request_date_from', '<=', request_date_to),
            ('request_date_to', '>=', request_date_from),
        ], limit=1)

        if overlap_leave:

            return {
                'status': 'failed',
                'error': (
                    f'Overlapping leave exists from '
                    f'{overlap_leave.request_date_from} '
                    f'to '
                    f'{overlap_leave.request_date_to}'
                )
            }
        datetime_from = datetime.combine(
            request_date_from,
            time.min
        )

        datetime_to = datetime.combine(
            request_date_to,
            time.max
        )

        try:
            leave = request.env['hr.leave'].sudo().with_context(
                leave_skip_state_check=True,
                tracking_disable=True,
                mail_create_nosubscribe=True,
                mail_notrack=True,
            ).create({
                'employee_id': employee.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': request_date_from,
                'request_date_to': request_date_to,
                'date_from': datetime_from,
                'date_to': datetime_to,
                'name': reason or 'Leave Request',
                'private_name': reason or 'Leave Request',
            })
            request.env.cr.execute("""
                UPDATE hr_leave
                SET state = 'confirm'
                WHERE id = %s
            """, (leave.id,))

            request.env.cr.commit()
            leave.invalidate_recordset()
            leave = request.env['hr.leave'].sudo().browse(leave.id)
            return {
                'status': 'success',
                'message': 'Leave applied successfully',
                'leave_id': leave.id,
                'employee': employee.name,
                'employee_email': employee.work_email,
                'leave_type': leave_type.name,
                'request_date_from': str(leave.request_date_from),
                'request_date_to': str(leave.request_date_to),
                'state': leave.state,
                'number_of_days': leave.number_of_days,
                'reason': leave.private_name
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }

    @http.route('/api/leave/balance',type='json',auth='public',methods=['POST'],csrf=False)
    def leave_balance(self, **kwargs):
        employee_email = kwargs.get('employee_email')
        if not employee_email:
            return {
                "status": "error",
                "message": "employee_email is required"
            }

        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', employee_email)
        ], limit=1)
        if not employee:
            return {
                "status": "error",
                "message": "Employee not found"
            }
        allocations = request.env['hr.leave.allocation'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate')
        ])
        result = []

        for allocation in allocations:
            leave_type = allocation.holiday_status_id
            allocated = allocation.number_of_days
            used_leaves = request.env[
                'hr.leave'
            ].sudo().search([
                ('employee_id', '=', employee.id),
                ('holiday_status_id', '=', leave_type.id),
                ('state', '=', 'validate')
            ])
            used = abs(sum(
                used_leaves.mapped('number_of_days')
            ))
            remaining = allocated - used
            result.append({
                "leave_type": leave_type.name,
                "time_off_code": leave_type.x_time_off_code,
                "allocated": round(allocated, 2),
                "used": round(used, 2),
                "remaining": round(remaining, 2)
            })
        return {
            "status": "success",
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_email": employee.work_email,
            "leave_balances": result
        }

    @http.route('/api/leave/history', type='json', auth='public', methods=['POST'], csrf=False)
    def leave_history(self, **kwargs):
        employee_email = kwargs.get('employee_email')
        if not employee_email:
            return {"error": "employee_email is required"}
        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', employee_email)
        ], limit=1)

        if not employee:
            return {"error": "Employee not found"}

        leaves = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id)
        ], order='id desc')
        result = []
        for leave in leaves:
            result.append({
                'leave_type': leave.holiday_status_id.name,
                'time_off_code': leave.holiday_status_id.x_time_off_code,
                'date_from': str(leave.request_date_from) if leave.request_date_from else False,
                'date_to': str(leave.request_date_to) if leave.request_date_to else False,
                'days': abs(round(leave.number_of_days, 2)),
                'state': leave.state,
            })

        return {
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_email": employee.work_email,
            "total_records": len(result),
            "leave_history": result
        }

    @http.route('/api/leave/update',type='json',auth='public',methods=['POST'],csrf=False)
    def update_leave(self, **kwargs):
        employee_email = kwargs.get('employee_email')
        x_time_off_code = kwargs.get('x_time_off_code')

        request_date_from = kwargs.get('request_date_from')
        request_date_to = kwargs.get('request_date_to')

        update_date_from = kwargs.get('update_date_from')
        update_date_to = kwargs.get('update_date_to')

        reason = kwargs.get('reason')

        if not employee_email:
            return {
                "status": "error",
                "message": "employee_email is required"
            }

        if not x_time_off_code:
            return {
                "status": "error",
                "message": "x_time_off_code is required"
            }

        if not request_date_from:
            return {
                "status": "error",
                "message": "request_date_from is required"
            }

        if not request_date_to:
            return {
                "status": "error",
                "message": "request_date_to is required"
            }

        if not update_date_from and not update_date_to and not reason:
            return {
                "status": "error",
                "message": "Nothing to update"
            }
        try:

            request_from = datetime.strptime(
                str(request_date_from),
                '%Y-%m-%d'
            ).date()

            request_to = datetime.strptime(
                str(request_date_to),
                '%Y-%m-%d'
            ).date()

            update_from = False
            update_to = False

            if update_date_from:
                update_from = datetime.strptime(
                    str(update_date_from),
                    '%Y-%m-%d'
                ).date()

            if update_date_to:
                update_to = datetime.strptime(
                    str(update_date_to),
                    '%Y-%m-%d'
                ).date()

            if update_from and update_to:
                if update_from > update_to:
                    return {
                        "status": "error",
                        "message": "update_date_from cannot be greater than update_date_to"
                    }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Date Error: {str(e)}"
            }

        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', employee_email)
        ], limit=1)

        if not employee:
            return {
                "status": "error",
                "message": "Employee not found"
            }

        leave_type = request.env['hr.leave.type'].sudo().search([
            ('x_time_off_code', '=', x_time_off_code)
        ], limit=1)

        if not leave_type:
            return {
                "status": "error",
                "message": "Time Off type not found"
            }

        leave = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type.id),
            ('request_date_from', '=', request_from),
            ('request_date_to', '=', request_to),
        ], limit=1, order='id desc')

        if not leave:

            all_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id)
            ])

            return {
                "status": "error",
                "message": "Matching leave request not found",
                "debug": {
                    "employee_id": employee.id,
                    "employee_name": employee.name,
                    "searched_from": str(request_from),
                    "searched_to": str(request_to),
                    "available_leaves": [
                        {
                            "leave_id": l.id,
                            "leave_type": l.holiday_status_id.name,
                            "from": str(l.request_date_from),
                            "to": str(l.request_date_to),
                            "state": l.state
                        }
                        for l in all_leaves
                    ]
                }
            }
        if leave.state in ['validate', 'refuse']:
            return {
                "status": "error",
                "message": "Approved or refused leave cannot be updated"
            }

        vals = {}
        if update_from:
            vals['request_date_from'] = update_from

        if update_to:
            vals['request_date_to'] = update_to

        if update_from:
            vals['date_from'] = datetime.combine(
                update_from,
                time.min
            )

        if update_to:
            vals['date_to'] = datetime.combine(
                update_to,
                time.max
            )
        if reason:
            vals['private_name'] = reason

        try:
            request.env.cr.execute("""
                UPDATE hr_leave
                SET
                    request_date_from = %s,
                    request_date_to = %s,
                    date_from = %s,
                    date_to = %s,
                    private_name = %s
                WHERE id = %s
            """, (
                vals.get('request_date_from') or leave.request_date_from,
                vals.get('request_date_to') or leave.request_date_to,
                vals.get('date_from') or leave.date_from,
                vals.get('date_to') or leave.date_to,
                vals.get('private_name') or leave.private_name,
                leave.id
            ))

            request.env.cr.commit()
            leave.invalidate_recordset()
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
        leave = request.env['hr.leave'].sudo().browse(leave.id)
        return {
            "status": "success",
            "message": "Leave updated successfully",
            "leave_id": leave.id,
            "employee_id": employee.id,
            "employee_name": employee.name,
            "employee_email": employee.work_email,
            "leave_type": leave_type.name,
            "x_time_off_code": leave_type.x_time_off_code,
            "updated_request_date_from": str(leave.request_date_from),
            "updated_request_date_to": str(leave.request_date_to),
            "updated_date_from": str(leave.date_from),
            "updated_date_to": str(leave.date_to),
            "reason": leave.private_name,
            "state": leave.state
        }
        

    @http.route('/api/leave/action',type='json',auth='public',methods=['POST'],csrf=False)
    def leave_action(self, **kwargs):
        employee_email = kwargs.get('employee_email')
        x_time_off_code = kwargs.get('x_time_off_code')

        request_date_from = kwargs.get('request_date_from')
        request_date_to = kwargs.get('request_date_to')

        action = kwargs.get('action')

        if not employee_email:
            return {
                "status": "error",
                "message": "employee_email is required"
            }

        if not x_time_off_code:
            return {
                "status": "error",
                "message": "x_time_off_code is required"
            }

        if not request_date_from:
            return {
                "status": "error",
                "message": "request_date_from is required"
            }

        if not request_date_to:
            return {
                "status": "error",
                "message": "request_date_to is required"
            }

        if action not in ['approve', 'reject']:
            return {
                "status": "error",
                "message": "action must be approve or reject"
            }
        try:

            request_from = datetime.strptime(
                str(request_date_from),
                '%Y-%m-%d'
            ).date()

            request_to = datetime.strptime(
                str(request_date_to),
                '%Y-%m-%d'
            ).date()

        except Exception as e:

            return {
                "status": "error",
                "message": f"Date Error: {str(e)}"
            }

        employee = request.env['hr.employee'].sudo().search([
            ('work_email', '=', employee_email)
        ], limit=1)

        if not employee:

            return {
                "status": "error",
                "message": "Employee not found"
            }

        leave_type = request.env['hr.leave.type'].sudo().search([
            ('x_time_off_code', '=', x_time_off_code)
        ], limit=1)

        if not leave_type:

            return {
                "status": "error",
                "message": "Time Off type not found"
            }

        leave = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('holiday_status_id', '=', leave_type.id),
            ('request_date_from', '=', request_from),
            ('request_date_to', '=', request_to),
        ], limit=1, order='id desc')

        if not leave:

            all_leaves = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id)
            ])

            return {
                "status": "error",
                "message": "Matching leave request not found",
                "debug": {
                    "employee_id": employee.id,
                    "employee_name": employee.name,
                    "searched_from": str(request_from),
                    "searched_to": str(request_to),
                    "available_leaves": [
                        {
                            "leave_id": l.id,
                            "leave_type": l.holiday_status_id.name,
                            "from": str(l.request_date_from),
                            "to": str(l.request_date_to),
                            "state": l.state
                        }
                        for l in all_leaves
                    ]
                }
            }
        if leave.state in ['validate', 'refuse']:

            return {
                "status": "error",
                "message": "Leave already processed",
                "current_state": leave.state
            }

        try:
            if action == 'approve':

                request.env.cr.execute("""
                    UPDATE hr_leave
                    SET state = 'validate'
                    WHERE id = %s
                """, (leave.id,))

                request.env.cr.commit()
            elif action == 'reject':

                request.env.cr.execute("""
                    UPDATE hr_leave
                    SET state = 'refuse'
                    WHERE id = %s
                """, (leave.id,))

                request.env.cr.commit()
            leave.invalidate_recordset()

        except Exception as e:

            return {
                "status": "error",
                "message": str(e)
            }

        leave = request.env['hr.leave'].sudo().browse(leave.id)

        return {
            "status": "success",
            "message": f"Leave {action}d successfully",
            "leave_id": leave.id,
            "employee_name": leave.employee_id.name,
            "employee_email": leave.employee_id.work_email,
            "leave_type": leave.holiday_status_id.name,
            "x_time_off_code": leave.holiday_status_id.x_time_off_code,
            "request_date_from": str(leave.request_date_from),
            "request_date_to": str(leave.request_date_to),
            "state": leave.state,
            "processed_by": "Public API"
        }