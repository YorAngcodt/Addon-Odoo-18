# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MaintenanceTeam(models.Model):
    _name = 'fits.maintenance.team'
    _description = 'Maintenance Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(
        string='Team Name',
        required=True,
        help='Name of the maintenance team'
    )

    member_ids = fields.Many2many(
        'hr.employee',
        string='Team Members',
        help='Employees who are members of this maintenance team'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to hide the team without removing it'
    )
