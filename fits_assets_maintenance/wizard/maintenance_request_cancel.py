# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MaintenanceRequestCancel(models.TransientModel):
    _name = 'fits.maintenance.request.cancel'
    _description = 'Maintenance Request Cancellation Wizard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    reason = fields.Text(string='Cancellation Reason', required=True)
    maintenance_request_id = fields.Many2one('fits.maintenance.request', string='Maintenance Request', required=True, ondelete='cascade')

    def action_confirm_cancel(self):
        self.ensure_one()
        if not self.reason:
            raise UserError(_('Please provide a reason for cancellation.'))
        
        # Update the maintenance request with cancellation reason and state
        self.maintenance_request_id.write({
            'cancellation_reason': self.reason,
            'state': 'cancelled'
        })
        
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
