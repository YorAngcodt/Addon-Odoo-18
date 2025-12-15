# FITS Overtime 2 - Contoh Penggunaan & Skenario

## 🎯 Skenario Penggunaan Umum

### Skenario 1: Setup Awal Perusahaan

**Konteks**: Perusahaan IT dengan jam kerja normal 09:00-17:00, ingin mengatur lembur dengan 3 tingkat tarif.

**Konfigurasi**:
```
Nama: "IT Company OT Rules 2024"
Periode: 2024-01-01 sampai 2024-12-31
Status: Active

OT Lines:
- OT1: 17:00 - 19:00 (2 jam, tarif 1.5x)
- OT2: 19:00 - 22:00 (3 jam, tarif 2.0x)  
- OT3: 22:00 - 24:00 (2 jam, tarif 3.0x)
```

**Langkah Setup**:
1. Admin masuk ke Overtime Management → Configuration
2. Create new configuration dengan detail di atas
3. Activate configuration
4. Assign ke semua employee IT

### Skenario 2: Request Lembur Normal

**Konteks**: Developer perlu lembur untuk menyelesaikan project urgent.

**Request Details**:
- Employee: John Doe (Developer)
- Start: 2024-03-15 18:00:00
- End: 2024-03-15 21:30:00
- Deskripsi: "Fixing critical bug for production release"

**Perhitungan Sistem**:
```
Request Time: 18:00 - 21:30 (3.5 jam)

OT1 (17:00-19:00): 
- Overlap: max(18:00, 17:00) to min(21:30, 19:00) = 18:00 to 19:00 = 1.0 jam

OT2 (19:00-22:00):
- Overlap: max(18:00, 19:00) to min(21:30, 22:00) = 19:00 to 21:30 = 2.5 jam

OT3 (22:00-24:00):
- Overlap: max(18:00, 22:00) to min(21:30, 24:00) = 22:00 to 21:30 = 0 jam (no overlap)

Hasil:
- OT1: 1.0 jam
- OT2: 2.5 jam
- OT3: 0.0 jam
- Total: 3.5 jam
```

**Workflow**:
1. John membuat request → Status: Draft
2. Sistem auto-calculate → Breakdown muncul
3. John submit → Status: Submitted
4. Manager review & approve → Status: Approved

### Skenario 3: Lembur Lintas Hari (Cross-day)

**Konteks**: Security guard shift malam yang lembur sampai pagi.

**Request Details**:
- Employee: Ahmad (Security)
- Start: 2024-03-15 23:00:00
- End: 2024-03-16 02:00:00
- Deskripsi: "Night shift overtime for special event"

**Perhitungan Sistem**:
```
Request Time: 23:00 - 02:00 (lintas hari)
Converted: 23:00 - 26:00 (26:00 = 02:00 next day)

Day 1 (23:00-24:00):
OT3 (22:00-24:00): 
- Overlap: max(23:00, 22:00) to min(24:00, 24:00) = 23:00 to 24:00 = 1.0 jam

Day 2 (00:00-02:00, atau 24:00-26:00):
OT1 (17:00-19:00): No overlap (17:00-19:00 vs 24:00-26:00)
OT2 (19:00-22:00): No overlap
OT3 (22:00-24:00): No overlap (22:00-24:00 vs 24:00-26:00)

Catatan: Untuk day 2, konfigurasi repeat dari 00:00
OT1 (00:00-02:00): 
- Overlap: max(24:00, 24:00) to min(26:00, 26:00) = 24:00 to 26:00 = 2.0 jam

Hasil:
- OT1: 2.0 jam (dari day 2)
- OT2: 0.0 jam
- OT3: 1.0 jam (dari day 1)
- Total: 3.0 jam
```

### Skenario 4: Error Handling

**Konteks**: Employee mencoba request tapi ada masalah konfigurasi.

**Case 4a - No Configuration**:
```
Employee: Jane (baru, belum di-assign konfigurasi)
Request: 18:00 - 21:00

Hasil:
- OT1: 0.0 jam
- OT2: 0.0 jam  
- OT3: 0.0 jam
- Debug Info: "No configuration assigned to employee"
```

**Case 4b - Expired Configuration**:
```
Employee: Bob (konfigurasi expired)
Configuration: Valid until 2023-12-31
Request Date: 2024-03-15

Hasil:
- OT1: 0.0 jam
- OT2: 0.0 jam
- OT3: 0.0 jam
- Debug Info: "Configuration not applicable: Request date 2024-03-15 is outside rule period"
```

**Case 4c - Invalid Time Range**:
```
Request: End time sebelum start time
Start: 2024-03-15 21:00:00
End: 2024-03-15 18:00:00

Error: "End datetime must be after start datetime"
Status: Tidak bisa save
```

## 🔧 Skenario Konfigurasi Khusus

### Konfigurasi 1: Shift Malam

**Konteks**: Perusahaan manufaktur dengan shift malam 22:00-06:00.

```
Nama: "Night Shift OT Rules"
Periode: 2024-01-01 sampai 2024-12-31

OT Lines:
- OT1: 22:00 - 24:00 (2 jam)
- OT2: 00:00 - 03:00 (3 jam, untuk hari berikutnya)
- OT3: 03:00 - 06:00 (3 jam)
```

