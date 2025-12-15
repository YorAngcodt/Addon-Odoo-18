# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from odoo.exceptions import UserError
from odoo.exceptions import AccessError

class OvertimeRequest(models.Model):
    _name = 'overtime.request'
    _description = 'Overtime Request'
    _rec_name = 'employee_id'
    _order = 'start_datetime desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic fields
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Manager', related='employee_id.parent_id', store=True, readonly=True)
    start_datetime = fields.Datetime(string='Start Date Time', required=True)
    end_datetime = fields.Datetime(string='End Date Time', required=True)
    description = fields.Text(string='Description', help='Reason for overtime request')
    include_in_payroll = fields.Boolean(string='Include In Payroll', default=True)

    # Request Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, tracking=True)

    # Overtime calculation fields
    total_hours = fields.Float(string='Total Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    # Weekday breakdown
    ot1_hours_weekday = fields.Float(string='OT1 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    ot2_hours_weekday = fields.Float(string='OT2 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    ot3_hours_weekday = fields.Float(string='OT3 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    overtime_breakdown_weekday = fields.Float(string='Total OT', compute='_compute_overtime_hours', store=True, readonly=True)
    # Day Off breakdown
    ot1_hours_off = fields.Float(string='OT1 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    ot2_hours_off = fields.Float(string='OT2 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    ot3_hours_off = fields.Float(string='OT3 Hours', compute='_compute_overtime_hours', store=True, readonly=True)
    overtime_breakdown_off = fields.Float(string='Total OT', compute='_compute_overtime_hours', store=True, readonly=True)
    overtime_configuration_id = fields.Many2one('overtime.configuration', string='Configuration', related='employee_id.overtime_configuration_id', store=True, readonly=True)

    # Configuration status related fields
    configuration_status = fields.Selection(related='overtime_configuration_id.status', string='Configuration Status', store=True, readonly=True)
    configuration_period = fields.Char(string='Configuration Period', compute='_compute_configuration_info', store=True, readonly=True)

    # Field untuk validasi calculation (hidden, untuk debugging saja)
    calculation_debug_info = fields.Text(string='Debug Info', compute='_compute_overtime_hours', store=False, readonly=True)

    # Tipe hari request (weekday/weekend/holiday) berdasarkan tanggal dan konfigurasi
    request_day_type = fields.Selection([
        ('weekday', 'Working Days'),
        ('off', 'Days Off'),
    ], string='Request Day Type', compute='_compute_request_day_type', store=True, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user
        # Kalau user bukan manager → otomatis isi employee
        if not user.has_group('fits_overtime.group_overtime_manager'):
            employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if employee:
                res['employee_id'] = employee.id
        return res

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        user = self.env.user
        if not user.has_group('fits_overtime.group_overtime_manager'):
            return {'domain': {'employee_id': [('user_id', '=', user.id)]}}
        else:
            return {'domain': {'employee_id': []}}  # Manager bisa lihat semua

    @api.depends('start_datetime', 'end_datetime', 'employee_id', 'employee_id.resource_calendar_id')
    def _compute_request_day_type(self):
        for record in self:
            day_type = False  # default kosong, tidak langsung 'weekday'

            if record.start_datetime and record.end_datetime and record.employee_id:
                weekday = record.start_datetime.weekday()  # 0=Senin ... 6=Minggu
                calendar = record.employee_id.resource_calendar_id

                if calendar:
                    # cek apakah hari itu libur
                    leave = self.env['resource.calendar.leaves'].search([
                        ('calendar_id', '=', calendar.id),
                        ('date_from', '<=', record.start_datetime),
                        ('date_to', '>=', record.start_datetime),
                    ], limit=1)

                    if leave:
                        day_type = 'off'
                    else:
                        # cek apakah ada jadwal kerja di hari tersebut
                        has_working_time = calendar.attendance_ids.filtered(
                            lambda att: att.dayofweek == str(weekday)
                        )
                        day_type = 'weekday' if has_working_time else 'off'
                else:
                    # fallback kalau tidak ada calendar
                    day_type = 'weekday' if weekday < 5 else 'off'

            record.request_day_type = day_type


    @api.depends('start_datetime', 'end_datetime', 'employee_id.overtime_configuration_id', 'employee_id.overtime_configuration_id.line_ids', 'employee_id.overtime_configuration_id.status', 'request_day_type')
    def _compute_overtime_hours(self):
        """
        LOGIKA: Calculate overtime hours separately for weekday and day off based on request_day_type
        """
        for record in self:
            # Reset all values to 0
            record.ot1_hours_weekday = 0.0
            record.ot2_hours_weekday = 0.0
            record.ot3_hours_weekday = 0.0
            record.overtime_breakdown_weekday = 0.0
            record.ot1_hours_off = 0.0
            record.ot2_hours_off = 0.0
            record.ot3_hours_off = 0.0
            record.overtime_breakdown_off = 0.0
            record.calculation_debug_info = "No calculation"

            # Basic validation
            if not record.employee_id or not record.start_datetime or not record.end_datetime:
                record.calculation_debug_info = "Missing employee or datetime"
                continue

            # Calculate total hours
            total_duration = (record.end_datetime - record.start_datetime).total_seconds() / 3600.0
            record.total_hours = total_duration

            # Get configuration
            config = record.employee_id.overtime_configuration_id
            if not config:
                record.calculation_debug_info = "No configuration assigned to employee"
                continue

            # Check if configuration is applicable
            request_date = record.start_datetime.date()
            is_applicable, message = config.is_rule_applicable(request_date)
            if not is_applicable:
                record.calculation_debug_info = f"Configuration not applicable: {message}"
                continue

            # Calculate breakdown based on request_day_type
            breakdown = config.with_context(employee_id=record.employee_id.id).calculate_overtime_for_request(record.start_datetime, record.end_datetime)
            
            # Set request_day_type using employee's working calendar
            record.request_day_type = config.get_day_type(request_date, record.employee_id)

            # Assign breakdown to appropriate fields based on request_day_type
            if record.request_day_type == 'weekday':
                record.ot1_hours_weekday = breakdown['ot1']
                record.ot2_hours_weekday = breakdown['ot2']
                record.ot3_hours_weekday = breakdown['ot3']
                record.overtime_breakdown_weekday = breakdown['total']
            else:  # 'off'
                record.ot1_hours_off = breakdown['ot1']
                record.ot2_hours_off = breakdown['ot2']
                record.ot3_hours_off = breakdown['ot3']
                record.overtime_breakdown_off = breakdown['total']
            
            record.calculation_debug_info = breakdown['message']

    @api.depends('overtime_configuration_id', 'overtime_configuration_id.date_start', 'overtime_configuration_id.date_end')
    def _compute_configuration_info(self):
        for record in self:
            if record.overtime_configuration_id:
                config = record.overtime_configuration_id
                if config.date_start and config.date_end:
                    # ubah format ke dd/mm/YYYY
                    start_date = fields.Date.to_date(config.date_start).strftime('%d/%m/%Y')
                    end_date = fields.Date.to_date(config.date_end).strftime('%d/%m/%Y')
                    record.configuration_period = f"{start_date} - {end_date}"
                else:
                    record.configuration_period = "Tanggal belum lengkap"
            else:
                record.configuration_period = "No configuration assigned"

    def _calculate_breakdown_from_configuration_totals(self, config):
        """
        LOGIKA INTI: Calculate breakdown berdasarkan configuration dengan validasi lengkap
        """
        result = {
            'ot1': 0.0,
            'ot2': 0.0,
            'ot3': 0.0,
            'total': 0.0,
            'message': ''
        }

        try:
            # STEP 1: Validasi configuration
            if not self._validate_configuration_status(config):
                result['message'] = "Configuration validation failed"
                return result

            # STEP 2: Validasi datetime request
            if not self._validate_request_datetime():
                result['message'] = "Request datetime validation failed"
                return result

            # STEP 3: Boundary check (pengecekan jam)
            boundary_check = self._perform_boundary_check(config)

            if not boundary_check['has_overlap']:
                result['message'] = boundary_check['message']
                return result

            # STEP 4: Calculate breakdown
            breakdown = self._calculate_overlap_breakdown(config, boundary_check)

            result.update(breakdown)
            result['message'] = f"Calculation successful: {breakdown['total']:.2f}h total"

            return result

        except Exception as e:
            result['message'] = f"Calculation error: {str(e)}"
            return result

    def _validate_configuration_status(self, config):
        """
        Validasi status konfigurasi
        """
        if not config:
            return False

        # Cek status configuration harus active
        if config.status != 'active':
            return False

        # Cek harus ada configuration lines
        if not config.line_ids:
            return False

        # Cek periode configuration
        request_date = self.start_datetime.date()
        is_applicable, _ = config.is_rule_applicable(request_date)

        return is_applicable

    def _validate_request_datetime(self):
        """
        Validasi datetime request
        """
        if not self.start_datetime or not self.end_datetime:
            return False

        # Cek start_datetime harus sebelum end_datetime
        if self.start_datetime >= self.end_datetime:
            return False

        return True

    def _perform_boundary_check(self, config):
        """
        PENGECEKAN JAM (BOUNDARY CHECK) - Logika inti dengan perbaikan cross-day handling
        """
        result = {
            'has_overlap': False,
            'overlap_details': [],
            'total_overlap_duration': 0.0,
            'message': ''
        }

        # PERBAIKAN: Better datetime to time float conversion
        request_start_time, request_end_time = self._convert_datetime_to_time_float()

        if request_start_time is None or request_end_time is None:
            result['message'] = "Invalid datetime conversion"
            return result

        # Boundary check untuk setiap configuration line
        for line in config.line_ids:
            # PERBAIKAN: Handle multiple day scenarios
            overlap_details = self._calculate_line_overlap(
                request_start_time, request_end_time, line
            )

            if overlap_details['has_overlap']:
                result['has_overlap'] = True
                result['overlap_details'].append({
                    'ot_type': line.type,
                    'line_start': line.start_time,
                    'line_end': line.end_time,
                    'overlap_start': overlap_details['overlap_start'],
                    'overlap_end': overlap_details['overlap_end'],
                    'overlap_duration': overlap_details['overlap_duration']
                })
                result['total_overlap_duration'] += overlap_details['overlap_duration']

        if result['has_overlap']:
            result['message'] = f"Found {len(result['overlap_details'])} overlapping boundaries, total: {result['total_overlap_duration']:.2f}h"
        else:
            result['message'] = f"Request time ({request_start_time:.2f}-{request_end_time:.2f}) outside configuration boundaries"

        return result

    def _calculate_overlap_breakdown(self, config, boundary_check):
        """
        Calculate breakdown berdasarkan overlap yang ditemukan di boundary check
        """
        # config parameter tidak digunakan dalam method ini, tapi dipertahankan untuk consistency
        _ = config  # Suppress unused parameter warning
        breakdown_result = {
            'ot1': 0.0,
            'ot2': 0.0,
            'ot3': 0.0,
            'total': 0.0
        }

        # Process setiap overlap yang ditemukan
        for overlap_detail in boundary_check['overlap_details']:
            ot_type = overlap_detail['ot_type']
            overlap_duration = overlap_detail['overlap_duration']

            # Assign ke breakdown sesuai OT type
            if ot_type == 'ot1':
                breakdown_result['ot1'] += overlap_duration
            elif ot_type == 'ot2':
                breakdown_result['ot2'] += overlap_duration
            elif ot_type == 'ot3':
                breakdown_result['ot3'] += overlap_duration

        # Round to 2 decimal places
        breakdown_result['ot1'] = round(breakdown_result['ot1'], 2)
        breakdown_result['ot2'] = round(breakdown_result['ot2'], 2)
        breakdown_result['ot3'] = round(breakdown_result['ot3'], 2)
        breakdown_result['total'] = breakdown_result['ot1'] + breakdown_result['ot2'] + breakdown_result['ot3']

        return breakdown_result

    def _convert_datetime_to_time_float(self):
        """
        PERBAIKAN: Convert datetime to time float dengan handling yang lebih baik
        Returns: (start_time_float, end_time_float) atau (None, None) jika error
        """
        try:
            # Check if start and end are on the same date
            start_date = self.start_datetime.date()
            end_date = self.end_datetime.date()

            # Convert to time float dengan presisi detik
            start_time_float = self.start_datetime.hour + (self.start_datetime.minute / 60.0) + (self.start_datetime.second / 3600.0)
            end_time_float = self.end_datetime.hour + (self.end_datetime.minute / 60.0) + (self.end_datetime.second / 3600.0)

            # Handle cross-day scenarios
            if end_date > start_date:
                # Calculate days difference
                days_diff = (end_date - start_date).days
                end_time_float += (days_diff * 24)
            elif end_date < start_date:
                # Invalid: end date before start date
                return None, None

            return start_time_float, end_time_float

        except (AttributeError, TypeError):
            # Handle None values or invalid datetime objects
            return None, None

    def _calculate_line_overlap(self, request_start_time, request_end_time, line):
        """
        PERBAIKAN: Calculate overlap between request time dan configuration line
        dengan handling yang lebih akurat untuk multi-day scenarios
        """
        result = {
            'has_overlap': False,
            'overlap_start': 0.0,
            'overlap_end': 0.0,
            'overlap_duration': 0.0
        }

        # Handle same-day scenario (most common case)
        if request_end_time <= 24.0:
            # Single day request - standard overlap calculation
            overlap_start = max(request_start_time, line.start_time)
            overlap_end = min(request_end_time, line.end_time)

            if overlap_start < overlap_end:
                result['has_overlap'] = True
                result['overlap_start'] = overlap_start
                result['overlap_end'] = overlap_end
                result['overlap_duration'] = overlap_end - overlap_start
        else:
            # Multi-day request - calculate overlap per day
            total_duration = 0.0
            first_overlap_start = None
            last_overlap_end = None

            # Day 1: from request_start to end of day (24.0)
            day1_start = request_start_time
            day1_end = 24.0

            overlap_start = max(day1_start, line.start_time)
            overlap_end = min(day1_end, line.end_time)

            if overlap_start < overlap_end:
                day1_duration = overlap_end - overlap_start
                total_duration += day1_duration
                first_overlap_start = overlap_start
                last_overlap_end = overlap_end

            # Day 2+: handle remaining time
            remaining_time = request_end_time - 24.0
            if remaining_time > 0:
                # For subsequent days, configuration repeats
                day2_start = 0.0
                day2_end = remaining_time

                overlap_start = max(day2_start, line.start_time)
                overlap_end = min(day2_end, line.end_time)

                if overlap_start < overlap_end:
                    day2_duration = overlap_end - overlap_start
                    total_duration += day2_duration
                    if first_overlap_start is None:
                        first_overlap_start = overlap_start
                    last_overlap_end = overlap_end

            if total_duration > 0:
                result['has_overlap'] = True
                result['overlap_start'] = first_overlap_start
                result['overlap_end'] = last_overlap_end
                result['overlap_duration'] = total_duration

        return result

    def get_calculation_summary(self):
        """
        Get summary of calculation for display purposes
        """
        if not self.employee_id or not self.start_datetime or not self.end_datetime:
            return "Incomplete request data"

        config = self.employee_id.overtime_configuration_id
        if not config:
            return "No configuration assigned to employee"

        if config.status != 'active':
            return f"Configuration status: {config.status} (must be active)"

        request_date = self.start_datetime.date()
        is_applicable, message = config.is_rule_applicable(request_date)
        if not is_applicable:
            return f"Configuration not applicable: {message}"

        if self.request_day_type == 'weekday':
            if self.overtime_breakdown_weekday == 0:
                return "No overlap with configuration time ranges (Weekday)"
            return f"Weekday - OT1: {self.ot1_hours_weekday:.2f}h, OT2: {self.ot2_hours_weekday:.2f}h, OT3: {self.ot3_hours_weekday:.2f}h (Total: {self.overtime_breakdown_weekday:.2f}h)"
        else:
            if self.overtime_breakdown_off == 0:
                return "No overlap with configuration time ranges (Day Off)"
            return f"Day Off - OT1: {self.ot1_hours_off:.2f}h, OT2: {self.ot2_hours_off:.2f}h, OT3: {self.ot3_hours_off:.2f}h (Total: {self.overtime_breakdown_off:.2f}h)"

    def debug_breakdown_calculation(self):
        """
        DEBUG METHOD: Detailed debugging untuk troubleshoot kenapa breakdown = 0
        """
        debug_info = {
            'request_info': {},
            'config_info': {},
            'validation_steps': {},
            'calculation_steps': {},
            'final_result': {}
        }

        # STEP 1: Request Information
        debug_info['request_info'] = {
            'employee_name': self.employee_id.name if self.employee_id else 'No Employee',
            'start_datetime': str(self.start_datetime),
            'end_datetime': str(self.end_datetime),
            'start_date': str(self.start_datetime.date()) if self.start_datetime else 'None',
            'end_date': str(self.end_datetime.date()) if self.end_datetime else 'None',
            'total_hours_calculated': self.total_hours,
            'request_day_type': self.request_day_type,
        }

        # STEP 2: Configuration Information
        config = self.employee_id.overtime_configuration_id if self.employee_id else None
        if config:
            debug_info['config_info'] = {
                'config_name': config.name,
                'config_status': config.status,
                'config_period': f"{config.date_start} to {config.date_end}",
                'config_lines_count': len(config.line_ids),
                'config_lines_detail': []
            }

            for line in config.line_ids:
                debug_info['config_info']['config_lines_detail'].append({
                    'type': line.type,
                    'start_time': line.start_time,
                    'end_time': line.end_time,
                    'duration': line.end_time - line.start_time
                })
        else:
            debug_info['config_info'] = {'error': 'No configuration assigned to employee'}

        # STEP 3: Validation Steps
        debug_info['validation_steps']['step1_config_exists'] = config is not None

        if config:
            debug_info['validation_steps']['step2_config_status'] = config.status
            debug_info['validation_steps']['step3_config_has_lines'] = len(config.line_ids) > 0

            # Check if rule is applicable
            request_date = self.start_datetime.date() if self.start_datetime else None
            if request_date:
                is_applicable, message = config.is_rule_applicable(request_date)
                debug_info['validation_steps']['step4_rule_applicable'] = {
                    'result': is_applicable,
                    'message': message
                }

            # Check sequence validation
            sequence_issues = config.validate_overtime_sequence()
            debug_info['validation_steps']['step5_sequence_valid'] = {
                'is_valid': len(sequence_issues) == 0,
                'issues': sequence_issues
            }

        # STEP 4: Calculation Steps
        if self.start_datetime and self.end_datetime:
            # Convert datetime to float
            start_time_float, end_time_float = self._convert_datetime_to_time_float()
            debug_info['calculation_steps']['datetime_conversion'] = {
                'start_time_float': start_time_float,
                'end_time_float': end_time_float,
                'conversion_success': start_time_float is not None and end_time_float is not None
            }

            if config and start_time_float is not None and end_time_float is not None:
                # Boundary check details
                debug_info['calculation_steps']['boundary_check'] = []

                for line in config.line_ids:
                    overlap_start = max(start_time_float, line.start_time)
                    overlap_end = min(end_time_float, line.end_time)
                    has_overlap = overlap_start < overlap_end
                    overlap_duration = overlap_end - overlap_start if has_overlap else 0.0

                    debug_info['calculation_steps']['boundary_check'].append({
                        'line_type': line.type,
                        'line_start': line.start_time,
                        'line_end': line.end_time,
                        'request_start': start_time_float,
                        'request_end': end_time_float,
                        'overlap_start': overlap_start,
                        'overlap_end': overlap_end,
                        'has_overlap': has_overlap,
                        'overlap_duration': overlap_duration
                    })

        # STEP 5: Final Result
        debug_info['final_result'] = {
            'weekday': {
                'ot1_hours': self.ot1_hours_weekday,
                'ot2_hours': self.ot2_hours_weekday,
                'ot3_hours': self.ot3_hours_weekday,
                'breakdown_total': self.overtime_breakdown_weekday
            },
            'off': {
                'ot1_hours': self.ot1_hours_off,
                'ot2_hours': self.ot2_hours_off,
                'ot3_hours': self.ot3_hours_off,
                'breakdown_total': self.overtime_breakdown_off
            }
        }

        return debug_info

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime_validity(self):
        """Validate datetime fields"""
        for record in self:
            if record.start_datetime and record.end_datetime:
                if record.start_datetime >= record.end_datetime:
                    raise ValidationError("End datetime must be after start datetime")

    @api.constrains('employee_id')
    def _check_employee_configuration(self):
        """Check if employee has overtime configuration (warning only)"""
        for record in self:
            if record.employee_id and not record.employee_id.overtime_configuration_id:
                # This is just a warning, not blocking
                pass

    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            if record.employee_id:
                name = f"{record.employee_id.name} - {record.start_datetime.strftime('%Y-%m-%d %H:%M') if record.start_datetime else 'No Date'}"
            else:
                name = f"Overtime Request - {record.id}"
            result.append((record.id, name))
        return result

    @api.model
    def create(self, vals):
        """Override create to add sequence"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('overtime.request') or 'New'
        return super(OvertimeRequest, self).create(vals)



    def action_submit(self):
        """User submit overtime request dengan pop-up warning lebih detail dan chatter log"""
        for rec in self:
            employee_name = rec.employee_id.name if rec.employee_id else "Unknown"
            config = rec.employee_id.overtime_configuration_id

            # CASE 1: Employee belum punya configuration
            if not config:
                raise UserError(
                    f"⚠ Employee '{employee_name}' belum punya overtime configuration.\n\n"
                    "Harap hubungi manager untuk membuat configuration sebelum submit."
                )

            # CASE 2: Start/End di luar periode configuration
            start_date = rec.start_datetime.date()
            end_date = rec.end_datetime.date()
            config_start = config.date_start
            config_end = config.date_end

            if start_date < config_start or end_date > config_end:
                raise UserError(
                    f"⚠ Request Overtime untuk Employee '{employee_name}' berada di luar periode configuration.\n\n"
                    f"Request Start: {start_date}\n"
                    f"Request End: {end_date}\n"
                    f"Configuration Period: {config_start} - {config_end}\n\n"
                    "Harap ubah tanggal request atau update configuration."
                )

            # Jika valid, ubah status ke submitted
            rec.status = 'submitted'
            # Log ke chatter
            rec.message_post(
                body=f"Overtime request submitted oleh {self.env.user.name}."
            )

    def action_set_draft(self):
        """Reset to draft dengan chatter log"""
        for rec in self:
            rec.status = 'draft'
            rec.message_post(
                body=f"Overtime request dikembalikan ke draft oleh {self.env.user.name}."
            )

    def action_approve(self):
        """Manager approve request dengan pop-up warning dan chatter log"""
        for rec in self:
            employee_name = rec.employee_id.name if rec.employee_id else "Unknown"
            config = rec.employee_id.overtime_configuration_id

            # Validasi configuration sebelum approve
            if not config:
                raise UserError(
                    f"⚠ Employee '{employee_name}' belum punya configuration.\nTidak bisa approve request."
                )

            start_date = rec.start_datetime.date()
            end_date = rec.end_datetime.date()
            config_start = config.date_start
            config_end = config.date_end

            if start_date < config_start or end_date > config_end:
                raise UserError(
                    f"⚠ Request Overtime untuk Employee '{employee_name}' berada di luar periode configuration.\n"
                    f"Request Start: {start_date}\n"
                    f"Request End: {end_date}\n"
                    f"Configuration Period: {config_start} - {config_end}\n"
                    "Tidak bisa approve request."
                )

            # Jika valid, ubah status ke approved
            rec.status = 'approved'
            rec.message_post(
                body=f"Overtime request disetujui oleh {self.env.user.name}."
            )

    def action_reject(self):
        """Manager reject request dengan chatter log"""
        for rec in self:
            rec.status = 'rejected'
            rec.message_post(
                body=f"Overtime request ditolak oleh {self.env.user.name}."
            )

    def unlink(self):
        for rec in self:
            if rec.status != 'draft':
                raise UserError(
                    f"You can not delete an Overtime Request with status '{rec.status}'. "
                    "Only Draft can be deleted."
                )
        return super(OvertimeRequest, self).unlink()


