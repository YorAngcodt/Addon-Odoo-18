from odoo import models, fields, api
from odoo.exceptions import UserError

class OvertimeReportingWizard(models.TransientModel):
    _name = 'overtime.reporting.wizard'
    _description = 'Overtime Reporting Wizard'

    employee_ids = fields.Many2many('hr.employee', string='Employees')
    overtime_configuration_id = fields.Many2one('overtime.configuration', string='Configuration')
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)

    def action_generate_report(self):
        domain = [
            ('start_datetime', '>=', self.date_from),
            ('start_datetime', '<=', self.date_to)
        ]
        
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        if self.overtime_configuration_id:
            domain.append(('overtime_configuration_id', '=', self.overtime_configuration_id.id))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Overtime Report - Filtered',
            'res_model': 'overtime.reporting',
            'view_mode': 'list,pivot,graph',
            'domain': domain,
            'target': 'current',
            'context': {
                'search_default_group_employee': 1,
                'create': False,
                'edit': False,
                'delete': False
            }
        }

    def action_print_pdf(self):
        if not self.date_from or not self.date_to:
            raise UserError(
                "Please specify both Start Date and End Date to generate the PDF report."
            )
        
        domain = [
            ('start_datetime', '>=', self.date_from),
            ('start_datetime', '<=', self.date_to)
        ]
        
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        if self.overtime_configuration_id:
            domain.append(('overtime_configuration_id', '=', self.overtime_configuration_id.id))

        records = self.env['overtime.reporting'].search(domain)
        
        if not records:
            raise UserError(
                "No overtime records found for the selected criteria.\n\n"
                "Please adjust your filters:\n"
                "- Check the date range\n"
                "- Verify employee selection\n"
                "- Confirm configuration settings"
            )

        # Pakai context untuk kirim date_from dan date_to dengan format MM/DD/YYYY
        return self.env.ref('fits_overtime.action_overtime_reporting_pdf').with_context(
            report_date_from=self.date_from.strftime('%m/%d/%Y'),
            report_date_to=self.date_to.strftime('%m/%d/%Y')
        ).report_action(records)
