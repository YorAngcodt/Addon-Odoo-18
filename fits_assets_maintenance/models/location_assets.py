from odoo import models, fields, api

class LocationAssets(models.Model):
    _name = 'fits.location.assets'
    _description = 'Location Assets'
    _order = 'location_code'
    _rec_name = 'location_name'

    # Location code field - manual entry
    location_code = fields.Char(
        string='Code',
        required=True,
        help='Kode lokasi dimasukkan manual oleh user'
    )

    # Location name field - user input
    location_name = fields.Char(
        string='Name',
        required=True,
        help='Nama lokasi dimasukkan manual oleh user'
    )
