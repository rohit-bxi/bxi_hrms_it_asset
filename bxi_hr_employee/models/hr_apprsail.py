from odoo import models, fields, api


class HrEmployeeAppraisal(models.Model):
    _name = 'hr.employee.appraisal'
    _description = 'Employee Appraisal'

    employee_id = fields.Many2one(
        'hr.employee',
        required=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('released', 'Released')
    ], default='draft', tracking=True)
    employee_code = fields.Char(
        related='employee_id.employee_code',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='employee_id.company_id',
        readonly=True,
    )
    promotion_job_id = fields.Many2one(
        'hr.job',
        string="Promotion To Role"
    )
    release_date = fields.Date()
    effective_date = fields.Date()

    band = fields.Char(
        related='employee_id.role_band',
        readonly=False,
    )
     # Monthly Components
    basic_salary = fields.Float("Basic Salary")
    flexible_allowance = fields.Float("Flexible Allowance",compute="_compute_salary", readonly=1, force_save="1")

    monthly_total = fields.Float(compute="_compute_salary", store=True, tracking=True)
    annual_fixed = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Retirals
    pf = fields.Float("Provident Fund", default=21600.0, tracking=True)
    insurance = fields.Float("Medical Insurance", default=50000.0, tracking=True)
    nps = fields.Float("NPS", default=15000, tracking=True)

    retiral_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Variable
    org_bonus = fields.Float("Org Bonus", compute="_compute_bonus", tracking=True)
    performance_bonus = fields.Float("Performance Bonus", compute="_compute_bonus", tracking=True)

    variable_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    # Final CTC
    ctc_total = fields.Float(compute="_compute_salary", store=True, tracking=True)

    revenue_type = fields.Selection([
        ('revenue', 'Revenue'),
        ('simple', 'Simple'),
        ('nonrevenue', 'Non Revenue'),
    ], string="Type", default='revenue', tracking=True)


    @api.depends(
        'basic_salary', 'flexible_allowance',
        'pf', 'insurance', 'nps',
        'performance_bonus', 'org_bonus'
    )
    def _compute_salary(self):
        for rec in self:

            # Monthly Total
            rec.monthly_total = rec.basic_salary + rec.flexible_allowance

            # Annual Fixed
            rec.annual_fixed = rec.monthly_total * 12

            # Retirals
            rec.retiral_total = rec.pf + rec.insurance + rec.nps

            # Variable
            rec.variable_total = rec.performance_bonus + rec.org_bonus

            # Final CTC
            rec.ctc_total = rec.annual_fixed + rec.retiral_total + rec.variable_total
    
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


