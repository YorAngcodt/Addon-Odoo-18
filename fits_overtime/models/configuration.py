from odoo import models, fields, api
from datetime import datetime, time
from babel.dates import format_date
from odoo.exceptions import UserError, AccessError


class OvertimeConfiguration(models.Model):
    _name = 'overtime.configuration'
    _description = 'Overtime Configuration'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True)
    line_ids = fields.One2many('overtime.configuration.line', 'configuration_id', string='Overtime Lines')

    # Rule/Aturan fields - Kapan aturan ini berlaku
    date_start = fields.Date(string='Valid From Date', required=True, default=fields.Date.today,
                            help='Tanggal mulai aturan lembur ini berlaku')
    date_end = fields.Date(string='Valid Until Date', required=True,
                          help='Tanggal berakhir aturan lembur ini berlaku')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
    ], string='Status', default='draft', required=True,
       help='Status aturan lembur: hanya yang Active yang bisa digunakan')

    # Datetime Float Range fields untuk pengecekan yang lebih akurat
    range_start_time = fields.Float(string='Range Start Time', compute='_compute_datetime_range', store=True,
                                   help='Waktu mulai rentang configuration (dalam format float)')
    range_end_time = fields.Float(string='Range End Time', compute='_compute_datetime_range', store=True,
                                 help='Waktu akhir rentang configuration (dalam format float)')
    range_duration = fields.Float(string='Range Duration', compute='_compute_datetime_range', store=True,
                                 help='Durasi total rentang configuration (dalam jam)')

    # Total fields untuk summary
    total_ot1_hours = fields.Float(string='Total OT1 Hours', compute='_compute_total_hours', store=True)
    total_ot2_hours = fields.Float(string='Total OT2 Hours', compute='_compute_total_hours', store=True)
    total_ot3_hours = fields.Float(string='Total OT3 Hours', compute='_compute_total_hours', store=True)
    total_overtime_hours = fields.Float(string='Total Overtime Hours', compute='_compute_total_hours', store=True)

    # Validation fields
    sequence_valid = fields.Boolean(string='Sequence Valid', compute='_compute_sequence_validation', store=True)
    sequence_status = fields.Char(string='Sequence Status', compute='_compute_sequence_validation', store=True)

    # Display fields untuk UI
    period_display = fields.Char(string='Period', compute='_compute_period_display', store=True)
    lines_count = fields.Integer(string='Lines Count', compute='_compute_lines_count')

    @api.depends('line_ids', 'line_ids.type', 'line_ids.start_time', 'line_ids.end_time')
    def _compute_total_hours(self):
        for record in self:
            ot1_total = 0.0
            ot2_total = 0.0
            ot3_total = 0.0

            for line in record.line_ids:
                duration = line.end_time - line.start_time
                if line.type == 'ot1':
                    ot1_total += duration
                elif line.type == 'ot2':
                    ot2_total += duration
                elif line.type == 'ot3':
                    ot3_total += duration

            record.total_ot1_hours = ot1_total
            record.total_ot2_hours = ot2_total
            record.total_ot3_hours = ot3_total
            record.total_overtime_hours = ot1_total + ot2_total + ot3_total
  
    @api.depends('date_start', 'date_end')
    def _compute_period_display(self):
        for record in self:
            if record.date_start and record.date_end:
                start_str = format_date(record.date_start, format="MM/dd/yyyy", locale="id_ID")
                end_str = format_date(record.date_end, format="MM/dd/yyyy", locale="id_ID")
                record.period_display = f"{start_str} - {end_str}"
            elif record.date_start:
                record.period_display = format_date(record.date_start, format="MM/dd/yyyy", locale="id_ID")
            else:
                record.period_display = "No period set"

    @api.depends('line_ids')
    def _compute_lines_count(self):
        for record in self:
            record.lines_count = len(record.line_ids)

    @api.depends('line_ids', 'line_ids.start_time', 'line_ids.end_time')
    def _compute_datetime_range(self):
        for record in self:
            if not record.line_ids:
                record.range_start_time = 0.0
                record.range_end_time = 0.0
                record.range_duration = 0.0
                continue

            min_start_time = float('inf')
            max_end_time = float('-inf')

            for line in record.line_ids:
                min_start_time = min(min_start_time, line.start_time)
                max_end_time = max(max_end_time, line.end_time)

            record.range_start_time = min_start_time if min_start_time != float('inf') else 0.0
            record.range_end_time = max_end_time if max_end_time != float('-inf') else 0.0
            record.range_duration = record.range_end_time - record.range_start_time

    @api.depends('line_ids', 'line_ids.type', 'line_ids.start_time')
    def _compute_sequence_validation(self):
        for record in self:
            issues = record.validate_overtime_sequence()
            record.sequence_valid = len(issues) == 0
            record.sequence_status = "Valid Sequence" if record.sequence_valid else "Invalid: " + "; ".join(issues)

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.name))
        return result

    def get_overtime_type_for_time(self, time_float):
        for line in self.line_ids:
            if line.start_time <= time_float < line.end_time:
                return line.type
        return False

    def validate_overtime_sequence(self):
        issues = []
        if not self.line_ids:
            issues.append("Configuration has no overtime lines")
            return issues

        week_types = ['weekday', 'off']
        for wtype in week_types:
            group_lines = self.line_ids.filtered(lambda l: l.type_week == wtype)
            if not group_lines:
                continue

            ot1_lines = group_lines.filtered(lambda l: l.type == 'ot1')
            ot2_lines = group_lines.filtered(lambda l: l.type == 'ot2')
            ot3_lines = group_lines.filtered(lambda l: l.type == 'ot3')

            ot1_min_start = min(ot1_lines.mapped('start_time')) if ot1_lines else float('inf')
            ot2_min_start = min(ot2_lines.mapped('start_time')) if ot2_lines else float('inf')
            ot3_min_start = min(ot3_lines.mapped('start_time')) if ot3_lines else float('inf')

            label = 'Working Days' if wtype == 'weekday' else 'Days Off'

            if ot1_lines and ot2_lines and ot1_min_start >= ot2_min_start:
                issues.append(f"[{label}] OT1 start time ({ot1_min_start}) must be earlier than OT2 start time ({ot2_min_start})")
            if ot2_lines and ot3_lines and ot2_min_start >= ot3_min_start:
                issues.append(f"[{label}] OT2 start time ({ot2_min_start}) must be earlier than OT3 start time ({ot3_min_start})")
            if ot1_lines and ot3_lines and ot1_min_start >= ot3_min_start:
                issues.append(f"[{label}] OT1 start time ({ot1_min_start}) must be earlier than OT3 start time ({ot3_min_start})")

            all_lines = sorted(group_lines, key=lambda l: l.start_time)
            for i in range(len(all_lines) - 1):
                current_line = all_lines[i]
                next_line = all_lines[i + 1]
                if current_line.type != next_line.type and current_line.end_time > next_line.start_time:
                    issues.append(f"[{label}] Overlap between {current_line.type.upper()} ({current_line.start_time}-{current_line.end_time}) and {next_line.type.upper()} ({next_line.start_time}-{next_line.end_time})")

        for line in self.line_ids:
            if line.start_time >= line.end_time:
                issues.append(f"{line.type.upper()}: start_time ({line.start_time}) must be less than end_time ({line.end_time})")
            if line.start_time < 0 or line.start_time >= 24:
                issues.append(f"{line.type.upper()}: start_time ({line.start_time}) must be between 0 and 24")
            if line.end_time <= 0 or line.end_time > 24:
                issues.append(f"{line.type.upper()}: end_time ({line.end_time}) must be between 0 and 24")

        return issues

    def is_valid_sequence(self):
        issues = self.validate_overtime_sequence()
        return len(issues) == 0

    def is_rule_applicable(self, request_date):
        if self.status != 'active':
            return False, f"Configuration status is {self.status}, must be 'active'"
        if not self.line_ids:
            return False, "Configuration has no overtime lines"
        if not self.is_valid_sequence():
            return False, "Configuration has invalid sequence"
        if not (self.date_start <= request_date <= self.date_end):
            return False, f"Request date {request_date} is outside rule period ({self.date_start} to {self.date_end})"

        day_type = self.get_day_type(request_date)
        day_lines = self.line_ids.filtered(lambda l: l.type_week == 'weekday' if day_type == 'weekday' else l.type_week == 'off')
        if not day_lines:
            label = 'Working Days' if day_type == 'weekday' else 'Days Off'
            return False, f"No overtime lines configured for day type '{label}'"

        return True, f"Rule is applicable for {day_type}"

    def get_day_type(self, request_date, employee=None):
        day_of_week = request_date.weekday()
        
        # If employee provided, use their working calendar
        if employee and employee.resource_calendar_id:
            calendar = employee.resource_calendar_id
            
            # Check for public holidays/leaves
            start_dt = datetime.combine(request_date, time.min)
            end_dt = datetime.combine(request_date, time.max)
            leaves = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('date_from', '<=', end_dt),
                ('date_to', '>=', start_dt),
            ], limit=1)
            
            if leaves:
                return 'off'
            
            # Check if there's working time for this day
            has_working_time = calendar.attendance_ids.filtered(
                lambda att: att.dayofweek == str(day_of_week)
            )
            return 'weekday' if has_working_time else 'off'
        
        # Fallback to default logic
        return 'weekday' if day_of_week < 5 else 'off'

    def calculate_overtime_for_request(self, start_datetime, end_datetime):
        breakdown_result = {
            'ot1': 0.0,
            'ot2': 0.0,
            'ot3': 0.0,
            'total': 0.0,
            'message': ''
        }

        request_date = start_datetime.date()
        is_applicable, message = self.is_rule_applicable(request_date)

        if not is_applicable:
            breakdown_result['message'] = f"Rule not applicable: {message}"
            return breakdown_result

        debug_parts = []
        debug_parts.append(f"StartDT: {start_datetime}")
        debug_parts.append(f"EndDT: {end_datetime}")

        from datetime import timedelta
        local_offset = timedelta(hours=7)
        start_datetime_local = start_datetime + local_offset
        end_datetime_local = end_datetime + local_offset

        debug_parts.append(f"StartDT_Local: {start_datetime_local}")
        debug_parts.append(f"EndDT_Local: {end_datetime_local}")

        start_time_float = start_datetime_local.hour + (start_datetime_local.minute / 60.0)
        end_time_float = end_datetime_local.hour + (end_datetime_local.minute / 60.0)

        debug_parts.append(f"TimeFloat: {start_time_float}-{end_time_float}")
        debug_parts.append(f"Request: {start_time_float}-{end_time_float}")

        # Get employee from context if available
        employee = self.env.context.get('employee_id')
        if employee:
            employee = self.env['hr.employee'].browse(employee)
        
        day_type = self.get_day_type(request_date, employee)
        debug_parts.append(f"DayType: {day_type}")
        lines = self.line_ids.filtered(lambda l: l.type_week == day_type)
        if not lines:
            label = 'Working Days' if day_type == 'weekday' else 'Days Off'
            breakdown_result['message'] = f"No overtime lines for day type '{label}'"
            return breakdown_result

        if end_time_float < start_time_float:
            end_time_float += 24
            debug_parts.append("Cross-day adjusted")

        for line in lines:
            overlap_start = max(start_time_float, line.start_time)
            overlap_end = min(end_time_float, line.end_time)
            line_debug = f"{line.type.upper()}({line.start_time}-{line.end_time}): overlap({overlap_start}-{overlap_end})"

            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                line_debug += f" = {overlap_duration}h"
                if line.type == 'ot1':
                    breakdown_result['ot1'] += overlap_duration
                elif line.type == 'ot2':
                    breakdown_result['ot2'] += overlap_duration
                elif line.type == 'ot3':
                    breakdown_result['ot3'] += overlap_duration
            else:
                line_debug += " = 0h (no overlap)"

            debug_parts.append(line_debug)

        for ot_type in ['ot1', 'ot2', 'ot3']:
            breakdown_result[ot_type] = round(breakdown_result[ot_type], 2)

        breakdown_result['total'] = breakdown_result['ot1'] + breakdown_result['ot2'] + breakdown_result['ot3']
        result_summary = f"OT1:{breakdown_result['ot1']}h OT2:{breakdown_result['ot2']}h OT3:{breakdown_result['ot3']}h"
        breakdown_result['message'] = f"Rule: {self.name} | {' | '.join(debug_parts)} | Result: {result_summary}"

        return breakdown_result

    def action_activate(self):
        today = fields.Date.today()
        if self.date_end < today:
            raise models.ValidationError(
                f'Cannot activate configuration: End date ({self.date_end}) has already passed. '
                f'Please update the end date to a future date.'
            )
        self.status = 'active'
        return True

    def action_set_draft(self):
        self.status = 'draft'
        return True

    def check_datetime_within_range(self, request_start_time, request_end_time):
        result = {
            'is_within_range': False,
            'overlap_duration': 0.0,
            'message': ''
        }

        if not self.line_ids:
            result['message'] = "No configuration lines found"
            return result

        config_start = self.range_start_time
        config_end = self.range_end_time

        overlap_start = max(request_start_time, config_start)
        overlap_end = min(request_end_time, config_end)

        if overlap_start < overlap_end:
            result['is_within_range'] = True
            result['overlap_duration'] = overlap_end - overlap_start
            result['message'] = f"Datetime within range ({config_start:.2f}-{config_end:.2f}), overlap: {result['overlap_duration']:.2f}h"
        else:
            result['is_within_range'] = False
            result['overlap_duration'] = 0.0
            result['message'] = f"Datetime outside range ({config_start:.2f}-{config_end:.2f})"

        return result

    def unlink(self):
        for record in self:
            if record.status == 'active':
                raise UserError(
                    "You can not delete an active configuration. Please set it to draft first."
                )
        return super(OvertimeConfiguration, self).unlink()

