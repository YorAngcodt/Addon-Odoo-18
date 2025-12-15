# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssetTransferReportWizard(models.TransientModel):
    _name = 'fits.asset.transfer.report.wizard'
    _description = 'Asset Transfers Report Wizard'

    selection_mode = fields.Selection([
        ('manual', 'Manual'),
        ('category', 'Category'),
        ('all', 'All Transfers'),
    ], string='Selection Mode', required=True)

    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    # Manual selection of transfer records
    transfer_ids_manual = fields.Many2many('fits.asset.transfer', string='Transfers (Manual)')

    # Category selection (via asset category)
    category_ids = fields.Many2many('fits.asset.category', string='Asset Categories')

    @api.onchange('selection_mode')
    def _onchange_selection_mode(self):
        if self.selection_mode == 'manual':
            self.category_ids = False
        elif self.selection_mode == 'category':
            self.transfer_ids_manual = False
        elif self.selection_mode == 'all':
            self.category_ids = False
            self.transfer_ids_manual = False

    def action_print_asset_transfer_report(self):
        self.ensure_one()

        model = self.env['fits.asset.transfer']

        if self.selection_mode == 'manual':
            transfers = self.transfer_ids_manual
            if not transfers:
                raise UserError(_('Please select at least one transfer record.'))
            return self.env.ref('fits_assets_maintenance.action_report_asset_transfer_detail').report_action(transfers)

        domain = []
        # Filter by date range if provided / required
        if self.selection_mode == 'category':
            if not self.category_ids:
                raise UserError(_('Asset Categories are required.'))
            if self.category_ids:
                domain.append(('asset_id.category_id', 'in', self.category_ids.ids))
            if self.date_start:
                domain.append(('transfer_date', '>=', self.date_start))
            if self.date_end:
                domain.append(('transfer_date', '<=', self.date_end))
        elif self.selection_mode == 'all':
            if not (self.date_start and self.date_end):
                raise UserError(_('Start Date and End Date are required for All mode.'))
            domain.extend([
                ('transfer_date', '>=', self.date_start),
                ('transfer_date', '<=', self.date_end),
            ])

        transfers = model.search(domain, order='transfer_date asc, id asc')
        if not transfers:
            raise UserError(_('No transfers found for the selected criteria.'))

        return self.env.ref('fits_assets_maintenance.action_report_asset_transfer_detail').report_action(transfers)
