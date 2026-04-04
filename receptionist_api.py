import calendar
from datetime import date, datetime

from flask import jsonify, request

from webapi import app, get_db

# dashboard_rec
# API lấy khoảng năm dành riêng cho Lễ tân
@app.route('/api/rec/years-range-rec', methods=['GET'])
def get_years_range_rec():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(strftime('%Y', NgayNhan)), MAX(strftime('%Y', NgayTra)) FROM CHITIET_DATPHONG")
    row = cursor.fetchone()
    conn.close()

    current_year = datetime.now().year
    start = int(row[0]) if row[0] else current_year
    end = int(row[1]) if row[1] else current_year
    return jsonify({"min_year": min(start, current_year), "max_year": max(end, current_year)})


# API 2: Lấy thống kê cho Lễ tân
@app.route('/api/rec/stats', methods=['GET'])
def get_rec_stats():
    month = int(request.args.get('month'))
    year = int(request.args.get('year'))
    today = datetime.now().strftime('%Y-%m-%d')
    month_filter = f"{year}-{month:02d}"

    conn = get_db()
    cursor = conn.cursor()

    # --- CHUNG (HIỆN TẠI) ---
    cursor.execute("SELECT COUNT(DISTINCT MaPhong) FROM CHITIET_DATPHONG WHERE TrangThai = 'Đã nhận'")
    occupied = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM PHONG WHERE TrangThai = 'Sẵn sàng'")
    available = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE NgayNhan = ? AND TrangThai != 'Đã hủy'", (today,))
    ci_today = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE NgayTra = ? AND TrangThai != 'Đã hủy'", (today,))
    co_today = cursor.fetchone()[0] or 0

    # --- THEO THÁNG ---
    cursor.execute(
        "SELECT COUNT(DISTINCT MaDP) FROM CHITIET_DATPHONG WHERE (strftime('%Y-%m', NgayNhan) = ? OR strftime('%Y-%m', NgayTra) = ?) AND TrangThai != 'Đã hủy'",
        (month_filter, month_filter))
    m_staying = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE strftime('%Y-%m', NgayNhan) = ? AND TrangThai != 'Đã hủy'",
        (month_filter,))
    m_ci = cursor.fetchone()[0] or 0

    cursor.execute(
        "SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE strftime('%Y-%m', NgayTra) = ? AND TrangThai != 'Đã hủy'",
        (month_filter,))
    m_co = cursor.fetchone()[0] or 0

    # --- BIỂU ĐỒ ---
    num_days = calendar.monthrange(year, month)[1]
    labels, chart_ci, chart_co, chart_stay = [], [], [], []

    for d in range(1, num_days + 1):
        d_str = f"{year}-{month:02d}-{d:02d}"
        labels.append(f"{d:02d}")

        cursor.execute("SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE NgayNhan = ? AND TrangThai != 'Đã hủy'", (d_str,))
        chart_ci.append(cursor.fetchone()[0] or 0)

        cursor.execute("SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE NgayTra = ? AND TrangThai != 'Đã hủy'", (d_str,))
        chart_co.append(cursor.fetchone()[0] or 0)

        cursor.execute(
            "SELECT COUNT(*) FROM CHITIET_DATPHONG WHERE NgayNhan <= ? AND NgayTra > ? AND TrangThai != 'Đã hủy'",
            (d_str, d_str))
        chart_stay.append(cursor.fetchone()[0] or 0)

    conn.close()
    return jsonify({
        "general": {"occupied": occupied, "available": available, "ci_today": ci_today, "co_today": co_today},
        "monthly": {"staying": m_staying, "ci": m_ci, "co": m_co},
        "chart": {"labels": labels, "ci": chart_ci, "co": chart_co, "stay": chart_stay}
    })

