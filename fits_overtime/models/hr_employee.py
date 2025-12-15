# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    overtime_configuration_id = fields.Many2one(
        'overtime.configuration', 
        string='Overtime Configuration',
        help='Overtime configuration assigned to this employee'
    )

    # Riwayat Lembur (Overtime History)
    overtime_request_ids = fields.One2many(
        'overtime.request', 'employee_id',
        string='Overtime Requests', readonly=True
    )
    overtime_request_count = fields.Integer(
        string='Overtime Count', compute='_compute_overtime_request_count', store=False
    )

    @api.depends('overtime_request_ids')
    def _compute_overtime_request_count(self):
        for emp in self:
            emp.overtime_request_count = len(emp.overtime_request_ids)

    def action_open_overtime_history(self):
        self.ensure_one()
        return {
            'name': 'Overtime History',
            'type': 'ir.actions.act_window',
            'res_model': 'overtime.request',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
            }
        }
