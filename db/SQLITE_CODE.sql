-- 1. Bảng Khách Hàng
CREATE TABLE KHACHHANG (
    MaKH INTEGER PRIMARY KEY AUTOINCREMENT,
    Email TEXT NOT NULL UNIQUE,
    MatKhau TEXT NOT NULL,
    HoTen TEXT NOT NULL,
    SDT TEXT NOT NULL UNIQUE
);

-- 2. Bảng Loại Phòng
CREATE TABLE LOAIPHONG (
    MaLoai INTEGER PRIMARY KEY AUTOINCREMENT,
    TenLoai TEXT NOT NULL,
    GiaTien INTEGER NOT NULL, -- Dùng INTEGER vì tiền VNĐ không có số thập phân
    SoNguoiToiDa INTEGER NOT NULL
);

-- 3. Bảng Dịch Vụ
CREATE TABLE DICHVU (
    MaDV INTEGER PRIMARY KEY AUTOINCREMENT,
    TenDV TEXT NOT NULL,
    MoTa TEXT,
    GiaTien INTEGER NOT NULL,
    ThayDoiSL INTEGER NOT NULL DEFAULT 0, -- 0: false, 1: true (SQLite không có kiểu BOOLEAN)
    TrangThai TEXT NOT NULL DEFAULT 'Đang có', -- 'Đang có', 'Đang khóa'
    HinhAnh TEXT -- Lưu đường dẫn ảnh URL
);

-- 4. Bảng Nhân Viên
CREATE TABLE NHANVIEN (
    MaNV INTEGER PRIMARY KEY AUTOINCREMENT,
    MatKhau TEXT NOT NULL,
    HoTen TEXT NOT NULL,
    SDT TEXT NOT NULL UNIQUE,
    LaAdmin INTEGER NOT NULL DEFAULT 0 -- 0: Nhân viên, 1: Admin
);

-- 5. Bảng Hình Ảnh Loại Phòng (Phụ thuộc LOAIPHONG)
CREATE TABLE HINHANH_LOAIPHONG (
    MaAnh INTEGER PRIMARY KEY AUTOINCREMENT,
    MaLoai INTEGER NOT NULL,
    HinhAnh TEXT NOT NULL,
    FOREIGN KEY (MaLoai) REFERENCES LOAIPHONG(MaLoai) ON DELETE CASCADE
);

-- 6. Bảng Phòng (Phụ thuộc LOAIPHONG)
CREATE TABLE PHONG (
    MaPhong INTEGER PRIMARY KEY AUTOINCREMENT,
    SoPhong TEXT NOT NULL UNIQUE,
    Tang INTEGER NOT NULL,
    MaLoai INTEGER NOT NULL,
    MoTa TEXT,
    TrangThai TEXT NOT NULL DEFAULT 'Sẵn sàng', -- 'Sẵn sàng', 'Bảo trì'
    FOREIGN KEY (MaLoai) REFERENCES LOAIPHONG(MaLoai) ON DELETE RESTRICT
);

-- 7. Bảng Đặt Phòng (Phụ thuộc KHACHHANG, NHANVIEN)
CREATE TABLE DATPHONG (
    MaDP INTEGER PRIMARY KEY AUTOINCREMENT,
    MaKH INTEGER NOT NULL,
    TongTien INTEGER NOT NULL DEFAULT 0,
    NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP, -- Tự động lấy ngày giờ hiện tại
    ThanhToan TEXT, -- Vd: 'Tiền mặt', 'Chuyển khoản'
    TrangThai TEXT NOT NULL DEFAULT 'Chờ xác nhận', -- 'Chờ xác nhận', 'Đã xác nhận', 'Đang lưu trú', 'Hoàn tất', 'Đã hủy'
    MaNV INTEGER, -- Cho phép NULL (Khách tự đặt)
    GhiChu TEXT,  -- Cho phép NULL
    FOREIGN KEY (MaKH) REFERENCES KHACHHANG(MaKH) ON DELETE RESTRICT,
    FOREIGN KEY (MaNV) REFERENCES NHANVIEN(MaNV) ON DELETE SET NULL
);