# KT dashboard_rec

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

    # Ưu tiên kiểm tra các trạng thái vật lý trước
    if room_data['TinhTrangVatLy'] == 'Bảo trì':
        room_data['status_code'] = 'MAINTENANCE'
        room_data['description'] = 'Phòng đang bảo trì'
    elif room_data['TinhTrangVatLy'] == 'Khóa':
        room_data['status_code'] = 'LOCKED'
        room_data['description'] = 'Phòng đang bị khóa'
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
# API 1: Lấy danh sách đặt phòng (Cập nhật lọc MaLoai)
@app.route('/api/rec/bookings', methods=['GET'])
def get_bookings():
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    ma_loai = request.args.get('ma_loai', 'all')  # Thêm tham số này

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

    # Logic tìm kiếm mã/tên
    if search:
        sql += " AND (CT.MaDP LIKE ? OR CT.MaCTDP LIKE ? OR KH.HoTen LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    # Logic lọc trạng thái gán
    if status == 'cho_gan':
        sql += " AND CT.MaPhong IS NULL AND CT.TrangThai = 'Chờ nhận'"
    elif status == 'da_gan':
        sql += " AND CT.MaPhong IS NOT NULL AND CT.TrangThai = 'Chờ nhận'"
    elif status == 'dang_o':
        sql += " AND CT.TrangThai = 'Đã nhận'"

    # LOGIC LỌC THEO LOẠI PHÒNG (MỚI)
    if ma_loai != 'all':
        sql += " AND LP.MaLoai = ?"
        params.append(ma_loai)

    sql += " ORDER BY DP.NgayTao DESC"
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


# API: Hủy gán phòng (đưa MaPhong về NULL)
@app.route('/api/rec/unassign-room', methods=['POST'])
def api_unassign_room():
    data = request.json
    ma_ctdp = data.get('ma_ctdp')

    if not ma_ctdp:
        return jsonify({"status": "error", "message": "Thiếu mã chi tiết đặt phòng"}), 400

    conn = get_db()
    # Chỉ cho phép hủy gán khi phòng chưa Check-in (Trạng thái vẫn là 'Chờ nhận')
    cursor = conn.cursor()
    cursor.execute("UPDATE CHITIET_DATPHONG SET MaPhong = NULL WHERE MaCTDP = ? AND TrangThai = 'Chờ nhận'", (ma_ctdp,))

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"status": "error", "message": "Không thể hủy gán (Phòng đã check-in hoặc không tồn tại)"}), 400

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Đã hủy gán phòng thành công"})


# Kt rooms_assign_rec


# checkin_rec
# 1. API Cập nhật trạng thái đơn đặt (Xác nhận hoặc Hủy)
@app.route('/api/rec/update-booking-status', methods=['POST'])
def api_update_booking_status():
    data = request.json
    ma_dp = data.get('ma_dp')
    new_status = data.get('status')  # 'Đã xác nhận' hoặc 'Đã hủy'

    conn = get_db()
    cursor = conn.cursor()

    # Cập nhật bảng DATPHONG
    cursor.execute("UPDATE DATPHONG SET TrangThai = ? WHERE MaDP = ?", (new_status, ma_dp))

    # Nếu hủy đơn, hủy luôn các chi tiết phòng
    if new_status == 'Đã hủy':
        cursor.execute("UPDATE CHITIET_DATPHONG SET TrangThai = 'Đã hủy' WHERE MaDP = ?", (ma_dp,))
        cursor.execute("""
            UPDATE DATPHONG_DICHVU
            SET TrangThai = 'Đã hủy'
            WHERE MaCTDP IN (
                SELECT MaCTDP
                FROM CHITIET_DATPHONG
                WHERE MaDP = ?
            )
        """, (ma_dp,))

    conn.commit()


    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": f"Đã chuyển đơn #{ma_dp} sang {new_status}"})


