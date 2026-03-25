# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class HelpdeskAPI(http.Controller):

    @http.route('/api/helpdesk/create', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def create_ticket(self, **kw):
        try:
            data = request.params or {}

            # -------------------------
            # Fields from Screenshot + Description
            # -------------------------
            name = data.get('name')
            description = data.get('description')
            team_id = data.get('team_id')
            user_id = data.get('user_id')
            partner_id = data.get('partner_id')
            priority = data.get('priority')

            # -------------------------
            # Validation
            # -------------------------
            if not name:
                return {"status": 400, "message": "Subject is required"}

            # Team Validation
            if team_id:
                team = request.env['helpdesk.team'].sudo().browse(team_id)
                if not team.exists():
                    return {"status": 400, "message": "Invalid team_id"}

            # Assigned User Validation
            if user_id:
                user = request.env['res.users'].sudo().browse(user_id)
                if not user.exists():
                    return {"status": 400, "message": "Invalid user_id"}

            # Customer Validation
            if partner_id:
                partner = request.env['res.partner'].sudo().browse(partner_id)
                if not partner.exists():
                    return {"status": 400, "message": "Invalid partner_id"}

            # -------------------------
            # Prepare Values
            # -------------------------
            vals = {
                "name": name
            }

            if description:
                vals["description"] = description

            if team_id:
                vals["team_id"] = team_id

            if user_id:
                vals["user_id"] = user_id

            if partner_id:
                vals["partner_id"] = partner_id

            if priority:
                vals["priority"] = priority  # 0,1,2,3

            # -------------------------
            # Create Ticket
            # -------------------------
            ticket = request.env['helpdesk.ticket'].sudo().create(vals)

            # -------------------------
            # Response
            # -------------------------
            return {
                "status": 200,
                "message": "Ticket Created Successfully",
                "ticket_id": ticket.id,
                "ticket_name": ticket.name
            }

        except Exception as e:
            return {
                "status": 500,
                "message": str(e)
            }

    @http.route('/api/helpdesk/update', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def update_ticket(self, **kw):
        try:
            data = request.params or {}

            ticket_id = data.get('ticket_id')

            if not ticket_id:
                return {"status": 400, "message": "ticket_id is required"}

            ticket = request.env['helpdesk.ticket'].sudo().browse(ticket_id)

            if not ticket.exists():
                return {"status": 404, "message": "Ticket not found"}

            description = data.get('description')
            team_id = data.get('team_id')
            partner_id = data.get('partner_id')
            partner_email = data.get('partner_email')
            partner_phone = data.get('partner_phone')
            priority = data.get('priority')
            stage_id = data.get('stage_id')
            additional_resolution_owner_email = data.get('additional_resolution_owner')
            message = data.get('message')

            vals = {}

            # -------------------------
            # Description
            # -------------------------
            if description is not None:
                vals["description"] = description

            # -------------------------
            # Team
            # -------------------------
            if team_id:
                team = request.env['helpdesk.team'].sudo().browse(team_id)
                if not team.exists():
                    return {"status": 400, "message": "Invalid team_id"}
                vals["team_id"] = team_id

            # -------------------------
            # Customer
            # -------------------------
            if partner_id:
                partner = request.env['res.partner'].sudo().browse(partner_id)
                if not partner.exists():
                    return {"status": 400, "message": "Invalid partner_id"}
                vals["partner_id"] = partner_id

            # -------------------------
            # Email / Phone
            # -------------------------
            if partner_email is not None:
                vals["partner_email"] = partner_email

            if partner_phone is not None:
                vals["partner_phone"] = partner_phone

            # -------------------------
            # Priority
            # -------------------------
            if priority is not None:
                vals["priority"] = priority

            # -------------------------
            # Stage
            # -------------------------
            if stage_id:
                stage = request.env['helpdesk.stage'].sudo().browse(stage_id)
                if not stage.exists():
                    return {"status": 400, "message": "Invalid stage_id"}
                vals["stage_id"] = stage_id

            # -------------------------
            # Additional Resolution Owner (ROBUST)
            # -------------------------
            if additional_resolution_owner_email:

                employee = False

                #  Case 1: Find Employee directly by work email
                employee = request.env['hr.employee'].sudo().search(
                    [('work_email', '=', additional_resolution_owner_email)],
                    limit=1
                )

                #  Case 2: If not found → via User
                if not employee:
                    user = request.env['res.users'].sudo().search(
                        ['|', ('login', '=', additional_resolution_owner_email),
                         ('email', '=', additional_resolution_owner_email)],
                        limit=1
                    )

                    if user:
                        employee = request.env['hr.employee'].sudo().search(
                            [('user_id', '=', user.id)],
                            limit=1
                        )
                if not employee:
                    return {
                        "status": 400,
                        "message": "No employee found with this email"
                    }

                vals["additional_resolution_owner"] = employee.id
            # -------------------------
            # Update Ticket
            # -------------------------
            if vals:
                ticket.write(vals)

            # -------------------------
            # Send Message (Chatter)
            # -------------------------
            if message:
                ticket.message_post(
                    body=message,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )

            # -------------------------
            # Response
            # -------------------------
            return {
                "status": 200,
                "message": "Ticket Updated Successfully",
                "ticket_id": ticket.id
            }

        except Exception as e:
            return {
                "status": 500,
                "message": str(e)
            }

    @http.route('/api/helpdesk/list', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def get_ticket_list(self, **kw):
        try:
            data = request.params or {}

            domain = []

            # Optional filters
            if data.get('team_id'):
                domain.append(('team_id', '=', data.get('team_id')))

            if data.get('user_id'):
                domain.append(('user_id', '=', data.get('user_id')))

            if data.get('partner_id'):
                domain.append(('partner_id', '=', data.get('partner_id')))

            tickets = request.env['helpdesk.ticket'].sudo().search(domain)

            result = []

            for t in tickets:
                result.append({
                    "ticket_id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "team_id": t.team_id.id,
                    "team_name": t.team_id.name,
                    "user_id": t.user_id.id if t.user_id else False,
                    "user_name": t.user_id.name if t.user_id else False,
                    "partner_id": t.partner_id.id if t.partner_id else False,
                    "partner_name": t.partner_id.name if t.partner_id else False,
                    "priority": t.priority,
                    "stage": t.stage_id.name
                })

            return {
                "status": 200,
                "count": len(result),
                "data": result
            }

        except Exception as e:
            return {
                "status": 500,
                "message": str(e)
            }