# Analysis Service Migration Plan Index

Mục tiêu: đưa core và yêu cầu nghiệp vụ từ smap-analyse vào analysis-srv theo clean architecture Python.

## Danh sách tài liệu

1. `01_migration_scope_from_smap_analyse.md`
   - Phạm vi migrate, boundary, in/out scope.
2. `02_target_clean_architecture_python.md`
   - Target architecture, layer boundaries, dependency rule.
3. `03_business_requirements_inventory.md`
   - Danh mục yêu cầu nghiệp vụ cần giữ khi migrate.
4. `04_core_porting_backlog.md`
   - Backlog chi tiết theo module để port core.
5. `05_delivery_milestones.md`
   - Lộ trình triển khai theo mốc và tiêu chí nghiệm thu.
6. `06_risks_testing_cutover.md`
   - Rủi ro, test strategy, cutover plan.

## Cách dùng

- Bước 1: Chốt phạm vi tại file 01.
- Bước 2: Chốt cấu trúc code tại file 02.
- Bước 3: Mapping nghiệp vụ tại file 03.
- Bước 4: Triển khai backlog file 04 theo mốc file 05.
- Bước 5: Chạy test + cutover theo file 06.
