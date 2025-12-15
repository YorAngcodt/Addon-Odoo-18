# FITS Overtime 2 - Analisis Detail Modul

## 📋 Overview
Modul **FITS Overtime 2** adalah sistem manajemen lembur komprehensif untuk Odoo 18 yang menyediakan:
- Konfigurasi aturan lembur fleksibel dengan 3 tingkat (OT1, OT2, OT3)
- Perhitungan otomatis jam lembur berdasarkan overlap waktu
- Workflow approval untuk permintaan lembur
- Validasi dan debugging tools yang lengkap

## 🏗️ Arsitektur Sistem

### Model Structure
```
overtime.configuration (Parent)
├── overtime.configuration.line (Child) - Detail OT1/OT2/OT3
├── overtime.request - Permintaan lembur
└── hr.employee (Inherit) - Assignment konfigurasi
```

### Dependencies
- **Base Modules**: `base`, `hr`, `mail`
- **External**: Tidak ada dependency eksternal

## 🔄 Alur Kerja Detail

### Phase 1: Setup & Konfigurasi (Biru)
1. **Admin Login** → Akses menu Overtime Management
2. **Create Configuration** → Buat aturan lembur baru
3. **Define Details**:
   - Nama konfigurasi
   - Periode berlaku (date_start - date_end)
   - Status (draft/active/expired)
4. **Create OT Lines**:
   - OT1: Biasanya 17:00-19:00 (jam lembur pertama)
   - OT2: Biasanya 19:00-22:00 (jam lembur kedua)  
   - OT3: Biasanya 22:00-24:00 (jam lembur ketiga)
5. **Validation Check**:
   - Urutan waktu: OT1 → OT2 → OT3
   - Tidak ada overlap antar jenis OT
   - Rentang waktu valid (0-24 jam)
6. **Activate Configuration** → Status menjadi 'active'
7. **Assign to Employee** → Set di hr.employee.overtime_configuration_id

### Phase 2: Request Creation (Ungu)
1. **Employee Creates Request** → Buat permintaan lembur
2. **Fill Details**:
   - Pilih employee
   - Set start datetime
   - Set end datetime
   - Tambah deskripsi/alasan
3. **Auto Validation**:
   - End datetime > start datetime
   - Employee memiliki konfigurasi
   - Konfigurasi dalam status active
4. **Status: Draft** → Request siap untuk perhitungan

### Phase 3: Calculation Engine (Hijau)
1. **Trigger**: `_compute_overtime_hours` (computed field)
2. **Get Configuration** → Ambil dari employee.overtime_configuration_id
3. **Configuration Check**:
   - Ada konfigurasi? → Jika tidak: ot_hours = 0
   - Status active? → Jika tidak: debug_info = 'Config not active'
   - Dalam periode? → Jika tidak: debug_info = 'Config expired'
4. **Core Calculation** (`calculate_overtime_for_request`):
   
   **a. Timezone Conversion**:
   ```python
   # Convert UTC to WIB (UTC+7)
   local_offset = timedelta(hours=7)
   start_local = start_datetime + local_offset
   end_local = end_datetime + local_offset
   ```
   
   **b. Time Float Extraction**:
   ```python
   # Convert to decimal hours (17:30 = 17.5)
   start_float = hour + (minute/60) + (second/3600)
   end_float = hour + (minute/60) + (second/3600)
   ```
   
   **c. Cross-day Handling**:
   ```python
   # Jika lintas hari, tambah 24 jam per hari
   if end_date > start_date:
       end_float += 24 * days_difference
   ```
   
   **d. Overlap Calculation** (untuk setiap OT line):
   ```python
   overlap_start = max(request_start, line_start)
   overlap_end = min(request_end, line_end)
   
   if overlap_start < overlap_end:
       duration = overlap_end - overlap_start
       # Assign ke ot1_hours/ot2_hours/ot3_hours
   ```

5. **Result Processing**:
   - Round ke 2 desimal
   - Hitung total
   - Generate debug message
   - Update fields: ot1_hours, ot2_hours, ot3_hours, overtime_breakdown_total

### Phase 4: Workflow Management (Orange)
1. **Employee Review** → Lihat hasil perhitungan
2. **Submit Request** → Status: 'submitted'
3. **Manager Review** → Evaluasi permintaan
4. **Manager Decision**:
   - **Approve** → Status: 'approved'
   - **Reject** → Status: 'rejected'
   - **Need Changes** → Status: 'draft' (kembali ke employee)

