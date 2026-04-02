from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os

app = Flask(__name__)
sqldbname = 'db/website.db'

# --- 1. CẤU HÌNH THƯ MỤC ẢNH ---
# Lấy đường dẫn tuyệt đối để tránh lỗi khi chạy từ các thư mục khác nhau
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Thư mục images nằm ngang hàng với file webapi.py
IMAGE_FOLDER = os.path.join(BASE_DIR, 'images')

# Route phục vụ ảnh từ thư mục ngoài static
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

def get_db():
    conn = sqlite3.connect(sqldbname)
    conn.row_factory = sqlite3.Row
    return conn

# Hàm hỗ trợ làm sạch đường dẫn ảnh (loại bỏ chữ 'images/' thừa nếu có trong DB)
def clean_image_path(path):
    if not path:
        return "default_room.jpg"
    # Nếu DB lưu 'images/rooms/abc.jpg' -> chỉ lấy 'rooms/abc.jpg'
    if path.startswith('images/'):
        return path.replace('images/', '', 1)
    return path

# --- 2. ENDPOINT: ĐĂNG NHẬP ---
@app.route('/login', methods=['POST'])
def login_api():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ!"}), 400

    email, password, role = data.get('email'), data.get('password'), data.get('role')
    conn = get_db()
    res = {"status": "error", "message": "Sai tài khoản hoặc mật khẩu!"}

    try:
        if role == 'nhanvien':
            query = "SELECT * FROM NHANVIEN WHERE SDT = ? AND MatKhau = ?"
            user = conn.execute(query, (email, password)).fetchone()
            if user:
                res = {"status": "success", "data": {"MaTK": user['MaNV'], "HoTen": user['HoTen'], "ChucVu": "nhanvien", "LaAdmin": user['LaAdmin']}}
        else:
            query = "SELECT * FROM KHACHHANG WHERE Email = ? AND MatKhau = ?"
            user = conn.execute(query, (email, password)).fetchone()
            if user:
                res = {"status": "success", "data": {"MaTK": user['MaKH'], "HoTen": user['HoTen'], "ChucVu": "khach"}}
    finally:
        conn.close()
    return jsonify(res)

# --- 3. ENDPOINT: TRANG CHỦ (TOP 3 PHÒNG) ---
@app.route('/api/top_rooms', methods=['GET'])
def get_top_rooms():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT * FROM LOAIPHONG LIMIT 3")
        rooms = [dict(row) for row in cursor.fetchall()]
        for room in rooms:
            img_cursor = conn.execute("SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = ? LIMIT 1", (room['MaLoai'],))
            img_row = img_cursor.fetchone()
            path = clean_image_path(img_row['HinhAnh'] if img_row else None)
            room['HinhAnhDaiDien'] = f"/images/{path}"
        return jsonify({"status": "success", "data": rooms})
    finally:
        conn.close()

# --- 4. ENDPOINT: TÌM PHÒNG TRỐNG (FIX LỖI SoLuongTrong) ---
@app.route('/api/search_rooms', methods=['GET'])
def search_rooms():
    checkin = request.args.get('checkin', '')
    checkout = request.args.get('checkout', '')
    max_price = request.args.get('max_price', 10000000)

    conn = get_db()
    # Query đầy đủ để lấy thông tin loại phòng và đếm số lượng phòng còn sẵn sàng
    query = """
        SELECT lp.*, 
        (SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = lp.MaLoai LIMIT 1) as HinhAnhPath,
        (SELECT COUNT(*) FROM PHONG p WHERE p.MaLoai = lp.MaLoai AND p.TrangThai = 'Sẵn sàng') as SoLuongTrong
        FROM LOAIPHONG lp
        WHERE lp.GiaTien <= ?
    """

    try:
        cursor = conn.execute(query, (max_price,))
        rooms = [dict(row) for row in cursor.fetchall()]

        for r in rooms:
            # Xử lý đường dẫn ảnh
            path = clean_image_path(r.get('HinhAnhPath'))
            r['HinhAnhDaiDien'] = f"/images/{path}"
            # Đảm bảo key SoLuongTrong luôn tồn tại để tránh lỗi Jinja2
            if r.get('SoLuongTrong') is None:
                r['SoLuongTrong'] = 0

        return jsonify({"status": "success", "data": rooms})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- 5. ENDPOINT: CHI TIẾT LOẠI PHÒNG ---
