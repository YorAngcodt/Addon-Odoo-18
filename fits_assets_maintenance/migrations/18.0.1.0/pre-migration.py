from odoo import api, SUPERUSER_ID

def migrate_asset_name_field(cr, version):
    """Migration function to handle asset_name field type change"""
    if not version:
        return

    # Drop the foreign key constraint if it exists
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name = 'fits_asset'
                AND constraint_name = 'fits_asset_asset_name_fkey'
            ) THEN
                ALTER TABLE fits_asset DROP CONSTRAINT fits_asset_asset_name_fkey;
            END IF;
        END $$;
    """)

    # Update any existing data if needed
    # (Add any data migration logic here if required)
