from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployeeAppraisal(models.Model):
    _name = 'hr.employee.appraisal'
    _description = 'Employee Appraisal'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        required=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('released', 'Released'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    employee_code = fields.Char(
        related='employee_id.employee_code',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='employee_id.company_id',
        readonly=True,
    )
    template_company_id = fields.Many2one(
        'res.company',
    )
    promotion_job_id = fields.Many2one(
        related='employee_id.job_id',
        string="Promotion To Role"
    )
    department_id = fields.Many2one(
        related='employee_id.department_id',
        string="Department"
    )
    release_date = fields.Date()
    effective_date = fields.Date()
    bonus_amount = fields.Integer()
    payout_month = fields.Date()

    band = fields.Char(
        related='employee_id.role_band',
        readonly=False,
    )
    letter_type = fields.Selection([
        ('bonus_letter', 'Bonus Letter'),
        ('appraisal_promotion_letter', 'Appraisal and Promotion Letter'),
        ('appraisal_letter', 'Appraisal Letter'),
        ('promotion_letter', 'Promotion Letter'),
    ], string='Letter Type')
     # Monthly Components
     
    basic_salary = fields.Float("Basic Salary")
    flexible_allowance = fields.Float(
        "Flexible Allowance",
        compute="_compute_salary",
        store=True,
        readonly=True,
        force_save=True,
        compute_sudo=True,
    )

    monthly_total = fields.Float(
        compute="_compute_salary",
        store=True,
        tracking=True,
        compute_sudo=True,
    )

    annual_fixed = fields.Float(
        compute="_compute_salary",
        store=True,
        tracking=True,
        compute_sudo=True,
    )
    pf = fields.Float("Provident Fund", default=21600.0, tracking=True) 
    insurance = fields.Float("Medical Insurance", default=50000.0, tracking=True) 
    nps = fields.Float("NPS", default=15000, tracking=True)
    performance_bonus = fields.Float("Performance Bonus", compute="_compute_bonus", tracking=True)

    retiral_total = fields.Float(
        compute="_compute_salary",
        store=True,
        tracking=True,
        compute_sudo=True,
    )
    org_bonus = fields.Float("Org Bonus", compute="_compute_bonus", tracking=True) 
    performance_bonus = fields.Float("Performance Bonus", compute="_compute_bonus", tracking=True)
    variable_total = fields.Float(
        compute="_compute_salary",
        store=True,
        tracking=True,
        compute_sudo=True,
    )

    ctc_total = fields.Float(
        compute="_compute_salary",
        store=True,
        tracking=True,
        compute_sudo=True,
    )

    revenue_type = fields.Selection([
        ('revenue', 'Revenue'),
        ('simple', 'Simple'),
        ('nonrevenue', 'Non Revenue'),
    ], string="Type", default='revenue', tracking=True)

    def action_open_letter_wizard(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Letter Actions',
            'res_model': 'employee.letter.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_appraisal_id': self.id,
            }
        }

    @api.constrains('bonus_amount')
    def _check_bonus_amount(self):
        for rec in self:
            if rec.bonus_amount <= 0:
                raise ValidationError(
                    "Bonus Amount must be greater than 0."
                )




























    @api.depends(
        'basic_salary',
        'pf',
        'insurance',
        'nps',
        'performance_bonus',
        'org_bonus'
    )
    def _compute_salary(self):
        for rec in self:

            rec.flexible_allowance = rec.basic_salary * 0.40

            rec.monthly_total = (
                rec.basic_salary +
                rec.flexible_allowance
            )

            rec.annual_fixed = rec.monthly_total * 12

            rec.retiral_total = (
                rec.pf +
                rec.insurance +
                rec.nps
            )

            rec.variable_total = (
                rec.performance_bonus +
                rec.org_bonus
            )

            rec.ctc_total = (
                rec.annual_fixed +
                rec.retiral_total +
                rec.variable_total
            )
    
    @api.depends('annual_fixed', 'retiral_total')
    def _compute_bonus(self):
        for rec in self:
            if rec.revenue_type in ['revenue','simple']:
                rec.org_bonus = (rec.annual_fixed + rec.retiral_total) * 0.10

                rec.performance_bonus = (
                    rec.annual_fixed + rec.retiral_total + rec.org_bonus
                ) * 0.10
            else:
                rec.org_bonus = (rec.annual_fixed + rec.retiral_total) * 0.25

                rec.performance_bonus = 0.00
    
    def action_release_letter(self):
        return self.env.ref(
            'bxi_hr_employee.action_report_appraisal_letter'
        ).report_action(self)
