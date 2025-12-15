from odoo import models, fields, api
from odoo.exceptions import ValidationError
import random

class MainAssets(models.Model):
    _name = 'fits.main.assets'
    _description = 'Main Assets'
    _order = 'asset_code'
    _rec_name = 'asset_name'

    # Informasi Dasar
    asset_name = fields.Char(string='Name', required=True)
    asset_code = fields.Char(
        string='Code',
        help='Kode asset dimasukkan manual oleh user'
    )

    # Computed combined code for display purposes
    combined_code = fields.Char(
        string='Combined Code',
        compute='_compute_combined_code',
        store=True,
        help='Kode hasil gabungan untuk keperluan tampilan'
    )

    def _compute_combined_code(self):
        """Compute combined code for display purposes"""
        for record in self:
            # Default case - not in any special context
            record.combined_code = ''

    def name_get_code(self):
        """Display only codes in many2one fields"""
        result = []
        for record in self:
            name = record.asset_code or 'No Code'
            result.append((record.id, name))
        return result

    def name_get_for_category(self):
        """Display codes for Asset Category many2one"""
        result = []
        for record in self:
            name = record.asset_code or 'No Code'
            result.append((record.id, name))
        return result

    def name_get(self):
        """Display Main Assets based on context"""
        result = []
        for record in self:
            # Check context for display preference - prioritize context over _rec_name
            if self.env.context.get('show_code'):
                # Show only code
                name = record.asset_code or 'No Code'
            elif self.env.context.get('show_name'):
                # Show only name
                name = record.asset_name or 'No Name'
            elif self.env.context.get('show_both'):
                # Show both code and name
                name = f"{record.asset_code} - {record.asset_name}" if record.asset_code and record.asset_name else (record.asset_name or record.asset_code or 'Unnamed')
            else:
                # Default: show code (since _rec_name is asset_code)
                name = record.asset_code or 'No Code'

            result.append((record.id, name))
        return result

    @api.model
    def create(self, vals):
        return super(MainAssets, self).create(vals)