-- 8. Bảng Chi Tiết Đặt Phòng (Phụ thuộc DATPHONG, PHONG, LOAIPHONG)
CREATE TABLE CHITIET_DATPHONG (
    MaCTDP INTEGER PRIMARY KEY AUTOINCREMENT,
    MaDP INTEGER NOT NULL,
    MaPhong INTEGER, -- Cho phép NULL (Lễ tân gán sau)
    MaLoai INTEGER NOT NULL,
    GiaPhong INTEGER NOT NULL,
    SoNguoi INTEGER NOT NULL,
    NgayNhan DATE NOT NULL,
    NgayTra DATE NOT NULL,
    TrangThai TEXT NOT NULL DEFAULT 'Chờ nhận', -- 'Chờ nhận', 'Đã nhận', 'Đã trả', 'Đã hủy'
    FOREIGN KEY (MaDP) REFERENCES DATPHONG(MaDP) ON DELETE CASCADE,
    FOREIGN KEY (MaPhong) REFERENCES PHONG(MaPhong) ON DELETE SET NULL,
    FOREIGN KEY (MaLoai) REFERENCES LOAIPHONG(MaLoai) ON DELETE RESTRICT
);

-- 9. Bảng Đặt Phòng - Dịch Vụ (Phụ thuộc CHITIET_DATPHONG, DICHVU)
CREATE TABLE DATPHONG_DICHVU (
    MaPDV INTEGER PRIMARY KEY AUTOINCREMENT,
    MaCTDP INTEGER NOT NULL,
    MaDV INTEGER NOT NULL,
    DonGia INTEGER NOT NULL,
    SoLuong INTEGER NOT NULL DEFAULT 1,
    Ngay DATE, -- Cho phép NULL
    Gio TIME,  -- Cho phép NULL
    TrangThai TEXT NOT NULL DEFAULT 'Chờ xử lý', -- 'Chờ xử lý', 'Đã phục vụ', 'Đã hủy'
    FOREIGN KEY (MaCTDP) REFERENCES CHITIET_DATPHONG(MaCTDP) ON DELETE CASCADE,
    FOREIGN KEY (MaDV) REFERENCES DICHVU(MaDV) ON DELETE RESTRICT
);

-- ==========================================
-- 1. INSERT KHÁCH HÀNG
-- ==========================================
INSERT INTO KHACHHANG (Email, MatKhau, HoTen, SDT) VALUES
('nguyenvana@gmail.com', '123456', 'Nguyễn Văn A', '0901234567'),
('tranbathib@gmail.com', '123456', 'Trần Thị B', '0987654321'),
('leduc@gmail.com', '123456', 'Lê Đức C', '0912345678');

-- ==========================================
-- 2. INSERT LOẠI PHÒNG
-- ==========================================
INSERT INTO LOAIPHONG (TenLoai, GiaTien, SoNguoiToiDa) VALUES
('Standard Giường Đôi', 500000, 2),
('Deluxe Hướng Biển', 850000, 3),
('Suite Gia Đình VIP', 1500000, 4);

-- ==========================================
-- 3. INSERT DỊCH VỤ (Đã sửa lại link ảnh lưu trong static/images/services/...)
-- ==========================================
INSERT INTO DICHVU (TenDV, MoTa, GiaTien, ThayDoiSL, TrangThai, HinhAnh) VALUES
('Buffet Sáng', 'Buffet sáng tiêu chuẩn 4 sao tại nhà hàng', 150000, 1, 'Đang có', 'images/services/buffet.jpg'),
('Xe đưa đón Sân Bay', 'Xe 4-7 chỗ đưa đón tận nơi', 300000, 1, 'Đang có', 'images/services/airport-transfer.jpg'),
('Gói Honeymoon', 'Trang trí hoa hồng, rượu vang đỏ', 500000, 0, 'Đang có', 'images/services/honeymoon.jpg'),
('Giường Phụ (Extra Bed)', 'Thêm 1 giường đơn cho người thứ 3', 250000, 1, 'Đang có', 'images/services/extra-bed.jpg');

