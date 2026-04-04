from flask import jsonify, request
from webapi import app, get_db
from datetime import datetime, timedelta


# --- HÀM HỖ TRỢ: Tự động thêm /static/ vào đường dẫn images/ từ DB ---
def format_image_path(path):
    if not path:
        return "/static/images/default_room.jpg"

    clean_path = path.lstrip('/')
    # Nếu DB chỉ lưu 'images/...' thì ta tiêm thêm 'static/' vào đầu
    if not clean_path.startswith('static/'):
        return f"/static/{clean_path}"
    return f"/{clean_path}"


# --- X. API: LẤY DANH SÁCH TẤT CẢ LOẠI PHÒNG (Cho Dropdown Filter) ---
@app.route('/api/all_room_types', methods=['GET'])
def get_all_room_types():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT MaLoai, TenLoai FROM LOAIPHONG ORDER BY MaLoai ASC")
        types = [dict(row) for row in cursor.fetchall()]
        return jsonify({"status": "success", "data": types})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- 1. API: LẤY 6 PHÒNG ĐỘNG (Trang chủ & Gợi ý) ---
@app.route('/api/top_rooms', methods=['GET'])
def get_top_rooms():
    conn = get_db()
    try:
        # Lấy 6 phòng (trước đó bạn set LIMIT 3 nhưng lại comment là lấy 6 phòng)
        cursor = conn.execute("SELECT * FROM LOAIPHONG LIMIT 6")
        base_rooms = [dict(row) for row in cursor.fetchall()]

        final_rooms = []
        for room in base_rooms:
            img_cursor = conn.execute("SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = ? ORDER BY LaAnhDaiDien DESC, MaAnh ASC LIMIT 1", (room['MaLoai'],))
            img_row = img_cursor.fetchone()

            new_room = room.copy()
            if img_row:
                new_room['HinhAnhDaiDien'] = format_image_path(img_row['HinhAnh'])
            else:
                new_room['HinhAnhDaiDien'] = "/static/images/default_room.jpg"
                
            final_rooms.append(new_room)

        return jsonify({"status": "success", "data": final_rooms[:6]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 2. API: TÌM KIẾM PHÒNG ---
@app.route('/api/search_rooms', methods=['GET'])
def search_rooms_api():
    max_price = request.args.get('max_price', 10000000)
    room_type = request.args.get('room_type', '').strip()
    guests = request.args.get('guests', 1)
    checkin_str = request.args.get('checkin', '').strip()
    checkout_str = request.args.get('checkout', '').strip()
    
    try:
        guests = int(guests)
    except:
        guests = 1

    checkin_date = None
    checkout_date = None
    if checkin_str and checkout_str:
        try:
            checkin_date = datetime.strptime(checkin_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            checkout_date = datetime.strptime(checkout_str, '%d/%m/%Y').strftime('%Y-%m-%d')
        except:
            pass

    conn = get_db()
    
    query = """
        SELECT lp.*, 
        (SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = lp.MaLoai LIMIT 1) as HinhAnhPath
        FROM LOAIPHONG lp WHERE lp.GiaTien <= ? AND lp.SoNguoiToiDa >= ?
    """
    params = [max_price, guests]
    
    # Lọc theo MÃ loại phòng (ID) từ frontend thay vì tên chuỗi
    if room_type.isdigit():
        query += " AND lp.MaLoai = ?"
        params.append(int(room_type))

    # Lọc loại trừ những loại phòng đã HẾT THỰC TẾ TRONG KHOẢNG NGÀY NÀY
    if checkin_date and checkout_date:
        query += """
            AND (
                SELECT COUNT(*) FROM PHONG p WHERE p.MaLoai = lp.MaLoai AND p.TrangThai = 'Sẵn sàng'
            ) > (
                SELECT COUNT(*) FROM CHITIET_DATPHONG ctdp 
                WHERE ctdp.MaLoai = lp.MaLoai 
                  AND ctdp.TrangThai IN ('Chờ nhận', 'Đã nhận') 
                  AND (ctdp.NgayNhan < ? AND ctdp.NgayTra > ?)
            )
        """
        # Nếu (Ngày nhận của Booking cũ < Ngày trả của form TRONG KHI Ngày trả của Booking cũ > Ngày nhận của form)
        # Tức là có sự trồng lấn (Overlapping). Số phòng sẵn sàng TRỪ ĐI số booking trồng lấn PHẢI > 0 thì mới hiển thị.
        params.append(checkout_date)
        params.append(checkin_date)

    try:
        cursor = conn.execute(query, tuple(params))
        rooms = [dict(row) for row in cursor.fetchall()]
        for r in rooms:
            r['HinhAnhDaiDien'] = format_image_path(r['HinhAnhPath'])
        return jsonify({"status": "success", "data": rooms})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 3. API: CHI TIẾT PHÒNG ---
@app.route('/api/room/<int:ma_loai>', methods=['GET'])
def get_room_detail_api(ma_loai):
    conn = get_db()
    try:
        room = conn.execute("SELECT * FROM LOAIPHONG WHERE MaLoai = ?", (ma_loai,)).fetchone()
        if not room:
            return jsonify({"status": "error", "message": "Không thấy phòng"}), 404

        room_dict = dict(room)
        img_cursor = conn.execute("SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = ?", (ma_loai,))

        # Bốc toàn bộ danh sách ảnh để làm gallery
        images = []
        for row in img_cursor.fetchall():
            path = format_image_path(row['HinhAnh'])
            images.append({"HinhAnh": path})

        room_dict['HinhAnhDaiDien'] = images[0]['HinhAnh'] if images else "/static/images/default_room.jpg"
        room_dict['DanhSachAnh'] = images  # Phải có cái này thì trang Detail mới hiện ảnh nhỏ

        return jsonify({"status": "success", "data": room_dict})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 4. API: DANH SÁCH DỊCH VỤ ---
@app.route('/api/services', methods=['GET'])
def get_services_api():
    conn = get_db()
    try:
        # Lấy tất cả cột từ bảng DICHVU
        cursor = conn.execute("SELECT * FROM DICHVU WHERE TrangThai = 'Đang có'")
        services = [dict(row) for row in cursor.fetchall()]

        for s in services:
            # Kiểm tra nếu key HinhAnh tồn tại và không rỗng
            path = s.get('HinhAnh')
            if path:
                # Gọi hàm format_image_path để tự thêm /static/ nếu DB chỉ lưu images/...
                s['HinhAnh'] = format_image_path(path)
            else:
                # Trả về ảnh mặc định nếu DB trống
                s['HinhAnh'] = "/static/images/default_service.jpg"

        return jsonify({"status": "success", "data": services})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 5. API: LƯU ĐƠN ĐẶT PHÒNG (FIX LỖI KHÔNG LƯU LỊCH SỬ) ---
@app.route('/api/save_booking', methods=['POST'])
def save_booking_api():
    data = request.get_json()
    conn = get_db()
    try:
        # 1. Lấy giờ hệ thống chuẩn YYYY-MM-DD HH:MM:SS
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 2. Đảm bảo MaKH là số nguyên
        ma_kh = int(data['ma_kh'])

        cursor = conn.execute(
            "INSERT INTO DATPHONG (MaKH, TongTien, NgayTao, ThanhToan, TrangThai) VALUES (?, ?, ?, ?, 'Chờ xác nhận')",
            (ma_kh, data.get('total_price', 0), now_str, data['payment'])
        )
        ma_dp = cursor.lastrowid

        for item in data['cart']:
            # Chuyển đổi dd/mm/yyyy -> yyyy-mm-dd để khớp với các đơn có sẵn trong DB
            try:
                checkin_db = datetime.strptime(item['checkin'], "%d/%m/%Y").strftime("%Y-%m-%d")
                checkout_db = datetime.strptime(item['checkout'], "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                checkin_db = item['checkin']
                checkout_db = item['checkout']

            res_ctdp = conn.execute(
                "INSERT INTO CHITIET_DATPHONG (MaDP, MaLoai, GiaPhong, SoNguoi, NgayNhan, NgayTra) VALUES (?, ?, ?, ?, ?, ?)",
                (ma_dp, item['MaLoai'], item['GiaTien'], item.get('SoNguoiToiDa', 2), checkin_db, checkout_db)
            )
            ma_ctdp = res_ctdp.lastrowid

            # 3. Dịch vụ (Vẫn giữ logic băm ngày của mày)
            for sv in item.get('services', []):
                # Sử dụng checkin_db và checkout_db ("Y-m-d") đã parse ở trên để tránh lỗi crash lúc lập lịch 
                start_dt = datetime.strptime(checkin_db, "%Y-%m-%d")
                end_dt = datetime.strptime(checkout_db, "%Y-%m-%d")
                gio_sd = sv.get('gio_dat', '08:00:00')

                if sv.get('TinhTheoNgay') == 1:
                    curr = start_dt
                    while curr < end_dt:
                        conn.execute(
                            "INSERT INTO DATPHONG_DICHVU (MaCTDP, MaDV, DonGia, SoLuong, Ngay, Gio, TrangThai) VALUES (?, ?, ?, ?, ?, ?, 'Chờ xử lý')",
                            (ma_ctdp, sv['MaDV'], sv['GiaTien'], sv['SoLuong'], curr.strftime("%Y-%m-%d"), gio_sd)
                        )
                        curr += timedelta(days=1)
                else:
                    conn.execute(
                        "INSERT INTO DATPHONG_DICHVU (MaCTDP, MaDV, DonGia, SoLuong, Ngay, Gio, TrangThai) VALUES (?, ?, ?, ?, ?, ?, 'Chờ xử lý')",
                        (ma_ctdp, sv['MaDV'], sv['GiaTien'], sv['SoLuong'], start_dt.strftime("%Y-%m-%d"), gio_sd)
                    )

        conn.commit()  # CHỐT HẠ PHẢI CÓ DÒNG NÀY
        return jsonify({"status": "success", "ma_dp": ma_dp})
    except Exception as e:
        conn.rollback()
        print(f"CRITICAL ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- 6. API: LỊCH SỬ ĐẶT PHÒNG (FIX LỖI KHÔNG HIỆN ẢNH PHÒNG) ---
@app.route('/api/history/<int:ma_kh>', methods=['GET'])
def get_history_api(ma_kh):
    conn = get_db()
    try:
        # 1. Lấy danh sách đơn hàng của khách
        cursor = conn.execute("SELECT * FROM DATPHONG WHERE MaKH = ? ORDER BY MaDP DESC", (ma_kh,))
        list_dp = [dict(row) for row in cursor.fetchall()]

        for dp in list_dp:
            # 2. Lấy chi tiết từng phòng trong đơn hàng
            ct_cursor = conn.execute("""
                SELECT ct.*, lp.TenLoai, p.SoPhong,
                (SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = lp.MaLoai LIMIT 1) as HinhAnhPath
                FROM CHITIET_DATPHONG ct 
                JOIN LOAIPHONG lp ON ct.MaLoai = lp.MaLoai 
                LEFT JOIN PHONG p ON ct.MaPhong = p.MaPhong
                WHERE ct.MaDP = ?
            """, (dp['MaDP'],))

            details = []
            for r in ct_cursor.fetchall():
                row_dict = dict(r)
                row_dict['HinhAnhHienThi'] = format_image_path(row_dict['HinhAnhPath'])

                # 3. ĐÂY LÀ CHỖ MÀY THIẾU: Lấy danh sách dịch vụ của TỪNG PHÒNG
                dv_cursor = conn.execute("""
                    SELECT dv.TenDV, dpdv.SoLuong, dpdv.DonGia
                    FROM DATPHONG_DICHVU dpdv
                    JOIN DICHVU dv ON dpdv.MaDV = dv.MaDV
                    WHERE dpdv.MaCTDP = ?
                """, (row_dict['MaCTDP'],))

                # Phải đặt tên là 'DanhSachDichVu' cho khớp với file history.html
                row_dict['DanhSachDichVu'] = [dict(dv) for dv in dv_cursor.fetchall()]
                details.append(row_dict)

            dp['DanhSachChiTiet'] = details

        return jsonify({"status": "success", "data": list_dp})
    except Exception as e:
        print(f"Loi API History: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()