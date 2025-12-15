# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.mail.models.mail_thread import MailThread
from datetime import datetime


class AssetTransfer(models.Model, MailThread):
    _name = 'fits.asset.transfer'
    _description = 'Asset Transfer'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # Auto-generated transfer reference with format ATF/YYYY/0001
    name = fields.Char(default='New', readonly=True, copy=False)

    # Display name combining asset name and transfer reference
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # Filter assets to only show active ones
    asset_id = fields.Many2one('fits.asset', string='Asset', required=True,
                              domain=[('status', '=', 'active')])

    transfer_date = fields.Date(string='Transfer Date', default=fields.Date.today)
    from_location = fields.Char(string='From Location', compute='_compute_from_location', store=True)
    to_location = fields.Many2one('fits.location.assets', string='To Location')

    # Asset details (computed fields from selected asset)
    main_asset_name = fields.Char(string='Main Asset', compute='_compute_asset_details', store=True)
    asset_category_name = fields.Char(string='Asset Category', compute='_compute_asset_details', store=True)
    location_assets_name = fields.Char(string='Location Assets', compute='_compute_asset_details', store=True)
    asset_code = fields.Char(string='Kode Asset', compute='_compute_asset_details', store=True)

    # Responsible Person details
    current_responsible_person = fields.Char(string='Current Responsible Person', compute='_compute_responsible_person', store=True)
    to_responsible_person = fields.Many2one('hr.employee', string='To Responsible Person')

    reason = fields.Text(string='Transfer Reason', required=True)

    # Updated status: draft, submitted, approved
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved')
    ], string='Status', default='draft')

    def action_confirm(self):
        """Confirm the transfer (approve it) and update asset location"""
        for record in self:
            # Validation: Check if required fields are filled
            if not record.reason:
                raise UserError('Transfer Reason must be filled before approving the transfer.')

            if not record.to_responsible_person:
                raise UserError('To Responsible Person must be filled before approving the transfer.')

            # Store old asset code for tracking changes
            old_asset_code = ''
            if record.asset_id and record.asset_id.serial_number_code:
                old_asset_code = record.asset_id.serial_number_code

            # Use stored from_location for the chatter message
            old_location = record.from_location or 'Unknown'
            
            # Update asset location to the transfer destination (if specified)
            if record.asset_id and record.to_location:
                new_location = record.to_location.location_name

                # Update asset location
                record.asset_id.write({
                    'location_asset_selection': record.to_location.id
                })

                # Regenerate asset code with new location
                try:
                    record.asset_id.generate_code()
                except UserError:
                    # If code generation fails, continue without it
                    pass

            # Update responsible person if specified
            if record.to_responsible_person:
                if record.asset_id:
                    record.asset_id.write({
                        'responsible_person_id': record.to_responsible_person.id
                    })

            # Get new asset code after potential regeneration
            new_asset_code = ''
            if record.asset_id and record.asset_id.serial_number_code:
                new_asset_code = record.asset_id.serial_number_code

            # Post combined message to asset chatter about all changes
            if record.asset_id:
                message_parts = []

                # Location change message
                if record.to_location:
                    new_location = record.to_location.location_name
                    # Use the old_location captured earlier in the method
                    message_parts.append(f"Asset location changed from '{old_location}' to '{new_location}' via Asset Transfer {record.name}")

                # Asset code change message
                if old_asset_code and new_asset_code and old_asset_code != new_asset_code:
                    message_parts.append(f"Asset code changed from '{old_asset_code}' to '{new_asset_code}'")

                # Responsible person change message
                if record.to_responsible_person:
                    message_parts.append(f"Asset responsible person changed to '{record.to_responsible_person.name}'")

                # Combine all messages
                if message_parts:
                    combined_message = ' and '.join(message_parts)
                    record.asset_id.message_post(
                        body=combined_message,
                        subject="Asset Updated via Transfer"
                    )

        # Update transfer status to approved
        self.write({'state': 'approved'})

        # Post notification to chatter about successful approval
        for record in self:
            # Get old asset code for comparison (need to get it again since it might have changed)
            old_asset_code = ''
            if record.asset_id and hasattr(record.asset_id, '_origin') and record.asset_id._origin.serial_number_code:
                old_asset_code = record.asset_id._origin.serial_number_code
            elif record.asset_id and record.asset_id.serial_number_code:
                old_asset_code = record.asset_id.serial_number_code

            message_parts = []
            message_parts.append(f"Transfer {record.name} has been approved.")

            if record.to_location:
                old_location = record.from_location or 'Unknown'
                new_location = record.to_location.location_name
                message_parts.append(f"Asset location changed from '{old_location}' to '{new_location}'")

            # Get final asset code for the message
            final_asset_code = ''
            if record.asset_id and record.asset_id.serial_number_code:
                final_asset_code = record.asset_id.serial_number_code

            if final_asset_code and old_asset_code and final_asset_code != old_asset_code:
                message_parts.append(f"Asset code updated to '{final_asset_code}'")

            if record.to_responsible_person:
                message_parts.append(f"Asset responsible person changed to '{record.to_responsible_person.name}'")

            if record.reason:
                message_parts.append(f"Transfer reason: {record.reason}")

            final_message = " | ".join(message_parts)

            record.message_post(
                body=final_message,
                subject="Transfer Approved"
            )

    def action_submit(self):
        """Submit the transfer for approval (draft -> submitted)"""
        for record in self:
            # Validation: Check if required fields are filled before submitting
            if not record.reason:
                raise UserError('Transfer Reason must be filled before sending for approval.')
            if not record.to_responsible_person:
                raise UserError('To Responsible Person must be filled before sending for approval.')

        self.write({'state': 'submitted'})

        # Post notification to chatter about successful submission
        for record in self:
            message = f"Transfer {record.name} has been successfully submitted for approval."
            if record.to_location:
                message += f" Destination location: {record.to_location.location_name}"
            if record.to_responsible_person:
                message += f" | New responsible person: {record.to_responsible_person.name}"

            record.message_post(
                body=message,
                subject="Transfer Submitted for Approval"
            )

    def action_reset_to_draft(self):
        """Reset transfer status back to draft and ensure asset data reflects approved transfer"""
        for record in self:
            # If transfer was previously approved, ensure asset data matches approved transfer
            if record.asset_id and record.state in ['approved']:
                updates_made = False
                asset_code_changed = False

                # Get current asset code before any changes
                old_asset_code = ''
                if record.asset_id and record.asset_id.serial_number_code:
                    old_asset_code = record.asset_id.serial_number_code

                # Apply the approved location to asset if specified
                if record.to_location:
                    current_location = record.asset_id.location_asset_selection
                    if not current_location or current_location.id != record.to_location.id:
                        record.asset_id.write({
                            'location_asset_selection': record.to_location.id
                        })
                        updates_made = True

                # Apply the approved responsible person to asset if specified
                if record.to_responsible_person:
                    current_responsible = record.asset_id.responsible_person_id
                    if not current_responsible or current_responsible.id != record.to_responsible_person.id:
                        record.asset_id.write({
                            'responsible_person_id': record.to_responsible_person.id
                        })
                        updates_made = True

                # Check if asset code changed after location update
                new_asset_code = ''
                if record.asset_id and record.asset_id.serial_number_code:
                    new_asset_code = record.asset_id.serial_number_code

                if old_asset_code and new_asset_code and old_asset_code != new_asset_code:
                    asset_code_changed = True

                # Post message about status reset
                if updates_made or asset_code_changed:
                    message_parts = []
                    if record.to_location:
                        message_parts.append(f"Asset location maintained at '{record.to_location.location_name}'")
                    if record.to_responsible_person:
                        message_parts.append(f"Asset responsible person maintained as '{record.to_responsible_person.name}'")
                    if asset_code_changed:
                        message_parts.append(f"Asset code maintained as '{new_asset_code}'")

                    if message_parts:
                        combined_message = f"Transfer {record.name} reset to draft: {' and '.join(message_parts)}"
                        record.asset_id.message_post(
                            body=combined_message,
                            subject="Transfer Reset to Draft - Data Maintained"
                        )

        self.write({'state': 'draft'})

        # Post notification to chatter about status reset
        for record in self:
            message = f"Transfer {record.name} has been reset to Draft status."
            record.message_post(
                body=message,
                subject="Transfer Reset to Draft"
            )

    @api.model
    def create(self, vals):
        """Generate transfer reference when creating new record and set from_location"""
        if vals.get('name', 'New') == 'New':
            # Generate ATF/YYYY/0001 format
            current_year = datetime.now().year
            sequence_code = self._get_next_sequence_number()
            vals['name'] = f'ATF/{current_year}/{sequence_code:04d}'

        # Set from_location if asset_id is provided
        if vals.get('asset_id'):
            asset = self.env['fits.asset'].browse(vals['asset_id'])
            if asset.location_asset_selection:
                vals['from_location'] = asset.location_asset_selection.location_name
            else:
                vals['from_location'] = 'Unknown'

            # Asset details are now computed fields, no need to set them manually
            # They will be automatically computed when asset_id is set

        return super(AssetTransfer, self).create(vals)

    def _get_next_sequence_number(self):
        """Get next sequence number for transfer reference"""
        current_year = datetime.now().year
        # Find the highest sequence number for current year
        existing_transfers = self.env['fits.asset.transfer'].search([
            ('name', '=like', f'ATF/{current_year}/%')
        ])

        max_sequence = 0
        for transfer in existing_transfers:
            try:
                # Extract sequence number from ATF/YYYY/XXXX format
                sequence_part = transfer.name.split('/')[-1]
                sequence_num = int(sequence_part)
                if sequence_num > max_sequence:
                    max_sequence = sequence_num
            except (ValueError, IndexError):
                continue

        return max_sequence + 1

    @api.depends('asset_id', 'state')
    def _compute_from_location(self):
        """Compute from location based on transfer status"""
        for record in self:
            if record.state == 'approved' and record.asset_id:
                # For approved transfers, from_location field should show the original location
                # The field is already set during creation, so we keep the stored value
                pass  # Keep the stored from_location value
            elif record.asset_id and record.asset_id.location_asset_selection:
                record.from_location = record.asset_id.location_asset_selection.location_name
            else:
                record.from_location = 'Unknown'

    @api.depends('asset_id', 'state', 'to_location')
    def _compute_asset_details(self):
        """Compute asset details based on selected asset and transfer status"""
        for record in self:
            if record.asset_id:
                record.main_asset_name = record.asset_id.main_asset_selection.asset_name if record.asset_id.main_asset_selection else ''
                record.asset_category_name = record.asset_id.category_id.name if record.asset_id.category_id else ''

                # Show location based on transfer status
                if record.state == 'approved' and record.to_location:
                    # Show the approved location
                    record.location_assets_name = record.to_location.location_name
                else:
                    # Show current asset location (which may reflect approved transfer)
                    record.location_assets_name = record.asset_id.location_asset_selection.location_name if record.asset_id.location_asset_selection else ''

                record.asset_code = record.asset_id.serial_number_code or ''
            else:
                record.main_asset_name = ''
                record.asset_category_name = ''
                record.location_assets_name = ''
                record.asset_code = ''

    @api.depends('asset_id', 'state', 'to_responsible_person')
    def _compute_responsible_person(self):
        """Compute current responsible person from asset (which reflects approved transfer)"""
        for record in self:
            if record.asset_id and record.asset_id.responsible_person_id:
                record.current_responsible_person = record.asset_id.responsible_person_id.name
            else:
                record.current_responsible_person = 'Not Assigned'

    @api.depends('asset_id.asset_name', 'name')
    def _compute_display_name(self):
        """Compute display name combining asset name and transfer reference"""
        for record in self:
            # Prefer explicit transfer reference when it is already generated
            transfer_ref = record.name if record.name and record.name != 'New' else False

            # Get a human friendly asset label (asset_name is required on assets)
            asset_label = False
            if record.asset_id:
                asset_label = getattr(record.asset_id, 'asset_name', False) or getattr(record.asset_id, 'name', False)

            if asset_label and transfer_ref:
                record.display_name = f"{asset_label} - {transfer_ref}"
            elif asset_label:
                record.display_name = f"{asset_label} - New"
            elif transfer_ref:
                record.display_name = f"Unknown Asset - {transfer_ref}"
            else:
                record.display_name = "New Transfer"

    def unlink(self):
        """Override unlink to prevent deletion of approved or submitted transfers"""
        for record in self:
            if record.state in ['submitted', 'approved']:
                raise UserError(f"Cannot delete Asset Transfer {record.name} because it has been {record.state}. Only Draft transfers can be deleted.")
        return super(AssetTransfer, self).unlink()

    def name_get(self):
        """Return only the Asset name for clearer manual selection labels.
        Fallback order: asset_name -> asset display_name/name -> transfer ref -> generic.
        """
        result = []
        for rec in self:
            # Start from computed display_name if available to keep consistency everywhere
            label = rec.display_name or None

            # If for some reason display_name is empty, build a label based on asset and transfer ref
            if not label and rec.asset_id:
                label = getattr(rec.asset_id, 'asset_name', False) or getattr(rec.asset_id, 'display_name', False) or getattr(rec.asset_id, 'name', False)

            # Fallback to transfer reference when available
            if not label and rec.name and rec.name != 'New':
                label = rec.name

            # Absolute fallback to avoid ever returning an empty name (prevents 'Unnamed' in UI)
            if not label:
                label = _('Transfer %s') % (rec.id,)
            result.append((rec.id, label))
        return result