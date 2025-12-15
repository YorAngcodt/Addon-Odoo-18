from odoo import api, SUPERUSER_ID

def migrate_maintenance_request_scheduled_fields(cr, version):
    """Migration function to handle scheduled_date and scheduled_end_date field type change from Datetime to Date"""
    if not version:
        return

    # The field type change from Datetime to Date will automatically convert existing datetime values to date values
    # by taking only the date part. This migration script documents this change.

    # No data migration is needed as Odoo handles the conversion automatically when changing field types
    # from Datetime to Date. The time portion of existing datetime values will be discarded.

    print("Migration: Changed scheduled_date and scheduled_end_date fields from Datetime to Date in fits.maintenance.request")
    print("Existing datetime values have been automatically converted to date values (time portion discarded)")
