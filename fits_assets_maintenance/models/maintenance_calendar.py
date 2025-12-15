# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta


class MaintenanceCalendar(models.Model):
    _name = 'fits.maintenance.calendar'
    _description = 'Maintenance Calendar'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Event Name', compute='_compute_name', store=True)
    asset_id = fields.Many2one('fits.asset', string='Asset', required=True)
    maintenance_date = fields.Date(string='Maintenance Date', required=True)
    description = fields.Text(string='Description', related='asset_id.notes', store=False)
    recurrence_pattern = fields.Selection(related='asset_id.recurrence_pattern', store=False)
    responsible_person_id = fields.Many2one(related='asset_id.responsible_person_id', store=False)

    # New fields for Maintenance Results and Team from Maintenance Requests
    hasil_status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('repaired', 'Repaired'),
        ('cancelled', 'Cancelled'),
        ('done', 'Done')
    ], string='Status', help='Maintenance result status from maintenance requests', readonly=True)

    team_id = fields.Many2one('fits.maintenance.team', string='Team', help='Maintenance team assigned to this asset', readonly=True)

    # Additional fields from Maintenance Requests
    maintenance_responsible_id = fields.Many2one('res.users', string='Responsible', help='Responsible person from maintenance request', readonly=True)
    maintenance_email = fields.Char(string='Email', help='Email from maintenance request', readonly=True)

    # Team Members from the selected team
    team_members_ids = fields.Many2many('hr.employee', string='Team Members', 
                                       related='team_id.member_ids', store=False, readonly=True)

    # Additional asset detail fields for Basic Information
    main_asset_id = fields.Many2one('fits.main.assets', string='Main Asset', related='asset_id.main_asset_selection', store=False, readonly=True)
    asset_category_id = fields.Many2one('fits.asset.category', string='Asset Category', related='asset_id.category_id', store=False, readonly=True)
    location_asset_id = fields.Many2one('fits.location.assets', string='Location Assets', related='asset_id.location_asset_selection', store=False, readonly=True)
    asset_code = fields.Char(string='Kode Asset', related='asset_id.serial_number_code', store=False, readonly=True)
    asset_condition = fields.Selection([
        ('new', 'Baru'),
        ('good', 'Baik'),
        ('minor_damage', 'Rusak Ringan'),
        ('major_damage', 'Rusak Berat')
    ], string='Condition', related='asset_id.condition', store=False, readonly=True)

    # Recurrence fields from asset
    recurrence_start_date = fields.Date(string='Recurrence Start Date', related='asset_id.recurrence_start_date', store=False, readonly=True)
    recurrence_interval = fields.Integer(string='Recurrence Interval', related='asset_id.recurrence_interval', store=False, readonly=True)
    recurrence_end_date = fields.Date(string='Recurrence End Date', related='asset_id.recurrence_end_date', store=False, readonly=True)

    def unlink(self):
        """Override unlink to remove schedule-based deletion constraints"""
        # Removed validation for past and current dates - events can now be deleted anytime
        # If all checks pass, proceed with deletion
        return super(MaintenanceCalendar, self).unlink()

    @api.depends('asset_id', 'maintenance_date')
    def _compute_name(self):
        for record in self:
            if record.asset_id and record.maintenance_date:
                record.name = f"Maintenance for {record.asset_id.name} on {record.maintenance_date}"
            else:
                record.name = 'Maintenance Event'

    def init(self):
        """Initialize the model and create events if context indicates"""
        super().init()
        if self.env.context.get('create_calendar_events'):
            self.create_calendar_events()

    @api.model
    def create_calendar_events(self):
        """Create calendar events from assets with recurrence settings and maintenance requests without duplicates"""
        print("DEBUG: Starting calendar event creation")

        # First, clean up any existing duplicates
        duplicates_removed = self.cleanup_duplicate_events()
        if duplicates_removed > 0:
            print(f"DEBUG: Cleaned up {duplicates_removed} duplicate events")

        events_to_create = []

        # 1. Create events from assets with recurrence settings
        assets = self.env['fits.asset'].search([
            ('recurrence_pattern', '!=', 'none'),
            ('recurrence_start_date', '!=', False),
            '|',
            ('recurrence_interval', '>', 0),
            ('recurrence_end_date', '!=', False),
            ('maintenance_required', '=', True),
            ('status', '=', 'maintenance')
        ])

        print(f"DEBUG: Found {len(assets)} assets with recurrence settings")

        for asset in assets:
            # Generate maintenance dates based on recurrence pattern and settings
            maintenance_dates = []

            if asset.recurrence_pattern == 'daily':
                # For Daily: generate dates based on interval or end date
                if asset.recurrence_interval and asset.recurrence_interval > 0:
                    # Use interval: generate dates from start_date for interval number of occurrences
                    print(f"DEBUG: Creating DAILY events for {asset.name} with interval {asset.recurrence_interval} from {asset.recurrence_start_date}")

                    current_date = asset.recurrence_start_date
                    for i in range(asset.recurrence_interval):
                        maintenance_dates.append(current_date)
                        current_date = current_date + timedelta(days=1)

                    print(f"DEBUG: Generated {len(maintenance_dates)} daily maintenance dates using interval for {asset.name}")

                elif asset.recurrence_end_date:
                    # Use end date: generate dates from start_date to end_date
                    print(f"DEBUG: Creating DAILY events for {asset.name} from {asset.recurrence_start_date} to {asset.recurrence_end_date}")

                    current_date = asset.recurrence_start_date
                    while current_date <= asset.recurrence_end_date:
                        maintenance_dates.append(current_date)
                        current_date = current_date + timedelta(days=1)

                    print(f"DEBUG: Generated {len(maintenance_dates)} daily maintenance dates using end date for {asset.name}")
                else:
                    print(f"DEBUG: Asset {asset.name} has daily pattern but no interval or end date - skipping")

            else:
                # For Weekly, Monthly, Yearly: create events only for start and calculated end dates
                if asset.recurrence_start_date:
                    start_date = asset.recurrence_start_date
                    interval = asset.recurrence_interval or 1

                    # Hitung end date otomatis jika belum ada
                    from dateutil.relativedelta import relativedelta
                    if asset.recurrence_pattern == 'weekly':
                        end_date = start_date + timedelta(weeks=interval)
                    elif asset.recurrence_pattern == 'monthly':
                        end_date = start_date + relativedelta(months=interval)
                    elif asset.recurrence_pattern == 'yearly':
                        end_date = start_date + relativedelta(years=interval)
                    else:
                        end_date = start_date + timedelta(days=interval)

                    print(f"DEBUG: Creating {asset.recurrence_pattern.upper()} events for {asset.name} (Start: {start_date}, End: {end_date})")
                    maintenance_dates = [start_date, end_date]

            # Get the latest maintenance request for this asset to populate status and team info
            latest_request = self.env['fits.maintenance.request'].search([
                ('asset_id', '=', asset.id)
            ], order='create_date DESC', limit=1)

            # Set default values
            hasil_status = latest_request.state if latest_request else 'draft'
            team_id = latest_request.team_id.id if latest_request and latest_request.team_id else False
            maintenance_responsible_id = latest_request.user_id.id if latest_request and latest_request.user_id else False
            maintenance_email = latest_request.email if latest_request and latest_request.email else False

            # Create events for each maintenance date
            for maintenance_date in maintenance_dates:
                # Check if event already exists for this asset and date
                existing_event = self.search([
                    ('asset_id', '=', asset.id),
                    ('maintenance_date', '=', maintenance_date)
                ], limit=1)

                if not existing_event:
                    print(f"DEBUG: Creating calendar event for {asset.name} on {maintenance_date}")

                    events_to_create.append({
                        'asset_id': asset.id,
                        'maintenance_date': maintenance_date,
                        'hasil_status': hasil_status,
                        'team_id': team_id,
                        'maintenance_responsible_id': maintenance_responsible_id,
                        'maintenance_email': maintenance_email,
                    })
                else:
                    print(f"DEBUG: Event already exists for {asset.name} on {maintenance_date}")

        # 2. Create events from maintenance requests (only if no recurring event exists for same date)
        maintenance_requests = self.env['fits.maintenance.request'].search([
            ('scheduled_date', '!=', False)
        ])

        print(f"DEBUG: Found {len(maintenance_requests)} maintenance requests")

        for request in maintenance_requests:
            # Check if this is a recurring asset (has recurrence settings)
            asset_has_recurring = self.env['fits.asset'].search([
                ('id', '=', request.asset_id.id),
                ('recurrence_pattern', '!=', 'none'),
                ('recurrence_start_date', '!=', False),
                '|',
                ('recurrence_interval', '>', 0),
                ('recurrence_end_date', '!=', False),
                ('maintenance_required', '=', True),
                ('status', '=', 'maintenance')
            ], limit=1)

            # Check if event already exists for this exact asset and date
            existing_event = self.search([
                ('asset_id', '=', request.asset_id.id),
                ('maintenance_date', '=', request.scheduled_date)
            ], limit=1)

            # Only create event if:
            # 1. No existing event for this asset and date, OR
            # 2. Asset doesn't have recurring settings (so we need individual request events)
            if not existing_event and (not asset_has_recurring):
                print(f"DEBUG: Creating request event for {request.asset_id.name} on {request.scheduled_date}")

                events_to_create.append({
                    'asset_id': request.asset_id.id,
                    'maintenance_date': request.scheduled_date,
                    'hasil_status': request.state,
                    'team_id': request.team_id.id if request.team_id else False,
                    'maintenance_responsible_id': request.user_id.id if request.user_id else False,
                    'maintenance_email': request.email,
                })
            elif existing_event:
                print(f"DEBUG: Event already exists for request {request.id} - {request.asset_id.name} on {request.scheduled_date}")
            elif asset_has_recurring:
                print(f"DEBUG: Skipping request {request.id} - asset {request.asset_id.name} has recurring settings")

        # 3. Create all events in bulk (only if we have new events to create)
        if events_to_create:
            created_events = self.create(events_to_create)
            print(f"DEBUG: Successfully created {len(created_events)} new calendar events")
            return len(created_events)
        else:
            print("DEBUG: No new events to create (all events already exist)")
            return 0

    @api.model
    def cleanup_duplicate_events(self):
        """Clean up duplicate calendar events for the same asset and date"""
        print("DEBUG: Starting duplicate calendar events cleanup")

        # Find all events grouped by asset and date
        all_events = self.search([])

        # Group events by asset_id and maintenance_date
        event_groups = {}
        for event in all_events:
            key = (event.asset_id.id, event.maintenance_date)
            if key not in event_groups:
                event_groups[key] = []
            event_groups[key].append(event)

        # Remove duplicates, keeping only the first event for each asset-date combination
        removed_count = 0
        for key, events in event_groups.items():
            if len(events) > 1:
                # Keep the first event, remove the rest
                events_to_keep = events[0]
                events_to_remove = events[1:]

                print(f"DEBUG: Found {len(events)} duplicate events for asset {events[0].asset_id.name} on {events[0].maintenance_date}")

                for event in events_to_remove:
                    print(f"DEBUG: Removing duplicate event {event.id}")
                    event.unlink()
                    removed_count += 1

        print(f"DEBUG: Cleanup complete - removed {removed_count} duplicate events")
        return removed_count

    def action_create_maintenance_request(self):
        """Create a new maintenance request from calendar event"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Maintenance Request',
            'res_model': 'fits.maintenance.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_asset_id': self.asset_id.id,
                'default_scheduled_date': self.maintenance_date,
                'default_user_id': self.maintenance_responsible_id.id if self.maintenance_responsible_id else self.env.user.id,
                'default_team_id': self.team_id.id if self.team_id else False,
                'default_maintenance_request_title': f'Maintenance for {self.asset_id.name}',
                'default_description': f'Scheduled maintenance on {self.maintenance_date}',
            }
        }

    @api.model
    def update_calendar_for_request(self, request_id):
        """Update calendar events for a specific maintenance request without creating duplicates"""
        request = self.env['fits.maintenance.request'].browse(request_id)
        if not request:
            return 0

        print(f"DEBUG: Updating calendar for maintenance request {request.id} - State: {request.state}")

        # Find existing event for this maintenance request by asset and scheduled date
        existing_event = self.search([
            ('asset_id', '=', request.asset_id.id),
            ('maintenance_date', '=', request.scheduled_date if request.scheduled_date else False)
        ], limit=1)

        if existing_event:
            # Update existing event status and details
            print(f"DEBUG: Updating existing event status to {request.state}")
            existing_event.write({
                'hasil_status': request.state,
                'team_id': request.team_id.id if request.team_id else False,
                'maintenance_responsible_id': request.user_id.id if request.user_id else False,
                'maintenance_email': request.email,
            })
            return 1
        else:
            # Only create new event if this request doesn't have a corresponding recurring event
            asset_has_recurring = self.env['fits.asset'].search([
                ('id', '=', request.asset_id.id),
                ('recurrence_pattern', '!=', 'none'),
                ('recurrence_start_date', '!=', False),
                '|',
                ('recurrence_interval', '>', 0),
                ('recurrence_end_date', '!=', False),
                ('maintenance_required', '=', True),
                ('status', '=', 'maintenance')
            ], limit=1)

            # If asset has recurring settings, don't create individual request events (they're handled by recurrence)
            if asset_has_recurring:
                print(f"DEBUG: Asset {request.asset_id.name} has recurring settings - not creating individual request event")
                return 0

            # Create new event only for non-recurring assets
            print(f"DEBUG: Creating new event for maintenance request {request.id}")
            self.create({
                'asset_id': request.asset_id.id,
                'maintenance_date': request.scheduled_date if request.scheduled_date else fields.Date.today(),
                'hasil_status': request.state,
                'team_id': request.team_id.id if request.team_id else False,
                'maintenance_responsible_id': request.user_id.id if request.user_id else False,
                'maintenance_email': request.email,
            })
            return 1
