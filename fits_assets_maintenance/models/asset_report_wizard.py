# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssetReportWizard(models.TransientModel):
    _name = 'fits.asset.report.wizard'
    _description = 'Asset Report Wizard'

    selection_mode = fields.Selection([
            ('category', 'Category'),
            ('all', 'All Assets'),
        ], string='Selection Mode')


    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    category_ids = fields.Many2many('fits.asset.category', string='Asset Categories')

    @api.onchange('selection_mode')
    def _onchange_selection_mode(self):
        if self.selection_mode == 'all':
            self.category_ids = False

    def action_print_asset_report(self):
        self.ensure_one()
        domain = []

        if self.selection_mode == 'category':
            if not self.category_ids:
                raise UserError(_('Please select at least one category.'))
            domain.append(('category_id', 'in', self.category_ids.ids))
            if self.date_start:
                domain.append(('acquisition_date', '>=', self.date_start))
            if self.date_end:
                domain.append(('acquisition_date', '<=', self.date_end))
        elif self.selection_mode == 'all':
            if not (self.date_start and self.date_end):
                raise UserError(_('Start Date and End Date are required for All mode.'))
            domain.extend([
                ('acquisition_date', '>=', self.date_start),
                ('acquisition_date', '<=', self.date_end),
            ])

        assets = self.env['fits.asset'].search(domain, order='acquisition_date asc, id asc')
        if not assets:
            raise UserError(_('No assets found for the selected criteria.'))

        return self.env.ref('fits_assets_maintenance.action_report_asset_detail').report_action(assets)
