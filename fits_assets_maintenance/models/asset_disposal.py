# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AssetDisposal(models.Model):
    _name = 'fits.asset.disposal'
    _description = 'Asset Disposal'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    reference = fields.Char(string='Reference', readonly=True, copy=False, default='New')
    name = fields.Char(default='New', readonly=True, copy=False)
    disposal_date = fields.Date(string='Disposal Date', default=fields.Date.today)
    asset_id = fields.Many2one('fits.asset', string='Asset', required=True)

    # Asset Details (populated from selected asset)
    asset_name = fields.Char(string='Asset Name', readonly=True)
    main_asset = fields.Char(string='Main Asset', readonly=True)
    asset_category = fields.Char(string='Asset Category', readonly=True)
    serial_number = fields.Char(string='Kode Asset', readonly=True)
    location = fields.Char(string='Location Assets', readonly=True)
    acquisition_date = fields.Date(string='Acquisition Date', readonly=True)
    purchase_reference = fields.Char(string='Purchase Reference', readonly=True)
    supplier = fields.Char(string='Supplier', readonly=True)
    responsible_person = fields.Char(string='Responsible Person', readonly=True)
    asset_status = fields.Char(string='Asset Status', readonly=True)
    asset_condition = fields.Char(string='Asset Condition', readonly=True)
    disposal_method = fields.Selection([
        ('sale', 'Sale'),
        ('scrap', 'Scrap'),
        ('donation', 'Donation'),
        ('other', 'Other')
    ], string='Disposal Method', required=True)
    disposal_value = fields.Float(string='Disposal Value')
    reason = fields.Text(string='Disposal Reason')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submit'),
        ('approved', 'Approved')
    ], string='Status', default='draft')

    def _generate_disposal_reference(self):
        """Generate disposal reference number with format DISP/YYYY/XXXX"""
        current_year = fields.Date.today().year
        # Get the next sequence number for this year
        existing_disposals = self.env['fits.asset.disposal'].search([
            ('reference', '!=', 'New'),
            ('reference', 'like', f'DISP/{current_year}/%')
        ], order='reference DESC', limit=1)

        if existing_disposals:
            # Extract the number from the latest reference
            latest_ref = existing_disposals.reference
            try:
                latest_num = int(latest_ref.split('/')[-1])
                next_num = latest_num + 1
            except:
                next_num = 1
        else:
            next_num = 1

        return f'DISP/{current_year}/{next_num:04d}'

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Populate asset details when asset is selected"""
        for record in self:
            if record.asset_id:
                asset = record.asset_id
                record.asset_name = asset.asset_name or asset.name
                record.main_asset = asset.main_asset_selection.asset_name if asset.main_asset_selection else ''
                record.asset_category = asset.category_id.name if asset.category_id else ''
                record.serial_number = asset.serial_number_code
                record.location = asset.location_id.display_name if asset.location_id else \
                                 (asset.location_asset_selection.location_name if asset.location_asset_selection else '')
                record.acquisition_date = asset.acquisition_date
                record.purchase_reference = asset.purchase_reference
                record.supplier = asset.supplier_id.name if asset.supplier_id else ''
                record.responsible_person = asset.responsible_person_id.name if asset.responsible_person_id else ''
                record.asset_status = asset.status
                record.asset_condition = asset.condition
            else:
                # Clear asset details if no asset selected
                record.asset_name = ''
                record.main_asset = ''
                record.asset_category = ''
                record.serial_number = ''
                record.location = ''
                record.acquisition_date = False
                record.purchase_reference = ''
                record.supplier = ''
                record.responsible_person = ''
                record.asset_status = ''
                record.asset_condition = ''

    def action_submit(self):
        """Submit disposal for approval"""
        self.write({'state': 'submit'})

    def action_approve(self):
        """Approve disposal"""
        self.write({'state': 'approved'})

    def action_set_to_draft(self):
        """Set disposal back to draft status"""
        self.write({'state': 'draft'})

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    @api.model
    def create(self, vals):
        """Create method - generate reference number for new disposals"""
        # Generate reference number if not provided
        if not vals.get('reference') or vals.get('reference') == 'New':
            reference_number = self._generate_disposal_reference()
            vals['reference'] = reference_number
            # Also update the name field to show the reference for display
            vals['name'] = reference_number

        return super(AssetDisposal, self).create(vals)