class OvertimeConfigurationLine(models.Model):
    _name = 'overtime.configuration.line'
    _description = 'Overtime Configuration Line'
    _rec_name = 'type'

    configuration_id = fields.Many2one('overtime.configuration', string='Configuration', required=True, ondelete='cascade')
    type = fields.Selection([
        ('ot1', 'OT1'),
        ('ot2', 'OT2'),
        ('ot3', 'OT3'),
    ], string='Type', required=True, default='ot1')
    type_week = fields.Selection([
        ("weekday", "Working Days"),
        ("off", "Days Off"),
    ], string='Type Week', required=True, default='weekday', help='Tipe hari untuk overtime line')
    start_time = fields.Float(string='Start Time', required=True, help='Start time in 24-hour format (e.g., 17.0 for 17:00)')
    end_time = fields.Float(string='End Time', required=True, help='End time in 24-hour format (e.g., 18.0 for 18:00)')
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    time_display = fields.Char(string='Time Range', compute='_compute_time_display')

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.start_time and record.end_time:
                record.duration = record.end_time - record.start_time
            else:
                record.duration = 0.0

    @api.depends('start_time', 'end_time')
    def _compute_time_display(self):
        for record in self:
            if record.start_time and record.end_time:
                start_hour = int(record.start_time)
                start_min = int((record.start_time - start_hour) * 60)
                end_hour = int(record.end_time)
                end_min = int((record.end_time - end_hour) * 60)
                record.time_display = f"{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}"
            else:
                record.time_display = "No time set"

    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise models.ValidationError('End time must be greater than start time.')
            if record.start_time < 0 or record.start_time >= 24:
                raise models.ValidationError('Start time must be between 0 and 24.')
            if record.end_time < 0 or record.end_time >= 24:
                raise models.ValidationError('End time must be between 0 and 24.')

    @api.constrains('type', 'start_time', 'end_time', 'configuration_id')
    def _check_no_overlap_same_type(self):
        for record in self:
            if record.configuration_id:
                same_type_lines = record.configuration_id.line_ids.filtered(
                    lambda l: l.type == record.type and l.type_week == record.type_week and l.id != record.id
                )
                for other_line in same_type_lines:
                    if not (record.end_time <= other_line.start_time or other_line.end_time <= record.start_time):
                        raise models.ValidationError(
                            f'Overlapping time ranges for {record.type.upper()}: '
                            f'{record.start_time:02.0f}:00-{record.end_time:02.0f}:00 overlaps with '
                            f'{other_line.start_time:02.0f}:00-{other_line.end_time:02.0f}:00'
                        )

    @api.constrains('type', 'start_time', 'configuration_id')
    def _check_overtime_sequence(self):
        for record in self:
            if record.configuration_id:
                issues = record.configuration_id.validate_overtime_sequence()
                if issues:
                    raise models.ValidationError(
                        f'Invalid overtime sequence in configuration "{record.configuration_id.name}":\n' +
                        '\n'.join(issues) +
                        '\n\nRule: OT1 must start before OT2, OT2 must start before OT3'
                    )

    def name_get(self):
        result = []
        for record in self:
            start_hour = int(record.start_time)
            start_min = int((record.start_time - start_hour) * 60)
            end_hour = int(record.end_time)
            end_min = int((record.end_time - end_hour) * 60)
            name = f"{record.type.upper()} ({start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d})"
            result.append((record.id, name))
        return result