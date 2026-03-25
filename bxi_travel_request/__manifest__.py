# -*- coding: utf-8 -*-
{
    'name': 'Travel Request Management',
    'category': 'Human Resources',
    'version': '19.0.1.0.0',
    'summary': 'Manage employee travel requests in Odoo 19',
    'sequence': 1,
    'author': 'BXI',
    'license': 'LGPL-3',
    'description': 'Employee View Modification',
    'depends': [
        'base',
        'mail',
        'hr',
        'hr_expense',
        'project',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/travel_request_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
