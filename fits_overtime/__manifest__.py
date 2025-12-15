{
    'name': 'Fits Overtime Management',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Overtime Request with Configuration-based Calculation',
    'description': """
Overtime Management Module
==========================

This module provides:
* Overtime configuration with OT1, OT2, OT3 time ranges
* Overtime request with automatic calculation
* Configuration-based OT breakdown calculation
* Request approval workflow
* Advanced debugging and troubleshooting tools
* Cross-day overtime support
* Configuration validation and auto-fix features
    """,
    'author': 'PT Fujicon Priangan Perdana',
    'website': 'https://www.fits.com',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/overtime_configuration_views.xml',
        'views/overtime_request_views.xml',
        'views/overtime_reporting_views.xml',
        'views/overtime_reporting_wizard_views.xml',
        'views/hr_employee_views.xml',
        'views/menu_views.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "fits_overtime/static/src/css/overtime_request.css",
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}