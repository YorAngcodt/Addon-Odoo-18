from odoo import models, fields, api

class OvertimeReporting(models.Model):
    _name = 'overtime.reporting'
    _description = 'Overtime Reporting'
    _auto = False

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        readonly=True
    )
    overtime_configuration_id = fields.Many2one(
        comodel_name='overtime.configuration',
        string='Overtime Configuration',
        readonly=True
    )
    start_datetime = fields.Datetime(
        string='Start Date',
        readonly=True
    )
    end_datetime = fields.Datetime(
        string='End Date',
        readonly=True
    )
    total_hours = fields.Float(
        string='Total Hours',
        readonly=True
    )
    request_status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        string='Status',
        readonly=True
    )
    request_day_type = fields.Selection(
        selection=[
            ('weekday', 'Working Days'),
            ('off', 'Days Off'),
        ],
        string='Day Type',
        readonly=True
    )
    # Field computed untuk menampilkan label
    day_type_label = fields.Char(
        string='Day Type Label',
        compute='_compute_day_type_label',
        readonly=True
    )
    overtime_request_id = fields.Many2one(
        comodel_name='overtime.request',
        string='Overtime Request',
        readonly=True
    )
    description = fields.Text(
        string='Description',
        readonly=True
    )

    @api.depends('request_day_type')
    def _compute_day_type_label(self):
        for rec in self:
            if rec.request_day_type == 'weekday':
                rec.day_type_label = 'Working Days'
            elif rec.request_day_type == 'off':
                rec.day_type_label = 'Days Off'
            else:
                rec.day_type_label = ''

    def init(self):
        self._cr.execute("""
            CREATE OR REPLACE VIEW overtime_reporting AS (
                SELECT 
                    id AS id,
                    employee_id,
                    overtime_configuration_id,
                    start_datetime,
                    end_datetime,
                    total_hours,
                    status AS request_status,
                    request_day_type,
                    id AS overtime_request_id,
                    description
                FROM overtime_request
                WHERE status IN ('approved', 'submitted', 'rejected')
            );
        """)
