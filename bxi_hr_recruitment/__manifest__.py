{
    'name': 'bxi_hr_recruitment',
    'version': '1.0',
    'summary': 'API for creating job positions',
    'author': 'Kriti',
    'category': 'HR',
    'depends': ['base','hr','hr_recruitment','website'],
    'data': [],
    'installable': True,
    'application': False,
    'data': [
        'security/ir.model.access.csv',
        'views/hr_hire_form.xml',
    ],
}