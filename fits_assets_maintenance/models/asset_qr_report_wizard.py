# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssetQRReportWizard(models.TransientModel):
    _name = 'fits.asset.qr.report.wizard'
    _description = 'Asset QR Code Report Wizard'

    # Checkbox selection field
    selection_mode = fields.Selection([
        ('manual', 'Manual'),
        ('category', 'Category'),
        ('all', 'All Assets')
    ], string='Selection Mode', required=True)

    # Optional date filters (used for category/all per requirements)
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    # Asset selection for manual mode
    asset_ids_manual = fields.Many2many(
        'fits.asset',
        string='Kode Asset (Manual)',
        help='Select assets to generate QR code labels for (Manual mode)',
        context={'display_field': 'serial_number_code', 'show_code': True}
    )

    # Available categories (computed field for category mode filtering options in view domain specs only - not displayed but used internally by view domains/filters when selecting categories in category mode selection)
    available_category_ids = fields.Many2many(
        'fits.asset.category',
        string='Available Categories',
        compute='_compute_available_categories',
        store=False,
        help='Available asset categories that have assets assigned (computed for view domain filtering)'
    )

    # Category selection for category mode - based on asset categories
    category_ids = fields.Many2many(
        'fits.asset.category',
        string='Asset Categories',
        help='Select asset categories to generate QR code labels for (Category mode)'
    )

    # Asset selection for all mode (computed field)
    asset_ids_all = fields.Many2many(
        'fits.asset',
        string='Selected Assets (All)',
        compute='_compute_asset_ids_all',
        help='All assets that will be included in the report (All mode)',
        context={'display_field': 'serial_number_code', 'show_code': True}
    )

    @api.depends()
    def _compute_available_categories(self):
        """Compute available categories from existing assets"""
        for record in self:
            # Get all assets that have categories assigned
            assets_with_categories = self.env['fits.asset'].search([
                ('category_id', '!=', False)
            ])

            if assets_with_categories:
                # Get unique category IDs from assets that have categories
                category_ids = assets_with_categories.mapped('category_id.id')
                record.available_category_ids = category_ids
            else:
                record.available_category_ids = False

    @api.depends('selection_mode')
    def _compute_asset_ids_all(self):
        """Compute all assets for All mode"""
        for record in self:
            if record.selection_mode == 'all':
                # Get all assets that have serial_number_code
                all_assets = self.env['fits.asset'].search([
                    ('serial_number_code', '!=', False)
                ])
                record.asset_ids_all = all_assets
            else:
                record.asset_ids_all = False

    @api.depends('selection_mode')
    def _compute_field_visibility(self):
        """Compute field visibility based on selection_mode"""
        for record in self:
            record.show_manual_field = (record.selection_mode == 'manual')
            record.show_category_field = (record.selection_mode == 'category')
            record.show_all_field = (record.selection_mode == 'all')

    show_manual_field = fields.Boolean(
        string='Show Manual Field',
        compute='_compute_field_visibility',
        store=False
    )

    show_category_field = fields.Boolean(
        string='Show Category Field',
        compute='_compute_field_visibility',
        store=False
    )

    show_all_field = fields.Boolean(
        string='Show All Field',
        compute='_compute_field_visibility',
        store=False
    )

    @api.onchange('selection_mode')
    def _onchange_selection_mode(self):
        """Handle selection mode changes"""
        if self.selection_mode == 'all':
            # Clear selected assets when switching to All mode
            self.asset_ids_manual = False
            self.category_ids = False
        elif self.selection_mode == 'manual':
            # Clear category selection when switching to manual
            self.category_ids = False
        elif self.selection_mode == 'category':
            # Clear manual selection when switching to category
            self.asset_ids_manual = False
            # Trigger category computation
            self._compute_available_categories()

    @api.model
    def create(self, vals):
        """Create method - ensure categories are computed for new records"""
        record = super().create(vals)
        # Compute available categories for the new record
        record._compute_available_categories()
        return record

    def action_print_qr_labels(self):
        """Print QR labels for selected assets"""
        if self.selection_mode == 'all':
            # All requires start and end date
            if not (self.date_start and self.date_end):
                raise UserError(_('Start Date and End Date are required for All mode.'))
            # All mode - use computed field
            # Filter by acquisition_date within range
            domain = [('serial_number_code', '!=', False),
                      ('acquisition_date', '>=', self.date_start),
                      ('acquisition_date', '<=', self.date_end)]
            assets_to_process = self.env['fits.asset'].search(domain)

            # Generate QR codes for all assets if they don't have them
            for asset in assets_to_process:
                if not asset.qr_code_image:
                    asset._compute_qr_code()

            # Return the report action for all assets
            if assets_to_process:
                return self.env.ref('fits_assets_maintenance.action_report_asset_qr_label').report_action(assets_to_process)
            else:
                # No assets available
                raise UserError(_('No assets found for the selected criteria.'))

        elif self.selection_mode == 'category':
            # Category mode - require categories
            if not self.category_ids:
                raise UserError(_('Asset Categories are required.'))
            # Date optional, apply if provided
            domain = [('category_id', 'in', self.category_ids.ids)]
            if self.date_start:
                domain.append(('acquisition_date', '>=', self.date_start))
            if self.date_end:
                domain.append(('acquisition_date', '<=', self.date_end))
            assets_to_process = self.env['fits.asset'].search(domain)

            # Generate QR codes for selected assets if they don't have them
            for asset in assets_to_process:
                if not asset.qr_code_image:
                    asset._compute_qr_code()

            # Return the report action for the selected assets
            if assets_to_process:
                return self.env.ref('fits_assets_maintenance.action_report_asset_qr_label').report_action(assets_to_process)
            else:
                raise UserError(_('No assets found for the selected criteria.'))

        elif self.selection_mode == 'manual':
            # Manual mode - require selected assets
            assets_to_process = self.asset_ids_manual
            if not assets_to_process:
                raise UserError(_('Please select at least one asset.'))

            # Ensure all selected assets have serial number codes generated
            for asset in assets_to_process:
                if not asset.serial_number_code:
                    # Try to generate code if asset has the required components
                    if asset.main_asset_selection and asset.category_id:
                        try:
                            asset.generate_code()
                        except:
                            # If generation fails, continue with other assets
                            pass

            # Generate QR codes for selected assets if they don't have them
            for asset in assets_to_process:
                if not asset.qr_code_image:
                    asset._compute_qr_code()

            # Return the report action for the selected assets
            return self.env.ref('fits_assets_maintenance.action_report_asset_qr_label').report_action(assets_to_process)
