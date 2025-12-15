# FITS Assets Maintenance - Version 1.1

## What's New in Version 1.1

This version introduces **Kanban Stages** for Maintenance Requests, providing better visual organization and workflow management.

### New Features:
- **Colored Kanban Stages**: Visual stages that match the status bar colors
- **Automatic Stage Assignment**: Stages are automatically updated when maintenance request status changes
- **Enhanced Kanban View**: Group maintenance requests by stages instead of plain states
- **Stage-based Filtering**: Filter and search maintenance requests by stages
- **Maintenance Calendar Integration**: In-progress requests automatically appear in maintenance calendar
- **Smart Button Logic**: Context-aware buttons based on current status

### Maintenance Request Status Logic
The module now includes proper status transition logic:

**Status Flow:**
1. **Draft** → **In Progress** (via "In Progress" button)
2. **In Progress** → **Repaired** (via "Repaired" button) or **Done** (via "Done" button) or **Cancel** (via "Cancel" button)
3. **Repaired** → **Done** (via "Done" button) or **Cancel** (via "Cancel" button)
4. **Cancelled** → **Draft** (via "Set to Draft" button)
5. **Done** → **No further actions** (maintenance completed) ✅

**Button Visibility:**
- **"In Progress"** button: Visible when status is **"Draft"** only
- **"Repaired"** button: Visible when status is **"In Progress"** only
- **"Done"** button: Visible when status is **"In Progress"** or **"Repaired"**
- **"Cancel"** button: Visible when status is **"In Progress"** or **"Repaired"**
- **"Set to Draft"** button: Visible when status is **"Cancelled"** only
- **When status = "Done"**: **NO buttons visible** (maintenance completed) ✅

### Asset Status Automation
**Automatic Asset Status Updates:**
- **Draft** → Asset status remains **Active** (default)
- **In Progress** → Asset status automatically becomes **"In Maintenance"** ✅
- **Repaired** → Asset status becomes **"In Maintenance"**
- **Done** → Asset status returns to **"Active"** (unless recurring maintenance)
- **Cancelled** → Asset status returns to **"Active"**

### Maintenance Calendar Views
**Two Main View Types:**
- **Calendar View**: Visual timeline with color-coded status indicators ✅
- **List View**: Tabular format showing all maintenance events with details ✅

**Calendar View Features:**
- **Visual Timeline**: See maintenance events on a calendar layout
- **Color-Coded Status**: Different colors for each maintenance status
- **Easy Navigation**: Click events to see details
- **Date-Based Planning**: Visual scheduling of maintenance activities

**List View Features:**
- **Complete Data Overview**: See all maintenance events in a structured table
- **Essential Columns**: Asset, Date, Status, Responsible Person, Team, Recurrence Dates
- **Quick Status Overview**: Visual status indicators in list format
- **Easy Sorting & Filtering**: Sort by any column, filter by status or dates
- **Export Capabilities**: Export maintenance data to Excel/PDF

### Stage Colors:
- **Draft**: Blue
- **In Progress**: Orange
- **Repaired**: Green
- **Cancelled**: Red (folded)
- **Done**: Dark Green (folded)

## Installation & Upgrade

### Current Approach: XML Data + Migration
The module uses **XML data file + migration script** for complete stage management:
- **XML data file** creates stages with proper colors and sequences automatically
- **Migration script** assigns stages to existing maintenance requests
- **Kanban groups by stage_id** with beautiful colored columns that appear automatically
- **No manual setup** required - stages appear immediately

### If you encounter errors:

#### 1. Duplicate Key Error (UniqueViolation)
The error `duplicate key value violates unique constraint "fits_maintenance_stage_name_unique"` occurs when stages already exist in the database.

**Solutions:**

**Option 1: Automatic Migration (Recommended)**
1. The migration script handles this automatically
2. It will update existing stages and assign them to maintenance requests
3. Simply try installing/upgrading the module again