-- ==========================================
-- 4. INSERT NHÂN VIÊN
-- ==========================================
INSERT INTO NHANVIEN (MatKhau, HoTen, SDT, LaAdmin) VALUES
('admin123', 'Quản Trị Viên', '0999999999', 1),
('letan123', 'Lễ Tân 1', '0888888888', 0);

-- ==========================================
-- 5. INSERT HÌNH ẢNH LOẠI PHÒNG (Đã sửa link lưu trong static/images/rooms/...)
-- ==========================================
INSERT INTO HINHANH_LOAIPHONG (MaLoai, HinhAnh) VALUES
(1, 'images/rooms/standard_1.jpg'),
(1, 'images/rooms/standard_2.jpg'),
(2, 'images/rooms/deluxe_1.jpg'),
(2, 'images/rooms/deluxe_2.jpg'),
(3, 'images/rooms/suite_1.jpg'),
(3, 'images/rooms/suite_2.jpg');

-- ==========================================
-- 6. INSERT PHÒNG VẬT LÝ
-- ==========================================
INSERT INTO PHONG (SoPhong, Tang, MaLoai, MoTa, TrangThai) VALUES
('101', 1, 1, 'Phòng gần sảnh chính', 'Sẵn sàng'),
('102', 1, 1, 'Phòng góc, yên tĩnh', 'Sẵn sàng'),
('201', 2, 2, 'View biển trực diện', 'Sẵn sàng'),
('202', 2, 2, 'View biển bị che một phần', 'Bảo trì'), 
('203', 2, 2, 'View biển trực diện', 'Sẵn sàng'),
('301', 3, 3, 'Suite nguyên tầng 3', 'Sẵn sàng');

-- ==========================================
-- 7. INSERT ĐẶT PHÒNG
-- ==========================================
INSERT INTO DATPHONG (MaKH, TongTien, NgayTao, ThanhToan, TrangThai, MaNV, GhiChu) VALUES
(1, 800000, '2026-03-25 08:30:00', 'Chuyển khoản VNPay', 'Chờ xác nhận', NULL, 'Đến check-in muộn lúc 16h'),
(2, 2000000, '2026-03-24 14:15:00', 'Tiền mặt', 'Đang lưu trú', 2, 'Gần thang máy'),
(3, 2000000, '2026-03-20 10:00:00', 'Thẻ tín dụng', 'Hoàn tất', NULL, 'Kỷ niệm ngày cưới');

-- ==========================================
-- 8. INSERT CHI TIẾT ĐẶT PHÒNG
-- ==========================================
INSERT INTO CHITIET_DATPHONG (MaDP, MaPhong, MaLoai, GiaPhong, SoNguoi, NgayNhan, NgayTra, TrangThai) VALUES
(1, NULL, 1, 500000, 2, '2026-03-28', '2026-03-29', 'Chờ nhận'),
(2, 3, 2, 850000, 2, '2026-03-24', '2026-03-26', 'Đã nhận'),
(3, 6, 3, 1500000, 2, '2026-03-21', '2026-03-22', 'Đã trả');

-- ==========================================
-- 9. INSERT ĐẶT PHÒNG KÈM DỊCH VỤ
-- ==========================================
INSERT INTO DATPHONG_DICHVU (MaCTDP, MaDV, DonGia, SoLuong, Ngay, Gio, TrangThai) VALUES
(1, 1, 150000, 2, NULL, NULL, 'Chờ xử lý'),
(2, 2, 300000, 1, '2026-03-24', '14:00:00', 'Đã phục vụ'),
(3, 3, 500000, 1, '2026-03-21', '15:30:00', 'Đã phục vụ');
