from datetime import datetime, timedelta

from flask import request, jsonify
from webapi import app, get_db
import os
import uuid

# ─────────────────────────────────────────────
# 🔹 1. THỐNG KÊ DASHBOARD (STATISTICS)
# ─────────────────────────────────────────────
@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    conn = get_db()
    cursor = conn.cursor()

    # Lấy thời gian hiện tại
    today = datetime.now().strftime('%Y-%m-%d')
    first_day_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')

    # 1. Doanh thu tháng hiện tại (DATPHONG)
    cursor.execute("""
        SELECT SUM(TongTien) FROM DATPHONG 
        WHERE NgayTao >= ? AND TrangThai != 'Đã hủy'
    """, (first_day_month,))
    revenue_month = cursor.fetchone()[0] or 0

    # 2. Tổng đơn đặt trong tháng
    cursor.execute("SELECT COUNT(MaDP) FROM DATPHONG WHERE NgayTao >= ?", (first_day_month,))
    total_bookings = cursor.fetchone()[0] or 0

    # 3. Đơn chờ xác nhận
    cursor.execute("SELECT COUNT(MaDP) FROM DATPHONG WHERE TrangThai = 'Chờ xác nhận'")
    pending_confirm = cursor.fetchone()[0] or 0

    # 4. Khách đang lưu trú (Trạng thái đơn)
    cursor.execute("SELECT COUNT(MaDP) FROM DATPHONG WHERE TrangThai = 'Đang lưu trú'")
    staying_guests = cursor.fetchone()[0] or 0

    # 5. Phòng sẵn sàng (PHONG)
    cursor.execute("SELECT COUNT(MaPhong) FROM PHONG WHERE TrangThai = 'Sẵn sàng'")
    available_rooms = cursor.fetchone()[0] or 0

    # 6. Phòng đang bảo trì
    cursor.execute("SELECT COUNT(MaPhong) FROM PHONG WHERE TrangThai = 'Bảo trì'")
    maintenance_rooms = cursor.fetchone()[0] or 0

    # 7. Tổng số khách hàng (KHACHHANG)
    cursor.execute("SELECT COUNT(MaKH) FROM KHACHHANG")
    total_customers = cursor.fetchone()[0] or 0

    # 8. Yêu cầu dịch vụ chờ xử lý (DATPHONG_DICHVU)
    cursor.execute("SELECT COUNT(MaPDV) FROM DATPHONG_DICHVU WHERE TrangThai = 'Chờ xử lý'")
    pending_services = cursor.fetchone()[0] or 0

    # DỮ LIỆU BIỂU ĐỒ: Doanh thu 7 ngày gần nhất
    chart_data = []
    chart_labels = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT SUM(TongTien) FROM DATPHONG 
            WHERE date(NgayTao) = ? AND TrangThai != 'Đã hủy'
        """, (day,))
        row = cursor.fetchone()  # PHẢI CÓ ()
        val = row[0] if row and row[0] else 0
        chart_data.append(val)
        # Chuyển định dạng ngày để hiển thị (ví dụ 03/04)
        chart_labels.append((datetime.now() - timedelta(days=i)).strftime('%d/%m'))

    conn.close()

    return jsonify({
        "status": "success",
        "data": {
            "widget": {
                "revenue_month": revenue_month,
                "total_bookings": total_bookings,
                "pending_confirm": pending_confirm,
                "staying_guests": staying_guests,
                "available_rooms": available_rooms,
                "maintenance_rooms": maintenance_rooms,
                "total_customers": total_customers,
                "pending_services": pending_services
            },
            "chart": {
                "labels": chart_labels,
                "values": chart_data
            }
        }
    })

# ─────────────────────────────────────────────
# 🔹 2. QUẢN LÝ PHÒNG (ROOMS)
# ─────────────────────────────────────────────
@app.route('/api/rooms', methods=['GET'])
def get_rooms_api():
    search = request.args.get('search', '')
    filter_floor = request.args.get('tang', '')
    filter_type = request.args.get('ma_loai', '')
    filter_status = request.args.get('trang_thai', '')

    conn = get_db()
    query = """
        SELECT p.*, lp.TenLoai
        FROM PHONG p
        JOIN LOAIPHONG lp ON p.MaLoai = lp.MaLoai
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.SoPhong LIKE ? OR p.MoTa LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if filter_floor:
        query += " AND p.Tang = ?"
        params.append(filter_floor)
    if filter_type:
        query += " AND p.MaLoai = ?"
        params.append(filter_type)
    if filter_status:
        query += " AND p.TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY p.Tang, p.SoPhong"
    
    rooms = conn.execute(query, params).fetchall()
    room_types = conn.execute("SELECT * FROM LOAIPHONG ORDER BY TenLoai").fetchall()
    floors = conn.execute("SELECT DISTINCT Tang FROM PHONG ORDER BY Tang").fetchall()
    conn.close()
    
    return jsonify({
        "status": "success",
        "rooms": [dict(r) for r in rooms],
        "room_types": [dict(rt) for rt in room_types],
        "floors": [dict(f) for f in floors]
    })