@app.route('/api/room/<ma_loai>', methods=['GET'])
def get_room_detail_api(ma_loai):
    conn = get_db()
    try:
        room = conn.execute("SELECT * FROM LOAIPHONG WHERE MaLoai = ?", (ma_loai,)).fetchone()
        images = conn.execute("SELECT HinhAnh FROM HINHANH_LOAIPHONG WHERE MaLoai = ?", (ma_loai,)).fetchall()

        if room:
            room_dict = dict(room)
            img_list = []
            for img in images:
                p = clean_image_path(img['HinhAnh'])
                img_list.append({"HinhAnh": f"/images/{p}"})

            if img_list:
                room_dict['HinhAnhDaiDien'] = img_list[0]['HinhAnh']
            else:
                room_dict['HinhAnhDaiDien'] = "/images/default_room.jpg"

            return jsonify({
                "status": "success",
                "data": room_dict,
                "images": img_list
            })
        return jsonify({"status": "error", "message": "Phòng không tồn tại"}), 404
    finally:
        conn.close()

# --- 6. ENDPOINT: DANH SÁCH DỊCH VỤ ---
@app.route('/api/services', methods=['GET'])
def get_services_api():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT * FROM DICHVU")
        services = []
        for row in cursor.fetchall():
            d = dict(row)
            path = clean_image_path(d.get('HinhAnh'))
            d['HinhAnh'] = f"/images/{path}"
            services.append(d)
        return jsonify({"status": "success", "data": services})
    finally:
        conn.close()

# --- 7. ENDPOINT: CHI TIẾT DỊCH VỤ ---
@app.route('/api/service_detail/<ma_dv>', methods=['GET'])
def get_service_detail(ma_dv):
    conn = get_db()
    try:
        sv = conn.execute("SELECT * FROM DICHVU WHERE MaDV = ?", (ma_dv,)).fetchone()
        if sv:
            d = dict(sv)
            path = clean_image_path(d.get('HinhAnh'))
            d['HinhAnh'] = f"/images/{path}"
            return jsonify({"status": "success", "data": d})
        return jsonify({"status": "error", "message": "Dịch vụ không tồn tại"}), 404
    finally:
        conn.close()


