from odoo import models, fields


class ProjectContractQuarter(models.Model):
    _name = 'project.contract.quarter'
    _description = 'Contract Quarterly Breakdown'

    project_id = fields.Many2one('project.project', ondelete='cascade')

    year = fields.Integer("Year")

    quarter = fields.Selection([
        ('Q1', 'Q1'),
        ('Q2', 'Q2'),
        ('Q3', 'Q3'),
        ('Q4', 'Q4'),
    ], string="Quarter")

    amount = fields.Float("Amount")