# 2. API Danh sách Check-in (Cập nhật logic Gán/Xác nhận)
@app.route('/api/rec/checkin-list', methods=['GET'])
def get_checkin_list():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status_filter', 'all')

    conn = get_db()
    cursor = conn.cursor()

    # Query cơ bản (Giữ nguyên các JOIN để lấy đủ thông tin)
    sql = """
        SELECT DP.*, KH.HoTen, KH.SDT,
               CT.MaCTDP, CT.MaPhong, CT.MaLoai, CT.NgayNhan, CT.NgayTra, 
               CT.TrangThai as TrangThaiCT, P.SoPhong, LP.TenLoai
        FROM DATPHONG DP
        JOIN KHACHHANG KH ON DP.MaKH = KH.MaKH
        JOIN CHITIET_DATPHONG CT ON DP.MaDP = CT.MaDP
        JOIN LOAIPHONG LP ON CT.MaLoai = LP.MaLoai
        LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
        WHERE 1=1
    """
    params = []

    # 1. Cập nhật Logic Tìm kiếm theo 4 tiêu chí: MaDP, MaCTDP, HoTen, TenLoai
    if search:
        sql += """ AND (
            DP.MaDP LIKE ? OR 
            CT.MaCTDP LIKE ? OR 
            KH.HoTen LIKE ? OR 
            LP.TenLoai LIKE ?
        )"""
        # Tạo chuỗi tìm kiếm đại diện %keyword%
        search_val = f'%{search}%'
        # Truyền tham số cho 4 dấu hỏi chấm (?)
        params.extend([search_val, search_val, search_val, search_val])

    # 2. Lọc theo trạng thái đơn
    if status_filter != 'all':
        sql += " AND DP.TrangThai = ?"
        params.append(status_filter)

    sql += " ORDER BY DP.NgayTao DESC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    # Gộp dữ liệu theo MaDP
    bookings_dict = {}
    for row in rows:
        ma_dp = row['MaDP']
        if ma_dp not in bookings_dict:
            bookings_dict[ma_dp] = dict(row)
            bookings_dict[ma_dp]['ChiTiet'] = []

        # Đưa thông tin chi tiết vào mảng con
        bookings_dict[ma_dp]['ChiTiet'].append({
            'MaCTDP': row['MaCTDP'],
            'MaPhong': row['MaPhong'],
            'SoPhong': row['SoPhong'],
            'TenLoai': row['TenLoai'],
            'NgayNhan': row['NgayNhan'],
            'NgayTra': row['NgayTra'],
            'TrangThaiCT': row['TrangThaiCT']
        })

    results = list(bookings_dict.values())
    for b in results:
        # Logic tính toán nút Xác nhận/Check-in
        all_assigned = all(ct['MaPhong'] is not None for ct in b['ChiTiet'])
        b['CanConfirm'] = (b['TrangThai'] == 'Chờ xác nhận' and all_assigned)
        # Thêm flag này nếu cần xử lý giao diện cho Đã xác nhận
        b['CanCheckin'] = (b['TrangThai'] == 'Đã xác nhận' and all_assigned)

    return jsonify(results)


# 2. API Check-in cho từng Chi tiết đặt phòng
@app.route('/api/rec/checkin-detail/<int:ma_ctdp>', methods=['POST'])
def api_checkin_detail(ma_ctdp):
    conn = get_db()
    cursor = conn.cursor()

    # 1. Cập nhật trạng thái Chi tiết đặt phòng
    cursor.execute("UPDATE CHITIET_DATPHONG SET TrangThai = 'Đã nhận' WHERE MaCTDP = ?", (ma_ctdp,))

    # 2. Lấy MaDP của chi tiết này để cập nhật đơn đặt tổng
    cursor.execute("SELECT MaDP FROM CHITIET_DATPHONG WHERE MaCTDP = ?", (ma_ctdp,))
    ma_dp = cursor.fetchone()[0]

    # 3. Chuyển trạng thái DATPHONG thành 'Đang lưu trú'
    cursor.execute("UPDATE DATPHONG SET TrangThai = 'Đang lưu trú' WHERE MaDP = ?", (ma_dp,))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# Kt checkin_rec