# --- ENDPOINT: LƯU ĐƠN ĐẶT PHÒNG ---
@app.route('/api/save_booking', methods=['POST'])
def save_booking():
    data = request.get_json()
    ma_kh = data.get('ma_kh')
    cart_items = data.get('cart')
    payment = data.get('payment', 'Tiền mặt')

    if not ma_kh or not cart_items:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"}), 400

    conn = get_db()
    try:
        # 1. Tính tổng tiền toàn bộ đơn
        tong_tien = 0
        for item in cart_items:
            tong_tien += int(item.get('GiaTien', 0))
            for sv in item.get('services', []):
                tong_tien += int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))

        # 2. Chèn vào bảng DATPHONG
        cursor = conn.execute(
            "INSERT INTO DATPHONG (MaKH, TongTien, ThanhToan, TrangThai) VALUES (?, ?, ?, 'Chờ xác nhận')",
            (ma_kh, tong_tien, payment)
        )
        ma_dp = cursor.lastrowid

        # 3. Chèn vào bảng CHITIET_DATPHONG
        for item in cart_items:
            # Ép kiểu ngày tháng nếu cần
            cursor = conn.execute(
                """INSERT INTO CHITIET_DATPHONG (MaDP, MaLoai, GiaPhong, SoNguoi, NgayNhan, NgayTra) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ma_dp, item['MaLoai'], item['GiaTien'], item.get('SoNguoiToiDa', 2), item['checkin'], item['checkout'])
            )
            ma_ctdp = cursor.lastrowid

            # 4. Chèn dịch vụ đi kèm (nếu có)
            for sv in item.get('services', []):
                conn.execute(
                    "INSERT INTO DATPHONG_DICHVU (MaCTDP, MaDV, DonGia, SoLuong) VALUES (?, ?, ?, ?)",
                    (ma_ctdp, sv['MaDV'], sv['GiaTien'], sv['SoLuong'])
                )

        conn.commit()
        return jsonify({"status": "success", "ma_dp": ma_dp})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- ENDPOINT: LẤY LỊCH SỬ CHO KHÁCH ---
@app.route('/api/history/<int:ma_kh>', methods=['GET'])
def get_history(ma_kh):
    conn = get_db()
    try:
        # TẦNG 1: Lấy các đơn hàng tổng (DATPHONG)
        cursor = conn.execute("SELECT * FROM DATPHONG WHERE MaKH = ? ORDER BY NgayTao DESC", (ma_kh,))
        list_dp = [dict(row) for row in cursor.fetchall()]

        for dp in list_dp:
            # TẦNG 2: Lấy chi tiết từng phòng trong đơn đó (CHITIET_DATPHONG)
            query_ct = """
                SELECT ct.*, lp.TenLoai, p.SoPhong 
                FROM CHITIET_DATPHONG ct
                JOIN LOAIPHONG lp ON ct.MaLoai = lp.MaLoai
                LEFT JOIN PHONG p ON ct.MaPhong = p.MaPhong
                WHERE ct.MaDP = ?
            """
            cursor_ct = conn.execute(query_ct, (dp['MaDP'],))
            list_ct = [dict(row) for row in cursor_ct.fetchall()]

            for ct in list_ct:
                # TẦNG 3: Lấy các dịch vụ đi kèm từng phòng (DATPHONG_DICHVU)
                query_dv = """
                    SELECT dv.*, d.TenDV 
                    FROM DATPHONG_DICHVU dv
                    JOIN DICHVU d ON dv.MaDV = d.MaDV
                    WHERE dv.MaCTDP = ?
                """
                cursor_dv = conn.execute(query_dv, (ct['MaCTDP'],))
                ct['DanhSachDichVu'] = [dict(row) for row in cursor_dv.fetchall()]

            # Đút hết vào cái biến mà HTML của mày đang chờ sẵn
            dp['DanhSachChiTiet'] = list_ct

        return jsonify({"status": "success", "data": list_dp})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# --- ENDPOINT: HỦY ĐƠN ĐẶT PHÒNG ---
@app.route('/api/cancel_booking/<int:ma_dp>', methods=['POST'])
def cancel_booking(ma_dp):
    conn = get_db()
    try:
        # Kiểm tra xem đơn có đang ở trạng thái cho phép hủy không (Chờ xác nhận)
        query_check = "SELECT TrangThai FROM DATPHONG WHERE MaDP = ?"
        row = conn.execute(query_check, (ma_dp,)).fetchone()

        if row and row['TrangThai'] == 'Chờ xác nhận':
            # Cập nhật trạng thái đơn tổng
            conn.execute("UPDATE DATPHONG SET TrangThai = 'Đã hủy' WHERE MaDP = ?", (ma_dp,))
            # Cập nhật trạng thái các phòng trong đơn đó
            conn.execute("UPDATE CHITIET_DATPHONG SET TrangThai = 'Đã hủy' WHERE MaDP = ?", (ma_dp,))
            conn.commit()
            return jsonify({"status": "success", "message": "Đã hủy đơn thành công"})
        else:
            return jsonify(
                {"status": "error", "message": "Đơn này không thể hủy (Đã xác nhận hoặc đã thanh toán)"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    # Chạy trên cổng 5000 để phục vụ các yêu cầu từ customer.py và admin.py
    app.run(debug=True, port=5000)