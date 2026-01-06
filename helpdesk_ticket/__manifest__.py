{
    'name': 'BXI Helpdesk Ticket',
    'version': '19.0',
    'category': 'Helpdesk',
    'summary': 'Add Category field to Helpdesk Tickets',
    'description': """
Adds a Category selection field to Helpdesk tickets
with predefined IT-related categories.
""",
    'author': 'BXI Technology',
    'depends': ['helpdesk'],
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
    'application': False,
}