**Option 2: Manual Database Cleanup**
If the automatic migration doesn't work, run this SQL command in your database:
```sql
DELETE FROM fits_maintenance_stage WHERE name IN ('Draft', 'In Progress', 'Repaired', 'Cancelled', 'Done');
```
Then restart the module installation.

**Option 3: Use the Fix Script**
Access Odoo shell and run:
```python
from fits_assets_maintenance.scripts.fix_stages import fix_maintenance_stages
fix_maintenance_stages(env)
```

## Usage

After successful installation:
1. Go to **Maintenance > Maintenance Requests**
2. The kanban view will show **5 colored columns** automatically (Draft, In Progress, Repaired, Cancelled, Done)
3. Each column has **distinct colors** matching the status bar
4. Use the **stage filters** in the search view to filter by specific stages
5. Stages automatically update when you change the status of maintenance requests
6. **In Progress** requests automatically appear in **Maintenance > Maintenance Calendar**

## Migration from Previous Versions

- Existing maintenance requests will automatically be assigned to appropriate stages
- The migration script creates the colored stages with proper sequences
- No manual intervention required for existing data

## Technical Details

### Current Implementation
- **XML Data File**: `data/maintenance_stage_data.xml` creates stages with colors and sequences
- **Kanban View**: Groups by `stage_id` with automatic colored columns
- **Migration Script**: Assigns stages to existing maintenance requests
- **Group Expand**: `_read_group_stage_ids` method makes columns appear automatically

### Asset Status Automation Implementation
**Automatic Asset Status Updates:**
- **`action_start_progress()`**: Sets asset status to **"In Maintenance"** when maintenance starts ✅
- **`action_mark_repaired()`**: Sets asset status to **"In Maintenance"** when maintenance is completed
- **`action_mark_done()`**: Returns asset to **"Active"** status (smart handling for recurring maintenance)
- **`action_set_to_draft()`**: Returns asset to **"Active"** status when maintenance is cancelled
- **`action_cancel()`**: Returns asset to **"Active"** status when maintenance is cancelled

### View Configuration
**Two View Support:**
```xml
<!-- List View -->
<record id="view_maintenance_calendar_list" model="ir.ui.view">
    <field name="name">fits.maintenance.calendar.list</field>
    <field name="model">fits.maintenance.calendar</field>
    <field name="arch" type="xml">
        <list string="Maintenance Calendar">
            <field name="asset_id"/>
            <field name="maintenance_date"/>
            <field name="hasil_status"/>
            <field name="maintenance_responsible_id"/>
            <field name="team_id"/>
            <field name="recurrence_start_date"/>
            <field name="recurrence_end_date"/>
            <field name="responsible_person_id"/>
        </list>
    </field>
</record>

<!-- Action with Two Views -->
<field name="view_mode">calendar,list</field>
<field name="view_id" ref="view_maintenance_calendar_list"/>
```

**View Order:**
1. **Calendar View** (default) - Visual timeline with color-coded events
2. **List View** - Tabular overview of all maintenance events

### How Asset Status Automation Works
1. **Create Maintenance Request** → `maintenance_required = True` (in create method)
2. **Click "In Progress"** → Asset status = **"In Maintenance"** 
3. **Maintenance Calendar** → Shows event with status = **"In Progress"** 
4. **Click "Done"** → Asset status = **"Active"** (unless recurring maintenance)
5. **Calendar Updates** → Event status changes to **"Done"**

### Workflow Button Logic
**Draft State:**
-  Only **"In Progress"** button visible
-  No other action buttons

**In Progress State:**
-  **"Repaired"** button visible
-  **"Done"** button visible
-  **"Cancel"** button visible
-  **"In Progress"** button hidden
-  **"Set to Draft"** button hidden

**Repaired State:**
-  **"Done"** button visible
-  **"Cancel"** button visible
-  **"Repaired"** button hidden
-  **"Set to Draft"** button hidden

**Done State:**
-  **NO buttons visible** (maintenance completed) 
-  **"Set to Draft"** button hidden

**Cancelled State:**
-  Only **"Set to Draft"** button visible
-  All other action buttons hidden
