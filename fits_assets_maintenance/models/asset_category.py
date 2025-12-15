from odoo import models, fields, api
import random

class AssetCategory(models.Model):
    _name = 'fits.asset.category'
    _description = 'Asset Category'
    _order = 'category_code'
    _rec_name = 'name'

    # Category code field - manual entry
    category_code = fields.Char(
        string='Code',
        required=True,
        help='Kode kategori dimasukkan manual oleh user'
    )

    # Manual name field - user input
    name = fields.Char(
        string='Name',
        required=True,
        help='Nama kategori dimasukkan manual oleh user'
    )

    # Many2one relationship to main asset
    main_asset_id = fields.Many2one('fits.main.assets', string='Main Asset', required=True)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Custom name search for Main Asset in Asset Category context"""
        if self.env.context.get('asset_category_context'):
            # In Asset Category context, search by code
            return self.env['fits.main.assets']._name_search(name, args, operator, limit, name_get_uid)
        return super(AssetCategory, self)._name_search(name, args, operator, limit, name_get_uid)

    @api.model
    def create(self, vals):
        result = super(AssetCategory, self).create(vals)
        return result

    def write(self, vals):
        # Update category code if explicitly provided
        if 'category_code' in vals and len(self) == 1:
            # Only allow updating if no main asset exists yet
            if not self.main_asset_id:
                pass  # Allow the update
            else:
                # If main asset exists, don't allow category code change
                vals.pop('category_code', None)
        return super(AssetCategory, self).write(vals)