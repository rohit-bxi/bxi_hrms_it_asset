from odoo import models, fields, api
from datetime import datetime


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # =====================
    # CONTRACT FIELDS
    # =====================
    contract_start_date = fields.Date("Contract Start Date")
    contract_end_date = fields.Date("Contract End Date")

    contract_tenure = fields.Integer(
        "Tenure (Years)",
        compute="_compute_tenure",
        store=True
    )

    contract_amount = fields.Float("Total Contract Amount")

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    contract_type = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('tnm', 'Time & Material')
    ], string="Contract Type")

    billing_cycle = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], default='quarterly')

    contract_status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated')
    ], default='draft')

    client_id = fields.Many2one('res.partner', string="Client")

    # =====================
    # ATTACHMENTS
    # =====================
    contract_attachment_ids = fields.Many2many(
        'ir.attachment',
        'project_contract_attachment_rel',
        'project_id',
        'attachment_id',
        string="Contract Documents"
    )

    # =====================
    # QUARTERS
    # =====================
    contract_quarter_ids = fields.One2many(
        'project.contract.quarter',
        'project_id',
        string="Quarterly Breakdown"
    )

    # =====================
    # COMPUTE TENURE
    # =====================
    @api.depends('contract_start_date', 'contract_end_date')
    def _compute_tenure(self):
        for rec in self:
            if rec.contract_start_date and rec.contract_end_date:
                start = rec.contract_start_date
                end = rec.contract_end_date

                delta_days = (end - start).days + 1  # include both start & end

                # Convert into years (float)
                rec.contract_tenure = round(delta_days / 365, 2)
            else:
                rec.contract_tenure = 0

    # =====================
    # GENERATE QUARTERS
    # =====================
    def action_generate_quarters(self):
        for rec in self:

            if not rec.contract_amount or not rec.contract_start_date or not rec.contract_end_date:
                continue

            rec.contract_quarter_ids.unlink()

            tenure = rec.contract_tenure or 1
            yearly_amount = rec.contract_amount / tenure
            quarterly_amount = yearly_amount / 4

            start_year = rec.contract_start_date.year

            for i in range(tenure):
                year = start_year + i

                for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                    self.env['project.contract.quarter'].create({
                        'project_id': rec.id,
                        'year': year,
                        'quarter': q,
                        'amount': quarterly_amount
                    })