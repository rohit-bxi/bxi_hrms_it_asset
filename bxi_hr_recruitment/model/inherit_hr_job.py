from odoo import models, fields, api

class HrJob(models.Model):
    _inherit = 'hr.job'

    location_type = fields.Selection([
        ('all', 'All Locations'),
        ('multiple', 'Select Multiple'),
        ('specific', 'Specific Location (Udaipur)')
    ], string="Location Type", default='all')

    location_ids = fields.Many2many(
        'hr.location',
        string="Job Locations"
    )

    employee_category = fields.Char(
        string="Employee Category"
    )

    resume_file = fields.Binary(
        string="Resume",
        attachment=True
    )

    resume_filename = fields.Char(
        string="File Name"
    )

    @api.onchange('location_type')
    def _onchange_location_type(self):
        if self.location_type == 'all':
            # select all locations
            locations = self.env['hr.location'].search([])
            self.location_ids = [(6, 0, locations.ids)]

        elif self.location_type == 'specific':
            # select only Udaipur
            udaipur = self.env['hr.location'].search([('name', '=', 'Udaipur')], limit=1)
            self.location_ids = [(6, 0, udaipur.ids)]

        elif self.location_type == 'multiple':
            # allow manual selection
            self.location_ids = [(5, 0, 0)]


    requisition_id = fields.Char(
        string="Requisition ID",
        copy=False,
        readonly=True,
        index=True,
        default='New'
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('requisition_id') or vals.get('requisition_id') == 'New':
                vals['requisition_id'] = sequence.next_by_code(
                    'hr.job.requisition'
                ) or 'New'
        return super().create(vals_list)

class HrJob(models.Model):
    _inherit = 'hr.job'

    location_type = fields.Selection([
        ('all', 'All Locations'),
        ('multiple', 'Select Multiple'),
        ('specific', 'Specific Location (Udaipur)')
    ], string="Location Type", default='all')

    location_ids = fields.Many2many(
        'hr.location',
        string="Job Locations"
    )

    employee_category = fields.Char(
        string="Employee Category"
    )

    @api.onchange('location_type')
    def _onchange_location_type(self):
        if self.location_type == 'all':
            # select all locations
            locations = self.env['hr.location'].search([])
            self.location_ids = [(6, 0, locations.ids)]

        elif self.location_type == 'specific':
            # select only Udaipur
            udaipur = self.env['hr.location'].search([('name', '=', 'Udaipur')], limit=1)
            self.location_ids = [(6, 0, udaipur.ids)]

        elif self.location_type == 'multiple':
            # allow manual selection
            self.location_ids = [(5, 0, 0)]


    requisition_id = fields.Char(
        string="Requisition ID",
        copy=False,
        readonly=True,
        index=True,
        default='New'
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('requisition_id') or vals.get('requisition_id') == 'New':
                vals['requisition_id'] = sequence.next_by_code(
                    'hr.job.requisition'
                ) or 'New'
        return super().create(vals_list)
