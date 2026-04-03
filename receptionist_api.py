from datetime import date, datetime

from flask import jsonify, request

from webapi import app, get_db

# API của rooms_layout_rec
@app.route('/api/rec/room-status/<ma_phong>', methods=['GET'])
def get_single_room_status(ma_phong):
    # Lấy tham số ngày từ URL (mặc định là hôm nay)
    checkin = request.args.get('checkin_date', date.today().isoformat())
    checkout = request.args.get('checkout_date', date.today().isoformat())

    conn = get_db()
    cursor = conn.cursor()

    # 1. Lấy thông tin cơ bản của phòng đó
    sql_phong = """
        SELECT P.MaPhong, P.SoPhong, P.Tang, P.TrangThai as TinhTrangVatLy, LP.TenLoai 
        FROM PHONG P 
        JOIN LOAIPHONG LP ON P.MaLoai = LP.MaLoai 
        WHERE P.MaPhong = ?
    """
    cursor.execute(sql_phong, (ma_phong,))
    room = cursor.fetchone()

    if not room:
        conn.close()
        return jsonify({"error": "Không tìm thấy phòng"}), 404

    room_data = dict(room)

    # 2. Kiểm tra xem phòng này có bị đặt trong khoảng thời gian đó không
    sql_booked = """
        SELECT KH.HoTen, CT.NgayTra, CT.NgayNhan
        FROM CHITIET_DATPHONG CT
        JOIN DATPHONG DP ON CT.MaDP = DP.MaDP
        JOIN KHACHHANG KH ON DP.MaKH = KH.MaKH
        WHERE CT.MaPhong = ? 
          AND CT.NgayNhan < ? 
          AND CT.NgayTra > ? 
          AND CT.TrangThai NOT IN ('Đã hủy', 'Đã trả')
        LIMIT 1
    """
    cursor.execute(sql_booked, (ma_phong, checkout, checkin))
    booking = cursor.fetchone()
    conn.close()

    # 3. Xác định trạng thái logic
    today_str = date.today().isoformat()

    if room_data['TinhTrangVatLy'] == 'Bảo trì':
        room_data['status_code'] = 'MAINTENANCE'
        room_data['description'] = 'Phòng đang bảo trì'
    elif booking:
        room_data['status_code'] = 'OCCUPIED'
        room_data['customer_name'] = booking['HoTen']
        room_data['checkin_booked'] = booking['NgayNhan']
        room_data['checkout_booked'] = booking['NgayTra']
        room_data['is_checkout_today'] = (booking['NgayTra'] == today_str)
        room_data['description'] = f"Khách: {booking['HoTen']} (Trả: {booking['NgayTra']})"
    else:
        room_data['status_code'] = 'AVAILABLE'
        room_data['description'] = 'Phòng trống'

    return jsonify(room_data)

# --- API Lấy danh sách các tầng hiện có ---
@app.route('/api/rec/floors', methods=['GET'])
def get_floors():
    conn = get_db()
    cursor = conn.cursor()
    # Lấy các tầng duy nhất từ bảng PHONG
    cursor.execute("SELECT DISTINCT Tang FROM PHONG ORDER BY Tang ASC")
    floors = [row['Tang'] for row in cursor.fetchall()]
    conn.close()
    return jsonify(floors)

# --- API: Lấy danh sách phòng trong một tầng ---
@app.route('/api/rec/floors/<int:tang>/rooms', methods=['GET'])
def get_rooms_by_floor(tang):
    conn = get_db()
    cursor = conn.cursor()

    sql = """
        SELECT P.MaPhong, P.SoPhong, P.MaLoai, LP.TenLoai
        FROM PHONG P
        JOIN LOAIPHONG LP ON P.MaLoai = LP.MaLoai
        WHERE P.Tang = ?
        ORDER BY P.SoPhong ASC
    """
    cursor.execute(sql, (tang,))
    rooms = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(rooms)

@app.route('/api/rec/room-types-rec', methods=['GET'])
def get_room_types():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT MaLoai, TenLoai FROM LOAIPHONG ORDER BY TenLoai ASC")
    types = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(types)


# API của room_assign_rec
# 1. API lấy danh sách đặt phòng kèm bộ lọc
@app.route('/api/rec/bookings', methods=['GET'])
def get_bookings():
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')

    conn = get_db()
    cursor = conn.cursor()

    sql = """
        SELECT CT.MaCTDP, CT.MaDP, CT.MaPhong, CT.NgayNhan, CT.NgayTra, CT.TrangThai as TrangThaiCT,
               CT.SoNguoi, CT.GiaPhong, KH.HoTen, KH.SDT, LP.TenLoai, LP.MaLoai, P.SoPhong, P.Tang
        FROM CHITIET_DATPHONG CT
        JOIN DATPHONG DP ON CT.MaDP = DP.MaDP
        JOIN KHACHHANG KH ON DP.MaKH = KH.MaKH
        JOIN LOAIPHONG LP ON CT.MaLoai = LP.MaLoai
        LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
        WHERE CT.TrangThai NOT IN ('Đã trả', 'Đã hủy')
    """
    params = []
    if search:
        sql += " AND (CT.MaDP LIKE ? OR CT.MaCTDP LIKE ? OR KH.HoTen LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if status == 'cho_gan':
        sql += " AND CT.MaPhong IS NULL AND CT.TrangThai = 'Chờ nhận'"
    elif status == 'da_gan':
        sql += " AND CT.MaPhong IS NOT NULL AND CT.TrangThai = 'Chờ nhận'"
    elif status == 'dang_o':
        sql += " AND CT.TrangThai = 'Đã nhận'"

    cursor.execute(sql, params)
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)


