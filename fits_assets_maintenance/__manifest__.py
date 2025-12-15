# -*- coding: utf-8 -*-
{
    'name': 'Fits Assets  Maintenance',
    'version': '1.1',
    'summary': 'Manajemen Aset Tetap (Fixed Assets Management)',
    'description': """
        Modul ini digunakan untuk mengelola aset tetap perusahaan.
        Fitur utama:
        - Registrasi aset
        - Depresiasi otomatis
        - Maintenance aset
        - Disposal aset
        - Integrasi dengan Accounting

        Version 1.1:
        - Improved Maintenance Requests dengan field Scheduled Start dan End sebagai Date fields
    """,
    'author': 'Fits Yordan',
    'website': 'http://www.fitsdev.com',
    'category': 'Accounting/Assets',
    'depends': ['base', 'account', 'product', 'hr', 'stock', 'purchase', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/maintenance_request_cancel_security.xml',
        'data/asset_sequence.xml',
        'views/asset_qr_report_wizard_views.xml',
        'views/asset_views.xml',
        'views/main_assets_views.xml',
        'views/location_assets_views.xml',
        'views/asset_category_views.xml',
        'views/asset_transfer_views.xml',
        'views/asset_disposal_views.xml',
        'views/asset_qr_label_report.xml',
        'views/maintenance_report_wizard_views.xml',
        'views/maintenance_report_report.xml',
        # New asset and transfer reports
        'views/asset_report_wizard_views.xml',
        'views/asset_detail_report.xml',
        'views/asset_transfer_report_wizard_views.xml',
        'views/asset_transfer_detail_report.xml',
        'views/asset_dashboard_views.xml',
        'views/maintenance_views.xml',
        'views/maintenance_team_views.xml',
        'views/maintenance_calendar_views.xml',
        'wizard/maintenance_request_cancel_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
