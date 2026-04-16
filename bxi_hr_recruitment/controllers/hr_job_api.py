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

            # 🔹 Fetch job records
            jobs = request.env['hr.job'].sudo().search_read(
                domain,
                [
                    'id',
                    'name',
                    'sequence',
                    'no_of_recruitment',
                    'description',
                    'requirements',
                    'website_published'
                ]
            )

            return {
                "status": 200,
                "count": len(jobs),
                "data": jobs
            }

        except Exception as e:
            return {
                "status": 500,
                "message": str(e)
            }