### Phase 5: Configuration Management
1. **Auto-expire Check** → Dijalankan harian/saat akses
2. **Date Check** → Jika date_end < today
3. **Auto-expire** → Status menjadi 'expired'

## 🧮 Contoh Perhitungan

### Konfigurasi:
- OT1: 17:00 - 19:00 (2 jam)
- OT2: 19:00 - 22:00 (3 jam)
- OT3: 22:00 - 24:00 (2 jam)

### Request: 18:00 - 21:00 (3 jam)

### Perhitungan:
1. **OT1 Overlap**: max(18.0, 17.0) to min(21.0, 19.0) = 18.0 to 19.0 = **1 jam**
2. **OT2 Overlap**: max(18.0, 19.0) to min(21.0, 22.0) = 19.0 to 21.0 = **2 jam**
3. **OT3 Overlap**: max(18.0, 22.0) to min(21.0, 24.0) = 22.0 to 21.0 = **0 jam** (no overlap)

### Hasil:
- OT1: 1.0 jam
- OT2: 2.0 jam  
- OT3: 0.0 jam
- **Total: 3.0 jam**

## 🔧 Fitur Khusus

### 1. Validasi Komprehensif
- **Sequence Validation**: OT1 start < OT2 start < OT3 start
- **Overlap Detection**: Tidak ada tumpang tindih antar jenis OT
- **Time Range Validation**: 0 ≤ time < 24
- **Configuration Status**: Hanya 'active' yang bisa digunakan

### 2. Cross-day Support
```python
# Contoh: Lembur dari 23:00 hari ini sampai 02:00 besok
start_time = 23.0  # 23:00
end_time = 26.0    # 02:00 + 24 (next day)
```

### 3. Timezone Handling
- Input datetime dalam UTC (standar Odoo)
- Konversi ke WIB (UTC+7) untuk perhitungan
- Akurat untuk zona waktu Indonesia

### 4. Debugging Tools
- Field `calculation_debug_info` untuk troubleshooting
- Method `debug_breakdown_calculation()` untuk analisis detail
- Validation messages yang informatif

### 5. Auto-expire Management
- Konfigurasi otomatis expired setelah date_end
- Cron job atau manual trigger
- Notifikasi untuk admin

## 🎯 Interface & User Experience

### Menu Structure:
```
Overtime Management
├── Requests (List & Form views)
└── Configuration (List & Form views)
```

### List Views:
- **Requests**: Employee, DateTime, Hours breakdown, Status badges
- **Configuration**: Name, Period, Lines count, Status

### Form Views:
- **Request Form**: Employee info, DateTime, Calculation results, Workflow buttons
- **Configuration Form**: Period setup, OT lines editor, Status management

### Status Badges:
- **Draft**: Info (biru)
- **Submitted**: Warning (kuning)
- **Approved**: Success (hijau)
- **Rejected**: Danger (merah)

## 🔐 Security & Access

### Access Rights:
- **Model**: `base.group_user` (semua user internal)
- **CRUD**: Read, Write, Create, Delete untuk semua model
- **Workflow**: Button actions berdasarkan status

### Data Security:
- Employee hanya bisa lihat request sendiri (bisa ditambah rule)
- Manager bisa approve/reject
- Admin mengelola konfigurasi

## 🚀 Keunggulan Sistem

1. **Akurasi Tinggi**: Perhitungan hingga detik dengan algoritma overlap
2. **Fleksibilitas**: Konfigurasi dapat disesuaikan per periode/departemen
3. **User Friendly**: Interface intuitif dengan status badges
4. **Debugging**: Tools lengkap untuk troubleshooting
5. **Scalability**: Mendukung multiple konfigurasi dan cross-day scenarios
6. **Automation**: Auto-calculation dan auto-expire
7. **Compliance**: Audit trail dengan mail tracking

## 📈 Potential Enhancements

1. **Multi-timezone Support**: Untuk perusahaan multinasional
2. **Rate Calculation**: Integrasi dengan payroll untuk hitung tarif
3. **Reporting**: Dashboard dan laporan lembur
4. **Mobile App**: Interface mobile untuk request
5. **Integration**: Dengan attendance/timesheet modules
6. **Notification**: Email/SMS untuk approval workflow
