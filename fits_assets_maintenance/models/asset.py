# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import io
import re
from datetime import timedelta
try:
    import qrcode
except ImportError:
    qrcode = None


class Asset(models.Model):
    _name = 'fits.asset'
    _description = 'Fixed Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    
    # Field to check user permissions
    can_edit_maintenance = fields.Boolean(
        string='Can Edit Maintenance',
        compute='_compute_can_edit_maintenance',
        help='Technical field to check if user can edit maintenance fields'
    )

    # Asset name as Char field (user input) - Identitas Aset manual input oleh user
    asset_name = fields.Char(string='Asset Name', required=True, help='Nama asset - field manual input untuk identitas aset')

    # Many2one field for selecting main asset - will auto-populate other fields
    main_asset_selection = fields.Many2one('fits.main.assets', string='Main Asset',
                                         help='Pilih main asset - akan mengisi otomatis kategori dan identitas aset')

    category_id = fields.Many2one('fits.asset.category', string='Asset Category', required=True,
                                help='Kategori asset - akan diisi otomatis dari Main Asset')

    # Computed domain field for category_id filtering
    category_domain = fields.Char(compute='_compute_category_domain', store=False)

    # Serial Number Code - user can generate this
    serial_number_code = fields.Char(string='Serial Number Code', 
                                   help='Kode Asset yang digenerate dari Main Asset, Asset Category, dan Location Asset dengan format: [MainAssetCode][CategoryCode][LocationCode][Counter] (4 digit: 0001, 0002, 0003, ...)')
    # Location Assets - user can select manually or it will be auto-filled based on asset_name
    location_asset_selection = fields.Many2one('fits.location.assets', string='Location Assets', required=True,
                                             help='Pilih Location Assets - akan diisi otomatis berdasarkan Asset Name jika ada yang cocok',
                                             domain=[('location_name', '!=', False)])
    
    # Maintenance Team
    maintenance_team_id = fields.Many2one(
        'fits.maintenance.team',
        string='Maintenance Team',
        help='Tim maintenance yang bertanggung jawab atas aset ini'
    )
    
    # Domain untuk maintenance_team_id berdasarkan role user
    @api.model
    def _get_maintenance_team_domain(self):
        """Mendapatkan domain untuk maintenance_team_id berdasarkan role user"""
        if self.env.user.has_group('fits_assets_maintenance.group_fits_asset_maintenance_manager'):
            return []  # Manager bisa lihat semua tim
        elif self.env.user.has_group('fits_assets_maintenance.group_fits_maintenance_team'):
            # Hanya tampilkan tim dimana user tersebut adalah anggota
            team_ids = self.env['fits.maintenance.team'].search([
                ('member_ids.user_id', '=', self.env.user.id)
            ]).ids
            return [('id', 'in', team_ids)]
        return [('id', '=', -1)]  # Default: tidak menampilkan tim apapun

    # Unique counter for this asset record - assigned once and reused
    unique_counter = fields.Integer(string='Unique Counter', copy=False, readonly=True,
                                   help='Unique counter assigned to this asset record')

    def _get_next_unique_counter(self):
        """Get the next available unique counter for new assets - unlimited growth"""
        # Find the highest existing counter across all assets using unique_counter field first,
        # then fall back to extracting from serial_number_code for backward compatibility
        max_counter = 0

        # First, try to get the highest unique_counter value
        highest_counter_asset = self.env['fits.asset'].search([
            ('unique_counter', '>', 0)
        ], order='unique_counter DESC', limit=1)

        if highest_counter_asset and highest_counter_asset.unique_counter:
            max_counter = highest_counter_asset.unique_counter
        else:
            # Fallback: extract from serial_number_code for existing records
            existing_assets = self.env['fits.asset'].search([
                ('serial_number_code', '!=', False)
            ], order='serial_number_code DESC', limit=1)

            if existing_assets and existing_assets.serial_number_code:
                # Extract counter from the highest existing code
                highest_code = existing_assets.serial_number_code
                # Find the last 4 digits (counter part)
                counter_match = re.search(r'\d{4}$', highest_code)
                if counter_match:
                    try:
                        max_counter = int(counter_match.group())
                    except:
                        max_counter = 0

        # Return next counter (unlimited growth)
        return max_counter + 1

    @api.depends()
    def _compute_can_edit_maintenance(self):
        """Compute if current user can edit maintenance fields"""
        is_team = self.env.user.has_group('fits_assets_maintenance.group_fits_maintenance_team')
        is_manager = self.env.user.has_group('fits_assets_maintenance.group_fits_asset_maintenance_manager')
        for record in self:
            record.can_edit_maintenance = is_team or is_manager

    @api.depends('main_asset_selection')
    def _compute_category_domain(self):
        """Compute domain for category_id field based on main_asset_selection"""
        for record in self:
            if record.main_asset_selection:
                # Filter categories for the selected Main Asset
                main_asset_id = record.main_asset_selection.id
                domain = [('main_asset_id', '=', main_asset_id)]

                # Check if categories exist
                category_count = record.env['fits.asset.category'].search_count(domain)

                if category_count > 0:
                    # Categories exist - use the filtering domain
                    record.category_domain = str(domain)
                    print(f"DEBUG: Setting category domain for Main Asset {record.main_asset_selection.display_name}: {domain}")
                else:
                    # No categories found - show empty
                    record.category_domain = str([('id', '=', False)])
                    print(f"DEBUG: No categories found for Main Asset {record.main_asset_selection.display_name}")
            else:
                # No Main Asset selected - show empty
                record.category_domain = str([('id', '=', False)])
                print("DEBUG: No Main Asset selected - category domain set to empty")
    qr_code_image = fields.Binary(string='QR Code', compute='_compute_qr_code', store=True,
                                 help='QR Code dari serial number dan location asset')
    
    # Informasi Perolehan
    acquisition_date = fields.Date(string='Acquisition Date')
    purchase_reference = fields.Many2one('purchase.order', string='Purchase Reference (PO/Invoice)',
                                       domain=[('state', 'in', ['purchase', 'done'])])
    supplier_id = fields.Many2one('res.partner', string='Supplier / Vendor', 
                                related='purchase_reference.partner_id', store=True, readonly=True)
    acquisition_cost = fields.Float(string='Acquisition Cost')
    
    # Garansi (Warranty)
    warranty_start_date = fields.Date(string='Warranty Start Date')
    warranty_end_date = fields.Date(string='Warranty End Date')
    warranty_provider = fields.Char(string='Warranty Provider')
    warranty_notes = fields.Text(string='Warranty Notes')
    
    # Lokasi & Penanggung Jawab
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Department / Cost Center')
    responsible_person_id = fields.Many2one('hr.employee', string='Responsible Person')
    

    
    # Status & Kondisi
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'In Maintenance')
    ], string='Status Asset', default='draft')
    condition = fields.Selection([
        ('new', 'Baru'),
        ('good', 'Baik'),
        ('minor_damage', 'Rusak Ringan'),
        ('major_damage', 'Rusak Berat')
    ], string='Condition', default='new')
    maintenance_required = fields.Boolean(string='Maintenance Required', default=False)

    # Recurrence fields for scheduled maintenance
    recurrence_pattern = fields.Selection([
        ('none', 'No Recurrence'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], string='Recurrence Pattern', default='none')

    recurrence_start_date = fields.Date(string='Recurrence Start Date')

    recurrence_interval = fields.Integer(string='Recurrence Interval', default=1,
                                       help='Interval for recurrence (e.g., every 2 weeks)')

    recurrence_end_date = fields.Date(string='Recurrence End Date')

    next_maintenance_date = fields.Date(string='Next Maintenance Date', compute='_compute_next_maintenance')
    
    # Dokumentasi
    image_1920 = fields.Binary(string='Foto Aset', attachment=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    notes = fields.Text(string='Notes / Description')
    # Chatter fields
    message_follower_ids = fields.Many2many('res.users', string='Followers')
    
    @api.depends('asset_name', 'serial_number_code')
    def _compute_name(self):
        """Compute display name from asset name or serial number code"""
        for record in self:
            if record.asset_name:
                record.name = record.asset_name
            elif record.serial_number_code:
                record.name = record.serial_number_code
            else:
                record.name = 'Unnamed Asset'

    @api.depends('recurrence_start_date', 'recurrence_pattern', 'recurrence_interval', 'recurrence_end_date', 'status')
    def _compute_next_maintenance(self):
        """Compute next maintenance date based on recurrence settings"""
        for record in self:
            # Only compute next maintenance date if status is 'maintenance' and has basic settings
            if record.status == 'maintenance' and record.recurrence_pattern != 'none' and record.recurrence_start_date:

                base_date = record.recurrence_start_date

                # Mode 1: Calculate using End Date + Pattern (when end date is set, ignore interval)
                if record.recurrence_end_date and not record.recurrence_interval:
                    # Calculate next maintenance date based on pattern from start date towards end date
                    if record.recurrence_pattern == 'daily':
                        # For daily: next day from start date, but not beyond end date
                        next_date = base_date + timedelta(days=1)
                        record.next_maintenance_date = min(next_date, record.recurrence_end_date)
                    elif record.recurrence_pattern == 'weekly':
                        # For weekly: next week from start date, but not beyond end date
                        next_date = base_date + timedelta(weeks=1)
                        record.next_maintenance_date = min(next_date, record.recurrence_end_date)
                    elif record.recurrence_pattern == 'monthly':
                        # For monthly: next month from start date, but not beyond end date
                        next_date = base_date
                        try:
                            next_date = next_date.replace(month=next_date.month + 1)
                            record.next_maintenance_date = min(next_date, record.recurrence_end_date)
                        except ValueError:
                            # Handle month overflow (e.g., Dec + 1 month = Jan next year)
                            record.next_maintenance_date = record.recurrence_end_date
                    elif record.recurrence_pattern == 'yearly':
                        # For yearly: next year from start date, but not beyond end date
                        next_date = base_date
                        try:
                            next_date = next_date.replace(year=next_date.year + 1)
                            record.next_maintenance_date = min(next_date, record.recurrence_end_date)
                        except ValueError:
                            # Handle year overflow
                            record.next_maintenance_date = record.recurrence_end_date
                    else:
                        record.next_maintenance_date = base_date

                # Mode 2: Calculate using Interval (when interval is set, ignore end date)
                elif record.recurrence_interval and not record.recurrence_end_date:
                    # Calculate using interval regardless of pattern
                    if record.recurrence_pattern == 'daily':
                        record.next_maintenance_date = base_date + timedelta(days=record.recurrence_interval)
                    elif record.recurrence_pattern == 'weekly':
                        record.next_maintenance_date = base_date + timedelta(weeks=record.recurrence_interval)
                    elif record.recurrence_pattern == 'monthly':
                        next_date = base_date
                        try:
                            record.next_maintenance_date = next_date.replace(month=next_date.month + record.recurrence_interval)
                        except ValueError:
                            # Handle month overflow
                            record.next_maintenance_date = next_date.replace(year=next_date.year + 1, month=1)
                    elif record.recurrence_pattern == 'yearly':
                        next_date = base_date
                        try:
                            record.next_maintenance_date = next_date.replace(year=next_date.year + record.recurrence_interval)
                        except ValueError:
                            # Handle year overflow
                            record.next_maintenance_date = next_date.replace(year=next_date.year + record.recurrence_interval)
                    else:
                        record.next_maintenance_date = base_date + timedelta(days=record.recurrence_interval)
                else:
                    # If both are set or neither is set, use start date as fallback
                    record.next_maintenance_date = base_date
            else:
                record.next_maintenance_date = False

    @api.depends('main_asset_selection')
    def _compute_category_id(self):
        """Removed auto-fill functionality for Asset Category"""
        # Auto-fill has been disabled as requested
        # Users will manually select Asset Category from filtered options
        pass

    @api.depends('asset_name')
    def _compute_location_asset_selection(self):
        """Compute location asset from asset name"""
        for record in self:
            if record.asset_name:
                # Find Location Asset by name that matches the asset name
                location_asset = self.env['fits.location.assets'].search([
                    ('location_name', '=', record.asset_name)
                ], limit=1)
                if location_asset:
                    record.location_asset_selection = location_asset.id
            else:
                record.location_asset_selection = False

    def generate_code(self):
        """Generate unique asset code for assets"""
        for record in self:
            code_parts = []

            # Add Main Asset code if available
            if record.main_asset_selection and record.main_asset_selection.asset_code:
                code_parts.append(record.main_asset_selection.asset_code)

            # Add Asset Category code if available
            if record.category_id and record.category_id.category_code:
                code_parts.append(record.category_id.category_code)

            # Add Location Asset code if available
            if record.location_asset_selection and record.location_asset_selection.location_code:
                code_parts.append(record.location_asset_selection.location_code)

            if code_parts:
                combined_code = ''.join(code_parts)

                # Get or assign unique counter for this record
                if not record.unique_counter:
                    # First time generating code for this record - assign a new unique counter
                    record.unique_counter = self._get_next_unique_counter()

                # Ensure we have a valid counter
                if record.unique_counter <= 0:
                    record.unique_counter = self._get_next_unique_counter()

                # Use the assigned unique counter (formatted as 4 digits with leading zeros)
                unique_code_formatted = f"{record.unique_counter:04d}"

                # Set the complete asset code
                record.serial_number_code = combined_code + unique_code_formatted
            else:
                # Show error message when no components available
                raise UserError('Cannot generate asset code. Please select Main Asset, Category, and/or Location.')
    
    @api.depends('serial_number_code', 'location_asset_selection', 'asset_name', 'responsible_person_id')
    def _compute_qr_code(self):
        """Generate QR code image with asset details including name, location, and responsible person"""
        for record in self:
            if record.serial_number_code and qrcode:
                try:
                    # Create QR code with comprehensive asset information
                    asset_code = record.serial_number_code
                    asset_name = record.asset_name or 'N/A'

                    # Get location information
                    location_info = 'N/A'
                    if record.location_asset_selection and record.location_asset_selection.location_name:
                        location_info = record.location_asset_selection.location_name

                    # Get responsible person information
                    responsible_info = 'N/A'
                    if record.responsible_person_id and record.responsible_person_id.name:
                        responsible_info = record.responsible_person_id.name

                    # Create QR text with organized layout
                    qr_text = f'ASSET CODE: {asset_code}\n'
                    qr_text += f'NAME ASSET: {asset_name}\n'
                    qr_text += f'LOCATION: {location_info}\n'
                    qr_text += f'RESPONSIBLE: {responsible_info}'

                    # Generate QR code with the text
                    qr = qrcode.QRCode(
                        version=1,  # Keep small version, will increase if needed
                        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_text)
                    qr.make(fit=True)

                    # Create image
                    img = qr.make_image(fill_color="black", back_color="white")

                    # Convert to bytes
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG')
                    img_bytes = img_buffer.getvalue()

                    # Convert to base64
                    record.qr_code_image = base64.b64encode(img_bytes)
                except Exception as e:
                    record.qr_code_image = False
            else:
                record.qr_code_image = False
    
    def generate_qr_code(self):
        """Open QR Code popup with asset details"""
        self.ensure_one()

        # Generate QR code if not exists
        if not self.qr_code_image:
            self._compute_qr_code()

        # Return action to open QR code popup
        return {
            'type': 'ir.actions.act_window',
            'name': 'Asset QR Code',
            'res_model': 'fits.asset',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('fits_assets_maintenance.view_asset_qr_code_popup').id,
            'target': 'new',  # Open as popup
            'context': {'qr_code_popup': True}
        }

    def print_qr_label_pdf(self):
        """Generate PDF label with QR code and asset information"""
        self.ensure_one()

        # Generate QR code if not exists
        if not self.qr_code_image:
            self._compute_qr_code()

        # Return action to generate PDF using the report action
        return self.env.ref('fits_assets_maintenance.action_report_asset_qr_label').report_action(self)
    
    def action_view_asset_photo(self):
        """Open popup to view asset photo in full size"""
        self.ensure_one()
        
        if not self.image_1920:
            raise UserError('No photo available for this asset. Please upload a photo first.')
        
        # Return action to open photo popup
        return {
            'type': 'ir.actions.act_window',
            'name': f'Asset Photo - {self.asset_name}',
            'res_model': 'fits.asset',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('fits_assets_maintenance.view_asset_photo_popup').id,
            'target': 'new',  # Open as popup
            'context': {'photo_popup': True}
        }

    @api.onchange('asset_name')
    def _onchange_asset_name(self):
        """Auto-fill location asset selection when asset name is entered"""
        for record in self:
            if record.asset_name:
                # Find Location Asset by name that matches the asset name
                location_asset = self.env['fits.location.assets'].search([
                    ('location_name', '=', record.asset_name)
                ], limit=1)
                if location_asset:
                    record.location_asset_selection = location_asset.id
            else:
                record.location_asset_selection = False

    @api.onchange('responsible_person_id')
    def _onchange_responsible_person_id(self):
        """Auto-populate department when responsible person is selected"""
        for record in self:
            if record.responsible_person_id and record.responsible_person_id.department_id:
                record.department_id = record.responsible_person_id.department_id
            elif record.responsible_person_id:
                # If employee has no department, clear the department field
                record.department_id = False

    @api.onchange('main_asset_selection')
    def _onchange_main_asset_category_domain(self):
        """Update category domain when main asset selection changes"""
        if self.main_asset_selection:
            # Filter categories for the selected Main Asset
            main_asset_id = self.main_asset_selection.id
            domain = [('main_asset_id', '=', main_asset_id)]

            print(f"DEBUG: Filtering categories for Main Asset {self.main_asset_selection.display_name} (ID: {main_asset_id})")
            print(f"DEBUG: Domain: {domain}")

            # Clear current category selection to force user to select from filtered options
            self.category_id = False

            # Return domain for immediate filtering in the UI
            return {'domain': {'category_id': domain}}
        else:
            # No Main Asset selected - show empty selection
            print("DEBUG: No Main Asset selected - clearing category domain")
            self.category_id = False
            return {'domain': {'category_id': [('id', '=', False)]}}

    @api.onchange('main_asset_selection')
    def _onchange_main_asset_selection(self):
        """Handle Main Asset Selection changes - only for filtering, no auto-fill"""
        # Only keep the filtering logic, remove auto-fill
        # The @api.onchange method for category domain filtering is handled separately
        pass

    def _inverse_location_asset_selection(self):
        """Allow manual setting of location asset"""
        pass  # This allows the field to be set manually if needed

    def _assign_unique_counter_to_existing_records(self):
        """Assign unique counters to existing asset records that don't have one"""
        existing_assets_without_counter = self.env['fits.asset'].search([
            ('unique_counter', '=', False),
            ('serial_number_code', '!=', False)
        ])

        for asset in existing_assets_without_counter:
            # Extract counter from existing serial_number_code
            if asset.serial_number_code:
                counter_match = re.search(r'\d{4}$', asset.serial_number_code)
                if counter_match:
                    try:
                        extracted_counter = int(counter_match.group())
                        # Verify this counter is not already used by another asset
                        existing_counter = self.env['fits.asset'].search([
                            ('unique_counter', '=', extracted_counter),
                            ('id', '!=', asset.id)
                        ], limit=1)

                        if existing_counter:
                            # Counter already exists, assign a new one
                            asset.unique_counter = self._get_next_unique_counter()
                        else:
                            # Use extracted counter
                            asset.unique_counter = extracted_counter
                    except:
                        # If extraction fails, assign a new counter
                        asset.unique_counter = self._get_next_unique_counter()
                else:
                    # No counter found in code, assign a new one
                    asset.unique_counter = self._get_next_unique_counter()

        # Ensure no duplicate counters exist
        self._resolve_duplicate_counters()

    def _resolve_duplicate_counters(self):
        """Resolve any duplicate unique counters in the system"""
        # Find all assets with unique counters
        assets_with_counters = self.env['fits.asset'].search([
            ('unique_counter', '>', 0)
        ])

        # Group by counter value
        counter_groups = {}
        for asset in assets_with_counters:
            counter = asset.unique_counter
            if counter not in counter_groups:
                counter_groups[counter] = []
            counter_groups[counter].append(asset)

        # Resolve duplicates
        for counter, assets in counter_groups.items():
            if len(assets) > 1:
                # Multiple assets have the same counter - keep the first one, reassign others
                for i, asset in enumerate(assets[1:], 1):
                    asset.unique_counter = self._get_next_unique_counter()

    @api.model
    def create(self, vals):
        """Create method - assign unique counter for new assets"""
        # Clear recurrence settings if maintenance_required is set to False
        if 'maintenance_required' in vals and not vals['maintenance_required']:
            vals.update({
                'recurrence_pattern': 'none',
                'recurrence_start_date': False,
                'recurrence_interval': False,
                'recurrence_end_date': False
            })

        # Create the record first
        result = super(Asset, self).create(vals)

        # Assign unique counter if not already set (for new assets)
        if not result.unique_counter:
            result.unique_counter = self._get_next_unique_counter()

        return result

    def write(self, vals):
        """Write method - handle changes and manage calendar events"""
        # Clear recurrence settings if maintenance_required is set to False
        if 'maintenance_required' in vals and not vals['maintenance_required']:
            vals.update({
                'recurrence_pattern': 'none',
                'recurrence_start_date': False,
                'recurrence_interval': False,
                'recurrence_end_date': False
            })

        # Ensure maintenance_required stays True if it was True and not explicitly changed
        for asset in self:
            if asset.maintenance_required and 'maintenance_required' not in vals:
                vals['maintenance_required'] = True

        # Store old values before write
        old_maintenance_required = {asset.id: asset.maintenance_required for asset in self}
        old_status = {asset.id: asset.status for asset in self}
        old_recurrence_pattern = {asset.id: asset.recurrence_pattern for asset in self}
        old_recurrence_start_date = {asset.id: asset.recurrence_start_date for asset in self}
        old_recurrence_interval = {asset.id: asset.recurrence_interval for asset in self}
        old_recurrence_end_date = {asset.id: asset.recurrence_end_date for asset in self}
        old_next_maintenance_date = {asset.id: asset.next_maintenance_date for asset in self}

        result = super(Asset, self).write(vals)

        # Handle calendar events after write
        for asset in self:
            asset_id = asset.id

            # If maintenance_required changed to False, remove from calendar
            if old_maintenance_required.get(asset_id, False) and not asset.maintenance_required:
                print(f"DEBUG: Asset {asset.name} maintenance_required changed to False, removing from calendar")
                calendar_events = self.env['fits.maintenance.calendar'].search([('asset_id', '=', asset_id)])
                calendar_events.unlink()
                continue

            # If status changed from maintenance to something else, remove from calendar
            if old_status.get(asset_id) == 'maintenance' and asset.status != 'maintenance':
                print(f"DEBUG: Asset {asset.name} status changed from maintenance to {asset.status}, removing from calendar")
                calendar_events = self.env['fits.maintenance.calendar'].search([('asset_id', '=', asset_id)])
                calendar_events.unlink()
                continue

            # Only create/update calendar events if recurrence settings actually changed or this is a new qualifying asset
            recurrence_settings_changed = (
                old_recurrence_pattern.get(asset_id) != asset.recurrence_pattern or
                old_recurrence_start_date.get(asset_id) != asset.recurrence_start_date or
                old_recurrence_interval.get(asset_id) != asset.recurrence_interval or
                old_recurrence_end_date.get(asset_id) != asset.recurrence_end_date or
                old_next_maintenance_date.get(asset_id) != asset.next_maintenance_date
            )

            # If conditions are met and settings changed, create/update calendar events
            if (asset.status == 'maintenance' and
                asset.maintenance_required and
                asset.recurrence_pattern != 'none' and
                asset.recurrence_start_date and
                (asset.recurrence_interval or asset.recurrence_end_date) and
                recurrence_settings_changed):
                print(f"DEBUG: Asset {asset.name} recurrence settings changed, creating/updating calendar events")
                self.env['fits.maintenance.calendar'].create_calendar_events()

        return result

    # Status transition methods
    def action_set_to_draft(self):
        """Set asset status to draft"""
        for asset in self:
            # If setting from active or maintenance to draft, set maintenance_required to False
            if asset.status in ['active', 'maintenance']:
                asset.write({'status': 'draft', 'maintenance_required': False})
            else:
                asset.write({'status': 'draft'})

    def action_set_to_active(self):
        """Set asset status to active"""
        self.write({'status': 'active'})

    def action_set_to_maintenance(self):
        """Set asset status to maintenance"""
        self.write({'status': 'maintenance'})

    def action_set_to_disposed(self):
        """Set asset status to disposed"""
        self.write({'status': 'disposed'})

    @api.onchange('maintenance_required')
    def _onchange_maintenance_required(self):
        """Clear recurrence settings when maintenance_required is set to False"""
        if not self.maintenance_required:
            self.recurrence_pattern = 'none'
            self.recurrence_start_date = False
            self.recurrence_interval = False
            self.recurrence_end_date = False

    @api.onchange('recurrence_interval')
    def _onchange_recurrence_interval(self):
        """Clear recurrence_end_date when recurrence_interval is set"""
        if self.recurrence_interval:
            self.recurrence_end_date = False

    @api.onchange('recurrence_end_date')
    def _onchange_recurrence_end_date(self):
        """Clear recurrence_interval when recurrence_end_date is set"""
        if self.recurrence_end_date:
            self.recurrence_interval = False

    def generate_maintenance_schedule(self):
        """Generate maintenance calendar events based on recurrence settings"""
        self.ensure_one()
        
        # Validate recurrence settings
        if self.recurrence_pattern == 'none':
            raise UserError('Please select a Recurrence Pattern before generating schedule.')
        
        if not self.recurrence_start_date:
            raise UserError('Please set a Start Date before generating schedule.')
        
        if not self.recurrence_interval and not self.recurrence_end_date:
            raise UserError('Please set either Interval (days) or End Date before generating schedule.')
        
        # Delete existing calendar events and draft maintenance requests for this asset
        existing_events = self.env['fits.maintenance.calendar'].search([
            ('asset_id', '=', self.id)
        ])
        if existing_events:
            existing_events.unlink()
        
        # Delete existing auto-generated draft maintenance requests for this asset
        existing_auto_requests = self.env['fits.maintenance.request'].search([
            ('asset_id', '=', self.id),
            ('state', '=', 'draft'),
            ('auto_generated', '=', True)
        ])
        if existing_auto_requests:
            existing_auto_requests.unlink()
        
        # Generate maintenance dates based on recurrence settings
        maintenance_dates = []
        
        if self.recurrence_pattern == 'daily':
            if self.recurrence_interval and self.recurrence_interval > 0:
                # Generate dates based on interval
                current_date = self.recurrence_start_date
                for i in range(self.recurrence_interval):
                    maintenance_dates.append(current_date)
                    current_date = current_date + timedelta(days=1)
            elif self.recurrence_end_date:
                # Generate dates from start to end date
                current_date = self.recurrence_start_date
                while current_date <= self.recurrence_end_date:
                    maintenance_dates.append(current_date)
                    current_date = current_date + timedelta(days=1)
        
        elif self.recurrence_pattern == 'weekly':
            if self.recurrence_interval and self.recurrence_interval > 0:
                # Generate weekly dates based on interval count
                current_date = self.recurrence_start_date
                for i in range(self.recurrence_interval):
                    maintenance_dates.append(current_date)
                    current_date = current_date + timedelta(weeks=1)
            elif self.recurrence_end_date:
                # Generate weekly dates from start to end date
                current_date = self.recurrence_start_date
                while current_date <= self.recurrence_end_date:
                    maintenance_dates.append(current_date)
                    current_date = current_date + timedelta(weeks=1)
        
        elif self.recurrence_pattern == 'monthly':
            if self.recurrence_interval and self.recurrence_interval > 0:
                # Generate monthly dates based on interval count
                current_date = self.recurrence_start_date
                for i in range(self.recurrence_interval):
                    maintenance_dates.append(current_date)
                    # Add 1 month
                    try:
                        if current_date.month == 12:
                            current_date = current_date.replace(year=current_date.year + 1, month=1)
                        else:
                            current_date = current_date.replace(month=current_date.month + 1)
                    except ValueError:
                        # Handle day overflow (e.g., Jan 31 -> Feb 31 doesn't exist)
                        if current_date.month == 12:
                            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                        else:
                            current_date = current_date.replace(month=current_date.month + 1, day=1)
            elif self.recurrence_end_date:
                # Generate monthly dates from start to end date
                current_date = self.recurrence_start_date
                while current_date <= self.recurrence_end_date:
                    maintenance_dates.append(current_date)
                    # Add 1 month
                    try:
                        if current_date.month == 12:
                            current_date = current_date.replace(year=current_date.year + 1, month=1)
                        else:
                            current_date = current_date.replace(month=current_date.month + 1)
                    except ValueError:
                        # Handle day overflow
                        if current_date.month == 12:
                            current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
                        else:
                            current_date = current_date.replace(month=current_date.month + 1, day=1)
        
        elif self.recurrence_pattern == 'yearly':
            if self.recurrence_interval and self.recurrence_interval > 0:
                # Generate yearly dates based on interval count
                current_date = self.recurrence_start_date
                for i in range(self.recurrence_interval):
                    maintenance_dates.append(current_date)
                    try:
                        current_date = current_date.replace(year=current_date.year + 1)
                    except ValueError:
                        # Handle leap year issues (Feb 29)
                        current_date = current_date.replace(year=current_date.year + 1, day=28)
            elif self.recurrence_end_date:
                # Generate yearly dates from start to end date
                current_date = self.recurrence_start_date
                while current_date <= self.recurrence_end_date:
                    maintenance_dates.append(current_date)
                    try:
                        current_date = current_date.replace(year=current_date.year + 1)
                    except ValueError:
                        # Handle leap year issues
                        current_date = current_date.replace(year=current_date.year + 1, day=28)
        
        # Create calendar events and maintenance requests for each maintenance date
        events_created = 0
        requests_created = 0
        
        for maintenance_date in maintenance_dates:
            # Create calendar event
            calendar_event = self.env['fits.maintenance.calendar'].create({
                'asset_id': self.id,
                'maintenance_date': maintenance_date,
                'hasil_status': 'draft',
            })
            events_created += 1
            
            # Create maintenance request with draft status (auto-generated)
            maintenance_request = self.env['fits.maintenance.request'].create({
                'asset_id': self.id,
                'scheduled_date': maintenance_date,
                'user_id': self.responsible_person_id.user_id.id if self.responsible_person_id and self.responsible_person_id.user_id else self.env.user.id,
                'team_id': self.maintenance_team_id.id if self.maintenance_team_id else False,
                'maintenance_request_title': f'Scheduled - {self.name}',
                'description': f'Auto-generated maintenance scheduled on {maintenance_date}',
                'maintenance_type': 'preventive',
                'state': 'draft',
                'auto_generated': True,  # Mark as auto-generated
            })
            requests_created += 1
        
        # Set maintenance_required to True when generating schedule
        self.write({'maintenance_required': True})
        
        # Return a notification message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'{events_created} schedule(s) and {requests_created} maintenance request(s) created successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_maintenance_calendar(self):
        """Open maintenance calendar for this asset"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Calendar',
            'res_model': 'fits.maintenance.calendar',
            'view_mode': 'calendar',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
            }
        }

    def action_view_maintenance_requests(self):
        """Open maintenance requests list for this asset"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Requests',
            'res_model': 'fits.maintenance.request',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {
                'default_asset_id': self.id,
                'default_maintenance_request_title': f'Maintenance for {self.name}',
            }
        }

    def unlink(self):
        """Override unlink to prevent deletion of active or maintenance assets"""
        for record in self:
            if record.status in ['active', 'maintenance']:
                raise UserError(f"Cannot delete Asset '{record.name}' because it is {record.status}. Only Draft assets can be deleted.")
        return super(Asset, self).unlink()
