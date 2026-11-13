# Việt Hóa Game

Launcher Windows tự tìm game đã cài (Steam / Epic / GOG / chọn tay) và cài / gỡ gói Việt hóa.

- Tải `VietHoaGame.exe` ở mục **Releases**.
- Danh mục gói: `danh_muc.json`. Gói tạo bằng `python cong_cu/tao_goi.py <thu_muc> <goi.zip>`.
- Dữ liệu trên máy: `%APPDATA%\VietHoaGame` (sao lưu file gốc, danh sách đã cài).
- Phát hành: tăng `APP_VERSION` trong `viet_hoa.py`, sửa `GHI_CHU_PHAT_HANH.md`, đẩy lên `main` → GitHub Actions tự đóng gói và đăng Release.
