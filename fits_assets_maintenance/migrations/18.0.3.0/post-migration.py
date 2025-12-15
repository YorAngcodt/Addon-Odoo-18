from odoo import api, SUPERUSER_ID

def migrate_maintenance_request_scheduled_fields_post(cr, version):
    """Post-migration function to handle scheduled_date and scheduled_end_date field type change"""
    if not version:
        return

    # Verify that the migration was successful
    cr.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'fits_maintenance_request'
        AND column_name IN ('scheduled_date', 'scheduled_end_date')
    """)

    columns = cr.fetchall()
    print(f"Post-migration: Verified columns in fits_maintenance_request table:")
    for column in columns:
        print(f"  - {column[0]}: {column[1]} (nullable: {column[2]})")

    # Check if there are any maintenance requests with these fields
    cr.execute("""
        SELECT COUNT(*) FROM fits_maintenance_request
        WHERE scheduled_date IS NOT NULL OR scheduled_end_date IS NOT NULL
    """)

    count = cr.fetchone()[0]
    print(f"Post-migration: Found {count} maintenance requests with scheduled dates")

    print("Post-migration completed successfully")
