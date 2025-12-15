# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class MaintenanceRequest(models.Model):
    _name = 'fits.maintenance.request'
    _description = 'Maintenance Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'maintenance_request_type'

    # Remove the name field - using maintenance_request_type as the main identifier
    # name = fields.Char(string='Request Number', required=True, copy=False, readonly=True,
    #                    default=lambda self: _('New'))

    asset_id = fields.Many2one(
        'fits.asset',
        string='Asset',
        required=True,
        domain="[('responsible_person_id.user_id', '=', user_id)]",
        help='Asset that requires maintenance'
    )

    category_id = fields.Many2one('fits.asset.category', string='Category',
                                 related='asset_id.category_id', store=True, readonly=True)

    # Additional asset information fields
    location_asset_id = fields.Many2one('fits.location.assets', string='Location Assets',
                                      related='asset_id.location_asset_selection', store=True, readonly=True)

    asset_code = fields.Char(string='Asset Code',
                           related='asset_id.serial_number_code', store=True, readonly=True)

    responsible_person_id = fields.Many2one('hr.employee', string='Responsible Person',
                                          related='asset_id.responsible_person_id', store=True, readonly=True)

    team_id = fields.Many2one('fits.maintenance.team', string='Team', domain="[('active', '=', True)]")

    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        domain=lambda self: self._get_user_domain()
    )

    @api.model
    def _get_user_domain(self):
        """Batasi user yang bisa dipilih berdasarkan roles"""
        # 🔹 Kalau user punya role Manager → bisa lihat semua user
        if self.env.user.has_group('fits_assets_maintenance.group_fits_asset_maintenance_manager'):
            return []
        # 🔹 Kalau bukan Manager → hanya dirinya sendiri
        else:
            return [('id', '=', self.env.user.id)]

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Sync asset choices with the selected responsible user."""
        if not self.user_id:
            self.asset_id = False
            return {'domain': {'asset_id': [('id', '=', False)]}}

        if self.asset_id and self.asset_id.responsible_person_id.user_id != self.user_id:
            self.asset_id = False

        return {
            'domain': {
                'asset_id': [('responsible_person_id.user_id', '=', self.user_id.id)]
            }
        }

    email = fields.Char(string='Email', related='user_id.email', readonly=False)

    priority_star = fields.Boolean(string='Priority', default=False)

    priority = fields.Selection([
        ('0', '0 Stars'),
        ('1', '1 Star'),
        ('2', '2 Stars'),
        ('3', '3 Stars')
    ], string='Priority', default='0', widget='priority')

    # Changed back to maintenance_type selection field as requested
    maintenance_type = fields.Selection([
        ('corrective', 'Corrective'),
        ('preventive', 'Preventive')
    ], string='Maintenance Type', default='corrective', required=True)

    # New field for Maintenance Request Type as char (title)
    maintenance_request_type = fields.Char(string='Maintenance Request',
                                         help='Combined request number and title',
                                         compute='_compute_maintenance_request_display',
                                         store=True,
                                         readonly=True)

    @api.depends('maintenance_request_title')
    def _compute_maintenance_request_display(self):
        """Compute the combined maintenance request display"""
        for record in self:
            if record.maintenance_request_title:
                record.maintenance_request_type = f"{record.maintenance_request_type.split(' - ')[0]} - {record.maintenance_request_title}" if record.maintenance_request_type else f"MR - {record.maintenance_request_title}"
            else:
                record.maintenance_request_type = record.maintenance_request_type or 'MR'

    # Field for the actual title (editable)
    maintenance_request_title = fields.Char(string='Request Title',
                                          help='Title/description of the maintenance request',
                                          required=True)

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        """Set maintenance request title based on selected asset"""
        if self.asset_id:
            self.maintenance_request_title = f"Maintenance for {self.asset_id.asset_name or 'Asset'}"

    # Remove the boolean fields as they're being replaced
    # is_corrective = fields.Boolean(string='Corrective', default=True)
    # is_preventive = fields.Boolean(string='Preventive', default=False)

    description = fields.Text(string='Description', required=True)

    scheduled_date = fields.Date(string='Scheduled Start', required=True)
    scheduled_end_date = fields.Date(string='Scheduled End')

    state = fields.Selection([
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('repaired', 'Repaired'),
    ('cancelled', 'Cancelled'),
    ('done', 'Done')
], string='Status', default='draft', tracking=True, group_expand='_group_expand_states')

    def _group_expand_states(self, states, domain, order=None):
        """Ensure all possible states are shown in kanban or grouped views."""
        return [key for key, val in self._fields['state'].selection]

    # Related fields from asset for recurrence display
    asset_recurrence_pattern = fields.Selection([
        ('none', 'No Recurrence'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly')
    ], string='Asset Recurrence Pattern', related='asset_id.recurrence_pattern', readonly=True)

    asset_recurrence_interval = fields.Integer(string='Asset Recurrence Interval',
                                             related='asset_id.recurrence_interval', readonly=True)

    asset_recurrence_start_date = fields.Date(string='Asset Recurrence Start Date',
                                            related='asset_id.recurrence_start_date', readonly=True)

    asset_recurrence_end_date = fields.Date(string='Asset Recurrence End Date',
                                          related='asset_id.recurrence_end_date', readonly=True)

    asset_next_maintenance_date = fields.Date(string='Asset Next Maintenance Date',
                                            related='asset_id.next_maintenance_date', readonly=True)

    # Auto-generated flag to identify maintenance requests created from schedule
    auto_generated = fields.Boolean(string='Auto Generated', default=False, readonly=True,
                                   help='Indicates if this maintenance request was auto-generated from schedule')
    
    # Cancellation reason
    cancellation_reason = fields.Text(string='Cancellation Reason', readonly=True, copy=False,
                                    help='Reason for cancelling the maintenance request')

    @api.constrains('asset_id', 'user_id')
    def _check_asset_user_alignment(self):
        for record in self:
            if (
                record.asset_id
                and record.user_id
                and record.asset_id.responsible_person_id.user_id != record.user_id
            ):
                raise ValidationError(_("The selected asset must belong to the chosen Responsible user."))
    
    @api.constrains('state', 'team_id')
    def _check_team_required(self):
        for record in self:
            if record.state not in ['draft', 'cancelled'] and not record.team_id:
                raise ValidationError(_("⚠️ The 'Team' field is required before saving this record."))

    @api.model
    def create(self, vals):
        # Generate unique identifier for maintenance request
        if not vals.get('maintenance_request_type'):
            sequence_code = self.env['ir.sequence'].next_by_code('fits.maintenance.request') or 'MR'
            title = vals.get('maintenance_request_title', '')
            vals['maintenance_request_type'] = f"{sequence_code} - {title}" if title else sequence_code

        # Create the record
        result = super(MaintenanceRequest, self).create(vals)

        # Set maintenance_required to True on the related asset (only if not draft)
        # Draft requests are auto-generated from schedule, so maintenance_required is already set
        if result.asset_id and result.state != 'draft':
            result.asset_id.write({'maintenance_required': True})

        # Update calendar if this is an in-progress request with scheduled date
        if result.state == 'in_progress' and result.scheduled_date:
            print(f"DEBUG: New in-progress maintenance request created - updating calendar")
            self.env['fits.maintenance.calendar'].update_calendar_for_request(result.id)

        return result

    def write(self, vals):
        """Override write to update calendar when status changes"""
        # Store old values before write
        old_states = {record.id: record.state for record in self}

        result = super(MaintenanceRequest, self).write(vals)

        # Update calendar if state changed to in_progress or other relevant changes
        for record in self:
            old_state = old_states.get(record.id)
            # Only update calendar if state actually changed to a relevant state or scheduled_date changed
            if (old_state != record.state and record.state in ['in_progress', 'repaired', 'done', 'cancelled']) or 'scheduled_date' in vals:
                # Update calendar events if state changed or relevant fields changed
                print(f"DEBUG: Maintenance request {record.id} changed - updating calendar")
                self.env['fits.maintenance.calendar'].update_calendar_for_request(record.id)

        return result
    
    def write(self, vals):
        """Override write to control Kanban state transitions and update related asset status."""
        old_states = {record.id: record.state for record in self}

        for record in self:
            new_state = vals.get('state')

            if not new_state:
                continue

            # === 1️⃣ Prevent changes from Done ===
            if record.state == 'done' and new_state != 'done':
                raise ValidationError(_("You cannot modify a maintenance request that is already marked as Done."))

            # === 2️⃣ Cancelled rules ===
            if record.state == 'cancelled':
                if new_state != 'draft':
                    raise ValidationError(_("You can only move to Draft from the Cancelled status."))

            # === 3️⃣ Draft rules ===
            if record.state == 'draft':
                if new_state not in ['in_progress', 'cancelled']:
                    raise ValidationError(_("You can only move from Draft to In Progress or Cancelled."))

            # === 4️⃣ In Progress rules ===
            if record.state == 'in_progress':
                if new_state not in ['done', 'repaired', 'cancelled']:
                    raise ValidationError(_("You can only move from In Progress to Repaired or Cancelled."))

            # === 5️⃣ Repaired rules ===
            if record.state == 'repaired':
                if new_state not in ['done', 'cancelled']:
                    raise ValidationError(_("You can only move from Repaired to Done or Cancelled."))

            # === Update asset status automatically ===
            if new_state in ['in_progress', 'repaired']:
                if record.asset_id:
                    record.asset_id.write({
                        'status': 'maintenance',
                        'maintenance_required': True
                    })

            elif new_state == 'done':
                if record.asset_id:
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': False
                    })

            elif new_state == 'cancelled':
                if record.asset_id:
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': False
                    })
                # Log cancellation reason to chatter
                if 'cancellation_reason' in vals and vals['cancellation_reason']:
                    record.message_post(body=_('Maintenance Request Cancelled. Reason: %s') % vals['cancellation_reason'])

        # Save the record
        result = super(MaintenanceRequest, self).write(vals)

        # Update calendar events if state changed
        for record in self:
            old_state = old_states.get(record.id)
            if (old_state != record.state and record.state in ['in_progress', 'repaired', 'done', 'cancelled']) or 'scheduled_date' in vals:
                self.env['fits.maintenance.calendar'].update_calendar_for_request(record.id)

        return result

    def action_start_progress(self):
        """Set status to In Progress and update asset status"""
        for record in self:
            # Update asset status to maintenance
            if record.asset_id:
                record.asset_id.write({'status': 'maintenance'})
        self.write({'state': 'in_progress'})

    def action_mark_repaired(self):
        """Set status to Repaired and update asset status"""
        for record in self:
            # Update asset status to maintenance
            if record.asset_id:
                record.asset_id.write({'status': 'maintenance'})
        self.write({'state': 'repaired'})

    def action_mark_done(self):
        """Set status to Done and update asset status back to active"""
        for record in self:
            # Update asset status back to active
            if record.asset_id:
                # Check if asset has active recurrence
                has_active_recurrence = (record.asset_id.recurrence_pattern != 'none' and
                                       record.asset_id.recurrence_start_date and
                                       (record.asset_id.recurrence_interval or record.asset_id.recurrence_end_date))
                
                if has_active_recurrence:
                    # Keep maintenance_required as True if there's active recurrence
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': True  # Keep as True for recurrence
                    })
                else:
                    # Set maintenance_required to False if no recurrence
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': False
                    })
        self.write({
            'state': 'done',
            'scheduled_end_date': fields.Date.today()
        })

    def action_set_to_draft(self):
        """Set status back to Draft from Cancelled status"""
        for record in self:
            # If setting back to draft from cancelled, revert asset status
            if record.state == 'cancelled' and record.asset_id:
                # Check if asset has active recurrence
                has_active_recurrence = (record.asset_id.recurrence_pattern != 'none' and
                                       record.asset_id.recurrence_start_date and
                                       (record.asset_id.recurrence_interval or record.asset_id.recurrence_end_date))

                if has_active_recurrence:
                    # Keep maintenance_required as True if there's active recurrence
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': True  # Keep as True for recurrence
                    })
                else:
                    # Set maintenance_required to False if no recurrence
                    record.asset_id.write({
                        'status': 'active',
                        'maintenance_required': False
                    })
        self.write({'state': 'draft'})

    def action_cancel(self):
        """Open the cancellation wizard for the maintenance request"""
        self.ensure_one()
        return {
            'name': _('Cancel Maintenance Request'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'fits.maintenance.request.cancel',
            'target': 'new',
            'context': {
                'default_maintenance_request_id': self.id,
            },
        }

    @api.constrains('scheduled_date', 'scheduled_end_date')
    def _check_dates(self):
        for record in self:
            if record.scheduled_end_date and record.scheduled_date:
                if record.scheduled_end_date < record.scheduled_date:
                    raise ValidationError(_('Scheduled End date cannot be before Scheduled Start date.'))