### Konfigurasi 2: Weekend Premium

**Konteks**: Tarif weekend berbeda dari weekday.

```
Nama: "Weekend Premium OT"
Periode: Setiap weekend

OT Lines:
- OT1: 08:00 - 12:00 (4 jam, weekend morning)
- OT2: 12:00 - 18:00 (6 jam, weekend afternoon)
- OT3: 18:00 - 22:00 (4 jam, weekend evening)
```

### Konfigurasi 3: Department Specific

**Konteks**: Department berbeda punya aturan lembur berbeda.

```
IT Department:
- OT1: 17:00 - 20:00 (3 jam)
- OT2: 20:00 - 23:00 (3 jam)
- OT3: 23:00 - 02:00 (3 jam)

Production Department:
- OT1: 15:00 - 18:00 (3 jam, shift lebih awal)
- OT2: 18:00 - 21:00 (3 jam)
- OT3: 21:00 - 24:00 (3 jam)
```

## 🧮 Contoh Perhitungan Kompleks

### Case 1: Multiple OT Types dalam Satu Request

**Request**: 16:00 - 23:30 (7.5 jam)
**Konfigurasi Standard**:
- OT1: 17:00 - 19:00
- OT2: 19:00 - 22:00  
- OT3: 22:00 - 24:00

**Perhitungan**:
```
Total Request: 16:00 - 23:30

OT1 (17:00-19:00):
- Overlap: max(16:00, 17:00) to min(23:30, 19:00) = 17:00 to 19:00 = 2.0 jam

OT2 (19:00-22:00):
- Overlap: max(16:00, 19:00) to min(23:30, 22:00) = 19:00 to 22:00 = 3.0 jam

OT3 (22:00-24:00):
- Overlap: max(16:00, 22:00) to min(23:30, 24:00) = 22:00 to 23:30 = 1.5 jam

Hasil:
- OT1: 2.0 jam
- OT2: 3.0 jam
- OT3: 1.5 jam
- Total: 6.5 jam

Note: 1 jam (16:00-17:00) tidak masuk hitungan lembur karena di luar konfigurasi
```

### Case 2: Partial Overlap

**Request**: 18:30 - 20:45 (2.25 jam)

**Perhitungan**:
```
OT1 (17:00-19:00):
- Overlap: max(18:30, 17:00) to min(20:45, 19:00) = 18:30 to 19:00 = 0.5 jam

OT2 (19:00-22:00):
- Overlap: max(18:30, 19:00) to min(20:45, 22:00) = 19:00 to 20:45 = 1.75 jam

OT3 (22:00-24:00):
- Overlap: max(18:30, 22:00) to min(20:45, 24:00) = 22:00 to 20:45 = 0 jam

Hasil:
- OT1: 0.5 jam
- OT2: 1.75 jam
- OT3: 0.0 jam
- Total: 2.25 jam
```

## 🔍 Debugging & Troubleshooting

### Debug Info Examples

**Successful Calculation**:
```
Debug Info: "Rule: IT Company OT Rules 2024 | StartDT: 2024-03-15 18:00:00 | EndDT: 2024-03-15 21:30:00 | StartDT_Local: 2024-03-16 01:00:00 | EndDT_Local: 2024-03-16 04:30:00 | TimeFloat: 18.0-21.5 | Request: 18.0-21.5 | OT1(17.0-19.0): overlap(18.0-19.0) = 1.0h | OT2(19.0-22.0): overlap(19.0-21.5) = 2.5h | OT3(22.0-24.0): overlap(22.0-21.5) = 0h (no overlap) | Result: OT1:1.0h OT2:2.5h OT3:0.0h"
```

**Configuration Issues**:
```
Debug Info: "Configuration not applicable: Request date 2024-03-15 is outside rule period (2023-01-01 to 2023-12-31)"
```

**No Configuration**:
```
Debug Info: "No configuration assigned to employee"
```

### Common Issues & Solutions

1. **Zero Hours Result**:
   - Check: Employee punya konfigurasi?
   - Check: Konfigurasi status active?
   - Check: Request time overlap dengan OT lines?
   - Check: Periode konfigurasi masih valid?

2. **Wrong Calculation**:
   - Check: Timezone conversion (UTC vs local)
   - Check: Cross-day handling
   - Check: OT lines sequence dan overlap

3. **Validation Errors**:
   - Check: OT sequence (OT1 < OT2 < OT3)
   - Check: No overlap antar OT types
   - Check: Time range 0-24

## 📊 Performance Considerations

### Optimization Tips

1. **Index Fields**: employee_id, start_datetime, status
2. **Computed Fields**: Store=True untuk calculation results
3. **Batch Processing**: Group similar requests
4. **Caching**: Cache active configurations
5. **Archiving**: Archive old requests untuk performance

### Scalability Notes

- **Large Dataset**: Pagination di list views
- **Multiple Configurations**: Index by employee/department
- **Real-time Calculation**: Debounce untuk avoid excessive computation
- **Reporting**: Separate model untuk aggregated data
