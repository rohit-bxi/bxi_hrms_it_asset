{
    'name': 'bxi_hr_recruitment',
    'version': '1.0',
    'summary': 'API for creating job positions',
    'author': 'Kriti',
    'category': 'HR',
    'depends': ['base','hr','hr_recruitment','website','mail'],
    'data': [],
    'installable': True,
    'application': False,
    'data': [
        'security/ir.model.access.csv',
        'views/hr_hire_form.xml',
        'views/inherit_hr_job.xml',
        'views/master_hr_location.xml',
        'data/email_template.xml',
        'data/hr_job_sequence.xml',
        'data/hr_recruitment_final_stage.xml',
        'report/offer_letter_report.xml',
        'report/offer_letter_template.xml',
    ],

}