@app.route('/api/rooms/add', methods=['POST'])
def add_room_api():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO PHONG (SoPhong, Tang, MaLoai, MoTa, TrangThai) VALUES (?, ?, ?, ?, ?)",
            (data['so_phong'], int(data['tang']), int(data['ma_loai']), data.get('mo_ta', ''), data.get('trang_thai', 'Sẵn sàng'))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rooms/edit/<int:id>', methods=['POST'])
def edit_room_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE PHONG SET SoPhong=?, Tang=?, MaLoai=?, MoTa=?, TrangThai=? WHERE MaPhong=?",
            (data['so_phong'], int(data['tang']), int(data['ma_loai']), data.get('mo_ta', ''), data.get('trang_thai', 'Sẵn sàng'), id)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rooms/toggle/<int:id>', methods=['POST'])
def toggle_room_api(id):
    conn = get_db()
    try:
        phong = conn.execute("SELECT TrangThai FROM PHONG WHERE MaPhong=?", (id,)).fetchone()
        if phong:
            # Toggle giữa Sẵn sàng và Bảo trì (chỉ khi không bị Khóa)
            if phong['TrangThai'] == 'Khóa':
                return jsonify({"status": "error", "message": "Phòng đang bị khóa, hãy mở khóa trước"}), 400
                
            new_status = 'Bảo trì' if phong['TrangThai'] == 'Sẵn sàng' else 'Sẵn sàng'
            conn.execute("UPDATE PHONG SET TrangThai=? WHERE MaPhong=?", (new_status, id))
            conn.commit()
            return jsonify({"status": "success", "new_status": new_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/rooms/lock/<int:id>', methods=['POST'])
def lock_room_api(id):
    conn = get_db()
    try:
        phong = conn.execute("SELECT TrangThai FROM PHONG WHERE MaPhong=?", (id,)).fetchone()
        if phong:
            # Khóa thì chuyển sang 'Khóa', Mở khóa thì chuyển sang 'Sẵn sàng'
            new_status = 'Khóa' if phong['TrangThai'] != 'Khóa' else 'Sẵn sàng'
            conn.execute("UPDATE PHONG SET TrangThai=? WHERE MaPhong=?", (new_status, id))
            conn.commit()
            return jsonify({"status": "success", "new_status": new_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# ─────────────────────────────────────────────
# 🔹 3. QUẢN LÝ LOẠI PHÒNG (ROOM TYPES)
# ─────────────────────────────────────────────
@app.route('/api/room-types', methods=['GET'])
def get_room_types_api():
    search = request.args.get('search', '')
    filter_status = request.args.get('trang_thai', '')
    conn = get_db()
    query = "SELECT * FROM LOAIPHONG WHERE 1=1"
    params = []
    if search:
        query += " AND TenLoai LIKE ?"
        params.append(f'%{search}%')
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY TenLoai"
    types = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({"status": "success", "room_types": [dict(t) for t in types]})

@app.route('/api/room-types/add', methods=['POST'])
def add_room_type_api():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO LOAIPHONG (TenLoai, GiaTien, SoNguoiToiDa, MoTa, TrangThai) VALUES (?, ?, ?, ?, 'Hiển thị')",
            (data['ten_loai'], int(data['gia_tien']), int(data['so_nguoi']), data.get('mo_ta', ''))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/edit/<int:id>', methods=['POST'])
def edit_room_type_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE LOAIPHONG SET TenLoai=?, GiaTien=?, SoNguoiToiDa=?, MoTa=?, TrangThai=? WHERE MaLoai=?",
            (data['ten_loai'], int(data['gia_tien']), int(data['so_nguoi']), data.get('mo_ta', ''), data['trang_thai'], id)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/toggle/<int:id>', methods=['POST'])
def toggle_room_type_api(id):
    conn = get_db()
    try:
        rt = conn.execute("SELECT TrangThai FROM LOAIPHONG WHERE MaLoai=?", (id,)).fetchone()
        if rt:
            # Xác định trạng thái mới cho Loại phòng
            new_rt_status = 'Ẩn' if rt['TrangThai'] == 'Hiển thị' else 'Hiển thị'
            # Xác định trạng thái tương ứng cho các Phòng thuộc loại này
            new_room_status = 'Khóa' if new_rt_status == 'Ẩn' else 'Sẵn sàng'
            
            # Cập nhật cả 2 bảng
            conn.execute("UPDATE PHONG SET TrangThai=? WHERE MaLoai=?", (new_room_status, id))
            conn.execute("UPDATE LOAIPHONG SET TrangThai=? WHERE MaLoai=?", (new_rt_status, id))
            
            conn.commit()
            return jsonify({"status": "success", "new_status": new_rt_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/<int:id>/images', methods=['GET'])
def get_room_type_images_api(id):
    conn = get_db()
    images = conn.execute("SELECT * FROM HINHANH_LOAIPHONG WHERE MaLoai=? ORDER BY LaAnhDaiDien DESC, ThuTu ASC", (id,)).fetchall()
    room_type = conn.execute("SELECT * FROM LOAIPHONG WHERE MaLoai=?", (id,)).fetchone()
    conn.close()
    return jsonify({
        "status": "success",
        "images": [dict(img) for img in images],
        "room_type": dict(room_type) if room_type else {}
    })

@app.route('/api/room-types/<int:id>/images/add', methods=['POST'])
def add_room_type_image_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        if data.get('la_anh_dai_dien') == 1:
            conn.execute("UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=0 WHERE MaLoai=?", (id,))
        conn.execute(
            "INSERT INTO HINHANH_LOAIPHONG (MaLoai, HinhAnh, ThuTu, LaAnhDaiDien) VALUES (?, ?, ?, ?)",
            (id, data['hinh_anh'], int(data.get('thu_tu', 0)), int(data.get('la_anh_dai_dien', 0)))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/images/set-avatar/<int:id>', methods=['POST'])
def set_room_type_avatar_api(id):
    conn = get_db()
    try:
        img = conn.execute("SELECT MaLoai FROM HINHANH_LOAIPHONG WHERE MaAnh=?", (id,)).fetchone()
        if img:
            conn.execute("UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=0 WHERE MaLoai=?", (img['MaLoai'],))
            conn.execute("UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=1 WHERE MaAnh=?", (id,))
            conn.commit()
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/images/delete/<int:id>', methods=['POST'])
def delete_room_type_image_api(id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM HINHANH_LOAIPHONG WHERE MaAnh=?", (id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/room-types/images/reorder', methods=['POST'])
def reorder_room_type_images_api():
    data = request.get_json()
    orders = data.get('orders', [])
    conn = get_db()
    try:
        for item in orders:
            conn.execute("UPDATE HINHANH_LOAIPHONG SET ThuTu=? WHERE MaAnh=?", (item['thu_tu'], item['ma_anh']))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# ─────────────────────────────────────────────
# 🔹 4. QUẢN LÝ DỊCH VỤ (SERVICES)
# ─────────────────────────────────────────────
@app.route('/api/services_admin', methods=['GET'])
def get_services_api_admin():
    search = request.args.get('search', '')
    filter_status = request.args.get('trang_thai', '')
    conn = get_db()
    query = "SELECT * FROM DICHVU WHERE 1=1"
    params = []
    if search:
        query += " AND (TenDV LIKE ? OR MoTa LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY TenDV"
    services = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({"status": "success", "services": [dict(s) for s in services]})

@app.route('/api/services/add', methods=['POST'])
def add_service_api():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO DICHVU (TenDV, MoTa, GiaTien, ThayDoiSL, TinhTheoNgay, TrangThai, HinhAnh) VALUES (?, ?, ?, ?, ?, 'Đang có', ?)",
            (data['ten_dv'], data.get('mo_ta', ''), int(data['gia_tien']), int(data.get('thay_doi_sl', 0)), int(data.get('tinh_theo_ngay', 0)), data.get('hinh_anh'))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/services/edit/<int:id>', methods=['POST'])
def edit_service_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE DICHVU SET TenDV=?, MoTa=?, GiaTien=?, ThayDoiSL=?, TinhTheoNgay=?, TrangThai=?, HinhAnh=? WHERE MaDV=?",
            (data['ten_dv'], data.get('mo_ta', ''), int(data['gia_tien']), int(data.get('thay_doi_sl', 0)), int(data.get('tinh_theo_ngay', 0)), data['trang_thai'], data.get('hinh_anh'), id)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/services/toggle/<int:id>', methods=['POST'])
def toggle_service_api(id):
    conn = get_db()
    try:
        svc = conn.execute("SELECT TrangThai FROM DICHVU WHERE MaDV=?", (id,)).fetchone()
        if svc:
            new_status = 'Đang khóa' if svc['TrangThai'] == 'Đang có' else 'Đang có'
            conn.execute("UPDATE DICHVU SET TrangThai=? WHERE MaDV=?", (new_status, id))
            conn.commit()
            return jsonify({"status": "success", "new_status": new_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# ─────────────────────────────────────────────
# 🔹 5. QUẢN LÝ NHÂN VIÊN (STAFFS)
# ─────────────────────────────────────────────
@app.route('/api/staffs', methods=['GET'])
def get_staffs_api():
    search = request.args.get('search', '')
    filter_role = request.args.get('la_admin', '')
    filter_status = request.args.get('trang_thai', '')
    conn = get_db()
    query = "SELECT * FROM NHANVIEN WHERE 1=1"
    params = []
    if search:
        query += " AND (HoTen LIKE ? OR SDT LIKE ? OR Email LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if filter_role != '':
        query += " AND LaAdmin = ?"
        params.append(filter_role)
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY LaAdmin DESC, HoTen"
    staffs = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({"status": "success", "staffs": [dict(s) for s in staffs]})

@app.route('/api/staffs/add', methods=['POST'])
def add_staff_api():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO NHANVIEN (HoTen, Email, SDT, MatKhau, LaAdmin, TrangThai) VALUES (?, ?, ?, ?, ?, 'Hoạt động')",
            (data['ho_ten'], data.get('email', ''), data['sdt'], data['mat_khau'], int(data.get('la_admin', 0)))
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/staffs/edit/<int:id>', methods=['POST'])
def edit_staff_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        if data.get('mat_khau'):
            conn.execute(
                "UPDATE NHANVIEN SET HoTen=?, Email=?, SDT=?, MatKhau=?, LaAdmin=?, TrangThai=? WHERE MaNV=?",
                (data['ho_ten'], data.get('email', ''), data['sdt'], data['mat_khau'], int(data.get('la_admin', 0)), data['trang_thai'], id)
            )
        else:
            conn.execute(
                "UPDATE NHANVIEN SET HoTen=?, Email=?, SDT=?, LaAdmin=?, TrangThai=? WHERE MaNV=?",
                (data['ho_ten'], data.get('email', ''), data['sdt'], int(data.get('la_admin', 0)), data['trang_thai'], id)
            )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/staffs/toggle/<int:id>', methods=['POST'])
def toggle_staff_api(id):
    conn = get_db()
    try:
        nv = conn.execute("SELECT TrangThai FROM NHANVIEN WHERE MaNV=?", (id,)).fetchone()
        if nv:
            new_status = 'Khóa' if nv['TrangThai'] == 'Hoạt động' else 'Hoạt động'
            conn.execute("UPDATE NHANVIEN SET TrangThai=? WHERE MaNV=?", (new_status, id))
            conn.commit()
            return jsonify({"status": "success", "new_status": new_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# ─────────────────────────────────────────────
# 🔹 6. QUẢN LÝ KHÁCH HÀNG (CUSTOMERS)
# ─────────────────────────────────────────────
@app.route('/api/customers_admin', methods=['GET'])
def get_customers_admin_api():
    search = request.args.get('search', '')
    filter_status = request.args.get('trang_thai', '')
    conn = get_db()
    query = "SELECT * FROM KHACHHANG WHERE 1=1"
    params = []
    if search:
        query += " AND (HoTen LIKE ? OR Email LIKE ? OR SDT LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY HoTen"
    customers = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({"status": "success", "customers": [dict(c) for c in customers]})

@app.route('/api/customers/add', methods=['POST'])
def add_customer_api():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO KHACHHANG (HoTen, Email, SDT, MatKhau, TrangThai) VALUES (?, ?, ?, ?, 'Hoạt động')",
            (data['ho_ten'], data['email'], data['sdt'], data['mat_khau'])
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/customers/edit/<int:id>', methods=['POST'])
def edit_customer_api(id):
    data = request.get_json()
    conn = get_db()
    try:
        if data.get('mat_khau'):
            conn.execute(
                "UPDATE KHACHHANG SET HoTen=?, Email=?, SDT=?, MatKhau=?, TrangThai=? WHERE MaKH=?",
                (data['ho_ten'], data['email'], data['sdt'], data['mat_khau'], data['trang_thai'], id)
            )
        else:
            conn.execute(
                "UPDATE KHACHHANG SET HoTen=?, Email=?, SDT=?, TrangThai=? WHERE MaKH=?",
                (data['ho_ten'], data['email'], data['sdt'], data['trang_thai'], id)
            )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/customers/toggle/<int:id>', methods=['POST'])
def toggle_customer_api(id):
    conn = get_db()
    try:
        kh = conn.execute("SELECT TrangThai FROM KHACHHANG WHERE MaKH=?", (id,)).fetchone()
        if kh:
            new_status = 'Khóa' if kh['TrangThai'] == 'Hoạt động' else 'Hoạt động'
            conn.execute("UPDATE KHACHHANG SET TrangThai=? WHERE MaKH=?", (new_status, id))
            conn.commit()
            return jsonify({"status": "success", "new_status": new_status})
        return jsonify({"status": "error", "message": "Not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# ─────────────────────────────────────────────
# 🔹 7. UPLOAD ẢNH (IMAGE UPLOAD)
# ─────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload_image', methods=['POST'])
def upload_image_api():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Không tìm thấy file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Chưa chọn file"}), 400
    
    folder = request.form.get('folder', 'services')
    upload_folder = f"static/images/{folder}"
    
    if file and allowed_file(file.filename):
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
            
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        
        file.save(filepath)
        return jsonify({
            "status": "success",
            "url": f"images/{folder}/{filename}"
        })
    
    return jsonify({"status": "error", "message": "Định dạng file không hỗ trợ"}), 400