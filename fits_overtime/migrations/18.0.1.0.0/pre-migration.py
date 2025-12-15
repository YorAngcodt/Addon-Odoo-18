def migrate(cr, version):
    # Menambahkan kolom show_status ke dalam tabel overtime_reporting_wizard
    cr.execute("""
        ALTER TABLE overtime_reporting_wizard 
        ADD COLUMN IF NOT EXISTS show_status VARCHAR
    """)