# services_manage_rec
@app.route('/api/rec/service-orders', methods=['GET'])
def get_service_orders():
    status_filter = request.args.get('status', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search = request.args.get('search', '')

    conn = get_db()
    cursor = conn.cursor()

    sql = """
        SELECT 
            PDV.MaPDV, PDV.MaCTDP, PDV.DonGia, PDV.SoLuong, PDV.Ngay, PDV.Gio, 
            PDV.TrangThai as OrderStatus,
            DV.TenDV, DV.TrangThai as CatalogStatus,
            P.SoPhong, KH.HoTen,
            CT.MaDP, CT.MaCTDP,
            DP.TrangThai as BookingStatus, -- Trạng thái Đơn Đặt
            CT.TrangThai as DetailStatus   -- Trạng thái Phòng (Chi tiết)
        FROM DATPHONG_DICHVU PDV
        JOIN DICHVU DV ON PDV.MaDV = DV.MaDV
        JOIN CHITIET_DATPHONG CT ON PDV.MaCTDP = CT.MaCTDP
        JOIN DATPHONG DP ON CT.MaDP = DP.MaDP
        JOIN KHACHHANG KH ON DP.MaKH = KH.MaKH
        LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
        WHERE 1=1
    """
    params = []

    if status_filter != 'all':
        sql += " AND PDV.TrangThai = ?"
        params.append(status_filter)

    if start_date:
        sql += " AND PDV.Ngay >= ?"
        params.append(start_date)

    if end_date:
        sql += " AND PDV.Ngay <= ?"
        params.append(end_date)

    if search:
        sql += " AND (P.SoPhong LIKE ? OR KH.HoTen LIKE ? OR DV.TenDV LIKE ? OR CT.MaDP LIKE ? OR CT.MaCTDP LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])

    # SẮP XẾP THEO NGÀY TĂNG DẦN
    sql += " ORDER BY PDV.Ngay ASC, PDV.Gio ASC"

    cursor.execute(sql, params)
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(orders)

# API 2: Lấy danh mục tất cả dịch vụ của khách sạn (Cho Tab 2)
@app.route('/api/rec/service-catalog', methods=['GET'])
def get_service_catalog():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DICHVU ORDER BY TenDV ASC")
    services = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(services)

@app.route('/api/rec/update-service-status', methods=['POST'])
def update_service_status():
    data = request.json
    ma_pdv = data.get('ma_pdv')
    new_status = data.get('status')  # 'Đã phục vụ' hoặc 'Đã hủy'

    conn = get_db()
    conn.execute("UPDATE DATPHONG_DICHVU SET TrangThai = ? WHERE MaPDV = ?", (new_status, ma_pdv))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# Kt services_manage_rec

# checkout_rec
@app.route('/api/rec/checkout-list', methods=['GET'])
def get_checkout_list():
    search = request.args.get('search', '')
    pay_filter = request.args.get('pay_filter', 'all')
    booking_filter = request.args.get('booking_filter', 'all')

    conn = get_db()
    cursor = conn.cursor()

    sql = """
        SELECT DP.*, KH.HoTen, KH.SDT
        FROM DATPHONG DP
        JOIN KHACHHANG KH ON DP.MaKH = KH.MaKH
        WHERE DP.TrangThai IN ('Đang lưu trú', 'Hoàn tất')
    """
    params = []
    if search:
        sql += " AND (DP.MaDP LIKE ? OR KH.HoTen LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if booking_filter != 'all':
        sql += " AND DP.TrangThai = ?"
        params.append(booking_filter)
    if pay_filter == 'paid':
        sql += " AND DP.MaNV IS NOT NULL"
    elif pay_filter == 'unpaid':
        sql += " AND DP.MaNV IS NULL"

    cursor.execute(sql + " ORDER BY DP.NgayTao DESC", params)
    bookings = [dict(row) for row in cursor.fetchall()]

    for b in bookings:
        # Lấy chi tiết phòng và TÍNH SỐ NGÀY Ở (Dùng julianday)
        # MAX(1, ...) đảm bảo dù khách check-out trong ngày vẫn tính 1 ngày tiền phòng
        cursor.execute("""
            SELECT CT.*, LP.TenLoai, P.SoPhong,
            CAST(MAX(1, julianday(CT.NgayTra) - julianday(CT.NgayNhan)) AS INTEGER) as SoNgayO
            FROM CHITIET_DATPHONG CT
            JOIN LOAIPHONG LP ON CT.MaLoai = LP.MaLoai
            LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
            WHERE CT.MaDP = ?
        """, (b['MaDP'],))
        chi_tiet_phong = [dict(row) for row in cursor.fetchall()]

        total_actual = 0
        all_returned = True

        for ct in chi_tiet_phong:
            # Lấy dịch vụ 'Đã phục vụ'
            cursor.execute("""
                SELECT DPDV.*, DV.TenDV
                FROM DATPHONG_DICHVU DPDV
                JOIN DICHVU DV ON DPDV.MaDV = DV.MaDV
                WHERE DPDV.MaCTDP = ? AND DPDV.TrangThai = 'Đã phục vụ'
            """, (ct['MaCTDP'],))
            ct['DichVu'] = [dict(row) for row in cursor.fetchall()]

            # Tiền phòng = Đơn giá * Số ngày (Chỉ tính cho phòng Đã nhận hoặc Đã trả)
            if ct['TrangThai'] in ['Đã nhận', 'Đã trả']:
                ct['ThanhTienPhong'] = ct['GiaPhong'] * ct['SoNgayO']
                total_actual += ct['ThanhTienPhong']

            if ct['TrangThai'] == 'Đã nhận':
                all_returned = False

            # Tiền dịch vụ
            ct['TongTienDV'] = sum(dv['DonGia'] * dv['SoLuong'] for dv in ct['DichVu'])
            total_actual += ct['TongTienDV']

        b['ChiTiet'] = chi_tiet_phong
        b['TongTienThucTe'] = total_actual
        b['IsPaid'] = b['MaNV'] is not None
        b['CanPay'] = (b['TrangThai'] == 'Đang lưu trú' and not b['IsPaid'])
        # Chỉ cho Hoàn tất nếu Đã thanh toán (MaNV != None) và Tất cả phòng đã trả/hủy
        b['CanComplete'] = (b['TrangThai'] == 'Đang lưu trú' and b['IsPaid'] and all_returned)

    conn.close()
    return jsonify(bookings)


@app.route('/api/rec/process-payment', methods=['POST'])
def api_process_payment():
    data = request.json
    ma_dp = data.get('ma_dp')
    ma_nv = data.get('ma_nv')
    tong_tien = data.get('tong_tien')
    phuong_thuc = data.get('phuong_thuc')  # Phương thức do lễ tân chọn lại

    conn = get_db()
    # Cập nhật cả tổng tiền thực tế, phương thức thanh toán và mã nhân viên thu tiền
    conn.execute("""
        UPDATE DATPHONG 
        SET TongTien = ?, ThanhToan = ?, MaNV = ? 
        WHERE MaDP = ?
    """, (tong_tien, phuong_thuc, ma_nv, ma_dp))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# API Cập nhật trạng thái chi tiết phòng (Dùng để Checkout từng phòng)
@app.route('/api/rec/update-detail-status', methods=['POST'])
def api_update_detail_status():
    data = request.json
    conn = get_db()
    conn.execute("UPDATE CHITIET_DATPHONG SET TrangThai = ? WHERE MaCTDP = ?",
                 (data['status'], data['ma_ctdp']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# Kt checkout

# customer_list_rec
@app.route('/api/rec/customers', methods=['GET'])
def api_get_customers():
    search = request.args.get('search', '')
    status_filter = request.args.get('status_filter', 'all')
    today = date.today().isoformat()

    conn = get_db()
    cursor = conn.cursor()

    sql = f"""
                SELECT 
                    KH.MaKH, KH.HoTen, KH.SDT, KH.Email,
                    -- (Các trường cũ giữ nguyên...)
                    (SELECT COUNT(*) FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Hoàn tất') as SoDonThanhCong,
                    (SELECT COUNT(*) FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Chờ xác nhận') as CoDonChoXacNhan,
                    (SELECT GROUP_CONCAT(P.SoPhong, ', ') FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP JOIN PHONG P ON CT.MaPhong = P.MaPhong WHERE DP.MaKH = KH.MaKH AND DP.TrangThai = 'Đang lưu trú') as CacPhongDangO,
                    (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP WHERE DP.MaKH = KH.MaKH AND CT.NgayNhan = '{today}' AND DP.TrangThai = 'Đã xác nhận') as CoCheckinHomNay,
                    (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP WHERE DP.MaKH = KH.MaKH AND CT.NgayTra = '{today}' AND DP.TrangThai = 'Đang lưu trú') as CoCheckoutHomNay,
                    (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP WHERE DP.MaKH = KH.MaKH AND CT.MaPhong IS NULL AND DP.TrangThai = 'Đã xác nhận') as ChuaGanPhong,

                    -- MỚI: Đếm các phòng sẽ đến trong tương lai
                    (SELECT COUNT(*) FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP 
                     WHERE DP.MaKH = KH.MaKH AND CT.NgayNhan > '{today}' 
                     AND DP.TrangThai IN ('Chờ xác nhận', 'Đã xác nhận')) as CoDonTuongLai
                FROM KHACHHANG KH
                WHERE 1=1
            """
    params = []

    # 1. Lọc theo tìm kiếm (Tên, SĐT, Email)
    if search:
        sql += " AND (KH.HoTen LIKE ? OR KH.SDT LIKE ? OR KH.Email LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    # 2. Lọc theo Tình trạng hiện tại (Dùng EXISTS để lọc chính xác)
    if status_filter == 'dang_o':
        sql += " AND EXISTS (SELECT 1 FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Đang lưu trú')"

    elif status_filter == 'sap_den':
        # Khách có phòng check-in từ hôm nay trở đi và đơn đã xác nhận/chờ xác nhận
        sql += f""" AND EXISTS (
            SELECT 1 FROM CHITIET_DATPHONG CT 
            JOIN DATPHONG DP ON CT.MaDP = DP.MaDP 
            WHERE DP.MaKH = KH.MaKH AND CT.NgayNhan >= '{today}' AND DP.TrangThai IN ('Chờ xác nhận', 'Đã xác nhận')
        )"""

    elif status_filter == 'cho_xac_nhan':
        sql += " AND EXISTS (SELECT 1 FROM DATPHONG WHERE MaKH = KH.MaKH AND TrangThai = 'Chờ xác nhận')"

    elif status_filter == 'chua_gan_phong':
        sql += " AND EXISTS (SELECT 1 FROM CHITIET_DATPHONG CT JOIN DATPHONG DP ON CT.MaDP = DP.MaDP WHERE DP.MaKH = KH.MaKH AND CT.MaPhong IS NULL AND DP.TrangThai = 'Đã xác nhận')"

    cursor.execute(sql, params)
    customers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(customers)


@app.route('/api/rec/customer-history/<int:ma_kh>', methods=['GET'])
def api_customer_history(ma_kh):
    conn = get_db()
    cursor = conn.cursor()

    # Truy vấn lấy cả thông tin Phòng và Dịch vụ đi kèm của từng phòng
    sql = """
        SELECT 
            DP.MaDP, DP.NgayTao, DP.TongTien, DP.TrangThai as TrangThaiDon,
            CT.MaCTDP, CT.GiaPhong, CT.NgayNhan, CT.NgayTra, CT.TrangThai as TrangThaiPhong,
            LP.TenLoai, P.SoPhong,
            DV.TenDV, DPDV.SoLuong, DPDV.DonGia as GiaDV, DPDV.TrangThai as TrangThaiDV, DPDV.Ngay as NgayDV
        FROM DATPHONG DP
        JOIN CHITIET_DATPHONG CT ON DP.MaDP = CT.MaDP
        JOIN LOAIPHONG LP ON CT.MaLoai = LP.MaLoai
        LEFT JOIN PHONG P ON CT.MaPhong = P.MaPhong
        LEFT JOIN DATPHONG_DICHVU DPDV ON CT.MaCTDP = DPDV.MaCTDP
        LEFT JOIN DICHVU DV ON DPDV.MaDV = DV.MaDV
        WHERE DP.MaKH = ?
        ORDER BY DP.NgayTao DESC, DP.MaDP DESC, CT.MaCTDP DESC
    """
    cursor.execute(sql, (ma_kh,))
    rows = cursor.fetchall()
    conn.close()

    bookings_dict = {}
    for row in rows:
        ma_dp = row['MaDP']
        ma_ctdp = row['MaCTDP']

        # 1. Khởi tạo Đơn hàng (Booking)
        if ma_dp not in bookings_dict:
            bookings_dict[ma_dp] = {
                "MaDP": ma_dp,
                "NgayTao": row['NgayTao'],
                "TongTien": row['TongTien'],
                "TrangThaiDon": row['TrangThaiDon'],
                "ChiTietPhong": {}  # Dùng dict để gộp dịch vụ vào đúng phòng
            }

        # 2. Khởi tạo/Lấy thông tin Phòng (Room)
        if ma_ctdp not in bookings_dict[ma_dp]["ChiTietPhong"]:
            bookings_dict[ma_dp]["ChiTietPhong"][ma_ctdp] = {
                "MaCTDP": ma_ctdp,
                "SoPhong": row['SoPhong'],
                "TenLoai": row['TenLoai'],
                "GiaPhong": row['GiaPhong'],
                "NgayNhan": row['NgayNhan'],
                "NgayTra": row['NgayTra'],
                "TrangThaiPhong": row['TrangThaiPhong'],
                "DichVu": []
            }

        # 3. Thêm Dịch vụ vào phòng (nếu có)
        if row['TenDV']:
            bookings_dict[ma_dp]["ChiTietPhong"][ma_ctdp]["DichVu"].append({
                "TenDV": row['TenDV'],
                "SoLuong": row['SoLuong'],
                "GiaDV": row['GiaDV'],
                "NgayDV": row['NgayDV'],
                "TrangThaiDV": row['TrangThaiDV']
            })

    # Chuyển đổi cấu trúc dict về list để JSON trả về mảng
    result = []
    for dp_id in bookings_dict:
        # Biến ChiTietPhong từ dict thành list
        bookings_dict[dp_id]["ChiTiet"] = list(bookings_dict[dp_id]["ChiTietPhong"].values())
        del bookings_dict[dp_id]["ChiTietPhong"]
        result.append(bookings_dict[dp_id])

    return jsonify(result)
# Kt customer_list_rec

