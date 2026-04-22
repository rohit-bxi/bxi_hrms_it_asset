from odoo import http
from odoo.http import request , Controller, route


class HrJobAPI(http.Controller):

    # @http.route('/api/create/job', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    # def create_job_position(self, **kw):
    #     try:
    #         data = request.params or {}

    #         name = data.get('name')
    #         sequence = data.get('sequence')
    #         no_of_recruitment = data.get('no_of_recruitment')
    #         description = data.get('description')
    #         requirements = data.get('requirements')
    #         user_id = data.get('user_id')

    #         # Validation
    #         if not name:
    #             return {
    #                 "status": 400,
    #                 "message": "Job Position name is required"
    #             }

    #         job_vals = {
    #             "name": name,
    #             "sequence": sequence,
    #             "no_of_recruitment": no_of_recruitment,
    #             "description": description,
    #             "requirements": requirements,
    #             "user_id": user_id
    #         }

    #         job = request.env['hr.job'].sudo().create(job_vals)

    #         return {
    #             "status": 200,
    #             "message": "Job Position Created Successfully",
    #             "job_id": job.id
    #         }

    #     except Exception as e:
    #         return {
    #             "status": 500,
    #             "message": str(e)
    #         }

    @http.route('/api/jobs', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def get_job_positions(self, **kwargs):
        try:
            params = request.params or {}
            status = params.get('status')
            job_id = params.get('job_id')

            domain = []

            if job_id:
                try:
                    job_id = int(job_id)
                    domain.append(('id', '=', job_id))
                except (ValueError, TypeError):
                    return {
                        "status": 400,
                        "message": "Invalid job_id. It must be an integer."
                    }
            else:
                #  Apply status filter only when job_id is not provided
                if status:
                    status = str(status).lower().strip()

                    if status == "published":
                        domain.append(('website_published', '=', True))
                    elif status == "unpublished":
                        domain.append(('website_published', '=', False))
                    elif status == "all":
                        pass
                    else:
                        return {
                            "status": 400,
                            "message": "Invalid status. Use published, unpublished or all"
                        }

            # 🔹 Fetch base job data
            jobs = request.env['hr.job'].sudo().search(domain)

            result = []

            for job in jobs:

                # 🔹 Location names
                location_names = job.location_ids.mapped('name') if job.location_ids else []

                # 🔹 Department
                department = job.department_id.name if job.department_id else ""

                # 🔹 Hiring Manager (user_id or custom field)
                hiring_manager = job.user_id.name if hasattr(job, 'user_id') and job.user_id else ""

                # 🔹 Recruiter Assigned (if custom field exists)
                recruiter = ""
                if hasattr(job, 'recruiter_id') and job.recruiter_id:
                    recruiter = job.recruiter_id.name

                # 🔹 Candidates (hr.applicant linked to job)
                applicants = request.env['hr.applicant'].sudo().search([
                    ('job_id', '=', job.id)
                ])

                candidate_names = applicants.mapped('partner_name') if applicants else []
                candidates_selected = len(applicants.filtered(lambda a: a.stage_id and a.stage_id.fold))

                # 🔹 Build response
                result.append({
                    "id": job.id,
                    "name": job.name,
                    "sequence": job.sequence,
                    "description": job.description,
                    "requirements": job.requirements,
                    "website_published": job.website_published,

                    # 🔹 Custom fields
                    "location_type": job.location_type,
                    "employee_category": job.employee_category or "",

                    # 🔹 Job Details (mapped / computed)
                    "location": location_names,
                    "job_location": location_names,
                    "department": department,
                    "hiring_manager": hiring_manager,
                    "recruiter_assigned": recruiter,

                    # 🔹 Open positions
                    "open_positions": job.no_of_recruitment,

                    # 🔹 Requisition ID (if exists in your system)
                    "requisition_id": getattr(job, 'requisition_id', ""),

                    # 🔹 Experience (custom field assumed)
                    "experience": getattr(job, 'experience', ""),

                    # 🔹 Job Type (custom or selection field assumed)
                    "job_type": getattr(job, 'job_type', ""),

                    # 🔹 Salary (if exists)
                    "salary": getattr(job, 'salary', ""),

                    # 🔹 Billed / Unbilled (custom assumption)
                    "billed_unbilled": getattr(job, 'billed_unbilled', ""),

                    # 🔹 Candidates
                    "number_of_openings": job.no_of_recruitment,
                    "candidates_selected": candidates_selected,
                    "candidates_name": candidate_names
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
