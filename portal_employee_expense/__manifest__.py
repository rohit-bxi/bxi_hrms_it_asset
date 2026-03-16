# -*- coding: utf-8 -*-
{
    'name': 'Employee Portal Expenses',
    'category': 'Human Resources',
    'version': '19.0.1.0.0',
    'sequence': 1,
    'author': 'BXI',
    'summary': 'Employee Expense Submission Portal',
    'description': 'Employee Expense Submission Portal',
    'depends': [
        'hr',
        'portal',
        'website',
    ],
    'data': [
        'views/portal_expense_menu.xml',
    ],
    "assets": {
        "web.assets_frontend": [
            # "portal_employee_profile/static/src/css/portal_employee.css",
        ]
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
