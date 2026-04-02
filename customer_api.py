from flask import jsonify, request
from webapi import app, get_db


# Hàm hỗ trợ dọn dẹp đường dẫn ảnh (Vì DB giờ đã có static/ rồi)
def format_image_path(path):
    if not path:
        return "static/images/default_room.jpg"
    return path


# --- 1. API: LẤY 6 PHÒNG ĐỘNG (Dùng cho Trang chủ & Gợi ý) ---
@app.route('/api/top_rooms', methods=['GET'])
def get_top_rooms():
    conn = get_db()
    try:
        # Bốc 3 loại phòng, mỗi loại lấy 2 ảnh để thành 6 card như mày muốn
        cursor = conn.execute("SELECT * FROM LOAIPHONG LIMIT 3")
        base_rooms = [dict(row) for row in cursor.fetchall()]

        final_rooms = []
        for room in base_rooms:
            img_cursor = conn.execute("SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = ?", (room['MaLoai'],))
            images = img_cursor.fetchall()

            for img_row in images:
                new_room = room.copy()
                # path bây giờ đã là 'static/images/rooms/xxx.jpg' từ DB
                new_room['HinhAnhDaiDien'] = f"/{format_image_path(img_row['HinhAnh'])}"
                final_rooms.append(new_room)

        return jsonify({"status": "success", "data": final_rooms[:6]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 2. API: TÌM KIẾM PHÒNG (Dùng cho rooms_list) ---
@app.route('/api/search_rooms', methods=['GET'])
def search_rooms_api():
    max_price = request.args.get('max_price', 10000000)
    conn = get_db()
    query = """
        SELECT lp.*, 
        (SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = lp.MaLoai LIMIT 1) as HinhAnhPath
        FROM LOAIPHONG lp
        WHERE lp.GiaTien <= ?
    """
    try:
        cursor = conn.execute(query, (max_price,))
        rooms = [dict(row) for row in cursor.fetchall()]
        for r in rooms:
            r['HinhAnhDaiDien'] = f"/{format_image_path(r['HinhAnhPath'])}"
        return jsonify({"status": "success", "data": rooms})
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
        images = [{"HinhAnh": f"/{format_image_path(row['HinhAnh'])}"} for row in img_cursor.fetchall()]

        room_dict['HinhAnhDaiDien'] = images[0]['HinhAnh'] if images else "/static/images/default_room.jpg"

        return jsonify({"status": "success", "data": room_dict, "images": images})
    finally:
        conn.close()


# --- 4. API: DANH SÁCH DỊCH VỤ ---
@app.route('/api/services', methods=['GET'])
def get_services_api():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT * FROM DICHVU WHERE TrangThai = 'Đang có'")
        services = [dict(row) for row in cursor.fetchall()]
        for s in services:
            s['HinhAnh'] = f"/{format_image_path(s['HinhAnh'])}"
        return jsonify({"status": "success", "data": services})
    finally:
        conn.close()


# --- 5. API: LƯU ĐƠN ĐẶT PHÒNG ---
@app.route('/api/save_booking', methods=['POST'])
def save_booking_api():
    data = request.get_json()
    conn = get_db()
    try:
        # Chèn vào bảng DATPHONG
        cursor = conn.execute(
            "INSERT INTO DATPHONG (MaKH, TongTien, ThanhToan, TrangThai) VALUES (?, ?, ?, 'Chờ xác nhận')",
            (data['ma_kh'], 0, data['payment'])  # Tổng tiền sẽ update sau hoặc tính toán ở client
        )
        ma_dp = cursor.lastrowid

        # Chèn chi tiết
        for item in data['cart']:
            conn.execute(
                "INSERT INTO CHITIET_DATPHONG (MaDP, MaLoai, GiaPhong, SoNguoi, NgayNhan, NgayTra) VALUES (?, ?, ?, ?, ?, ?)",
                (ma_dp, item['MaLoai'], item['GiaTien'], item['SoNguoiToiDa'], item['checkin'], item['checkout'])
            )
        conn.commit()
        return jsonify({"status": "success", "ma_dp": ma_dp})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- 6. API: LỊCH SỬ ĐẶT PHÒNG ---
@app.route('/api/history/<int:ma_kh>', methods=['GET'])
def get_history_api(ma_kh):
    conn = get_db()
    try:
        cursor = conn.execute("SELECT * FROM DATPHONG WHERE MaKH = ? ORDER BY NgayTao DESC", (ma_kh,))
        list_dp = [dict(row) for row in cursor.fetchall()]
        for dp in list_dp:
            # Lấy chi tiết phòng
            ct_cursor = conn.execute("""
                SELECT ct.*, lp.TenLoai FROM CHITIET_DATPHONG ct 
                JOIN LOAIPHONG lp ON ct.MaLoai = lp.MaLoai WHERE ct.MaDP = ?
            """, (dp['MaDP'],))
            dp['DanhSachChiTiet'] = [dict(r) for r in ct_cursor.fetchall()]
        return jsonify({"status": "success", "data": list_dp})
    finally:
        conn.close()