# -*- coding: utf-8 -*-
{
    'name': 'BXI HR Employee',
    'category': 'Human Resources',
    'version': '19.0.1.0.0',
    'sequence': 1,
    'author': 'BXI',
    'summary': 'Employee form customization',
    'description': 'Employee View Modification',
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_view.xml',
        'views/hr_apprsail.xml',
        'report/report.xml',
        'report/apprasail_promation_letter.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
