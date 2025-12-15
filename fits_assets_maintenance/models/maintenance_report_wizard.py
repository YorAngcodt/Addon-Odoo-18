# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MaintenanceReportWizard(models.TransientModel):
    _name = 'fits.maintenance.report.wizard'
    _description = 'Maintenance Report Wizard'

    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    def action_print_maintenance_report(self):
        """Generate Maintenance PDF report for selected filters"""
        self.ensure_one()

        # Require both dates
        if not (self.date_start and self.date_end):
            raise UserError(_('Start Date and End Date are required.'))

        domain = [
            ('scheduled_date', '>=', self.date_start),
            ('scheduled_date', '<=', self.date_end),
        ]

        requests = self.env['fits.maintenance.request'].search(domain, order='scheduled_date asc')

        if not requests:
            raise UserError(_('No maintenance requests found for the selected criteria.'))

        # Call QWeb PDF report using maintenance requests as docs
        return self.env.ref('fits_assets_maintenance.action_report_maintenance_detail').report_action(requests)