# 2. API lấy toàn bộ phòng và các khoảng thời gian đã bận
@app.route('/api/rec/rooms-metadata', methods=['GET'])
def get_rooms_metadata():
    conn = get_db()
    cursor = conn.cursor()

    # Lấy danh sách phòng
    cursor.execute("SELECT MaPhong, SoPhong, Tang, MaLoai, TrangThai FROM PHONG")
    rooms = [dict(row) for row in cursor.fetchall()]

    # Lấy lịch bận
    cursor.execute(
        "SELECT MaCTDP, MaPhong, NgayNhan, NgayTra FROM CHITIET_DATPHONG WHERE TrangThai NOT IN ('Đã trả', 'Đã hủy')")
    intervals = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({"rooms": rooms, "booked_intervals": intervals})


# 3. API Gán phòng
@app.route('/api/rec/assign-room', methods=['POST'])
def api_assign_room():
    data = request.json
    ma_ctdp = data.get('ma_ctdp')
    ma_phong = data.get('ma_phong')

    conn = get_db()
    conn.execute("UPDATE CHITIET_DATPHONG SET MaPhong = ? WHERE MaCTDP = ?", (ma_phong, ma_ctdp))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})


# 4. API Check-in
@app.route('/api/rec/checkin/<int:ma_ctdp>', methods=['POST'])
def api_checkin(ma_ctdp):
    conn = get_db()
    conn.execute("UPDATE CHITIET_DATPHONG SET TrangThai = 'Đã nhận' WHERE MaCTDP = ?", (ma_ctdp,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# Kt rooms_assign_rec

# customer_list_rec
@app.route('/api/rec/customers', methods=['GET'])
def api_get_customers():
    search = request.args.get('search', '')
    today = date.today().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    sql = f"""
            SELECT 
                KH.MaKH, KH.HoTen, KH.SDT, KH.Email,
                (SELECT COUNT(*) FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Hoàn tất') as SoDonThanhCong,
                -- Đếm số đơn đang Chờ xác nhận
                (SELECT COUNT(*) FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Chờ xác nhận') as CoDonChoXacNhan,

                (SELECT GROUP_CONCAT(P.SoPhong, ', ') 
                 FROM CHITIET_DATPHONG CT 
                 JOIN DATPHONG DP ON CT.MaDP = DP.MaDP
                 JOIN PHONG P ON CT.MaPhong = P.MaPhong
                 WHERE DP.MaKH = KH.MaKH AND DP.TrangThai = 'Đang lưu trú') as CacPhongDangO,

                (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP 
                 WHERE DP.MaKH = KH.MaKH AND CT.NgayNhan = '{today}' AND DP.TrangThai = 'Đã xác nhận') as CoCheckinHomNay,

                (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP 
                 WHERE DP.MaKH = KH.MaKH AND CT.NgayTra = '{today}' AND DP.TrangThai = 'Đang lưu trú') as CoCheckoutHomNay,

                (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP 
                 WHERE DP.MaKH = KH.MaKH AND CT.MaPhong IS NULL AND DP.TrangThai = 'Đã xác nhận') as ChuaGanPhong
            FROM KHACHHANG KH
            WHERE 1=1
        """
    params = []
    if search:
        sql += " AND (KH.HoTen LIKE ? OR KH.SDT LIKE ? OR KH.Email LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    cursor.execute(sql, params)
    customers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(customers)


@app.route('/api/rec/customer-history/<int:ma_kh>', methods=['GET'])
def api_customer_history(ma_kh):
    conn = get_db()
    cursor = conn.cursor()

    # Lấy toàn bộ chi tiết của tất cả các đơn khách đã đặt
    sql = """
        SELECT 
            DP.MaDP, DP.NgayTao, DP.TongTien, DP.TrangThai as TrangThaiDon,
            CT.MaCTDP, CT.GiaPhong, CT.NgayNhan, CT.NgayTra, CT.TrangThai as TrangThaiPhong,
            LP.TenLoai, P.SoPhong
        FROM DATPHONG DP
        JOIN CHITIET_DATPHONG CT ON DP.MaDP = CT.MaDP
        JOIN LOAIPHONG LP ON CT.MaLoai = LP.MaLoai
        LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
        WHERE DP.MaKH = ?
        ORDER BY DP.NgayTao DESC, DP.MaDP DESC
    """
    cursor.execute(sql, (ma_kh,))
    rows = cursor.fetchall()
    conn.close()

    # Tổ chức lại dữ liệu: Gộp các CTDP vào trong DP tương ứng
    bookings_dict = {}
    for row in rows:
        ma_dp = row['MaDP']
        if ma_dp not in bookings_dict:
            bookings_dict[ma_dp] = {
                "MaDP": ma_dp,
                "NgayTao": row['NgayTao'],
                "TongTien": row['TongTien'],
                "TrangThaiDon": row['TrangThaiDon'],
                "ChiTiet": []
            }

        bookings_dict[ma_dp]["ChiTiet"].append({
            "MaCTDP": row['MaCTDP'],
            "SoPhong": row['SoPhong'],
            "TenLoai": row['TenLoai'],
            "GiaPhong": row['GiaPhong'],
            "NgayNhan": row['NgayNhan'],
            "NgayTra": row['NgayTra'],
            "TrangThaiPhong": row['TrangThaiPhong']
        })

    return jsonify(list(bookings_dict.values()))
# Kt customer_list_rec

