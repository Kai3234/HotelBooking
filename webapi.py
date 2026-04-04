# Import flask and sqlite3 modules
from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

sqldbname = 'db/website.db'

# Hàm kết nối tới Cơ sở dữ liệu SQLite
def get_db():
    conn = sqlite3.connect(sqldbname)
    conn.row_factory = sqlite3.Row # Giúp lấy dữ liệu dạng Dictionary thay vì Tuple
    return conn

@app.route('/login', methods=['POST'])
def login_api():
    # Lấy dữ liệu JSON được gửi từ Frontend (cổng 5001)
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu gửi lên không hợp lệ!"}), 400

    email= data.get('email')
    password = data.get('password')
    role = data.get('role')

    conn = get_db()

    # --- 1. XỬ LÝ CHO NHÂN VIÊN ---
    if role == 'nhanvien':
        # Lưu ý: Theo schema trước đó NHANVIEN đăng nhập bằng SDT.
        # Nếu bạn đã thêm cột Email vào NHANVIEN thì hãy đổi `SDT = ?` thành `Email = ?`
        query = "SELECT * FROM NHANVIEN WHERE Email = ? AND MatKhau = ?"
        user = conn.execute(query, (email, password)).fetchone()

        if user:
            conn.close()
            return jsonify({
                "status": "success",
                "data": {
                    "MaTK": user['MaNV'],
                    "HoTen": user['HoTen'],
                    "LaAdmin": user['LaAdmin']
                }
            })

    # --- 2. XỬ LÝ CHO KHÁCH HÀNG ---
    elif role == 'khachhang':
        query = "SELECT * FROM KHACHHANG WHERE Email = ? AND MatKhau = ?"
        user = conn.execute(query, (email, password)).fetchone()

        if user:
            conn.close()
            return jsonify({
                "status": "success",
                "data": {
                    "MaTK": user['MaKH'],
                    "HoTen": user['HoTen'],
                    "LaAdmin": 0 # Khách hàng không có quyền Admin
                }
            })

    conn.close()
    # Trả về lỗi nếu không tìm thấy User hoặc mật khẩu sai
    return jsonify({
        "status": "error",
        "message": "Thông tin đăng nhập hoặc mật khẩu không chính xác!"
    }), 200 # Frontend của bạn kiểm tra status_code == 200 để lấy JSON nên để 200


@app.route('/register', methods=['POST'])
def register_api():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu không hợp lệ"}), 400

    fullname = data.get('fullname')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')

    conn = get_db()
    try:
        # 1. Kiểm tra email đã tồn tại trong bảng KHACHHANG hay chưa
        check_user = conn.execute("SELECT * FROM KHACHHANG WHERE Email = ?", (email,)).fetchone()

        if check_user:
            return jsonify({
                "status": "error",
                "message": "Email này đã được sử dụng. Vui lòng chọn email khác!"
            }), 200  # Trả về 200 để Client dễ xử lý JSON message

        # 2. Thêm mới khách hàng
        conn.execute(
            "INSERT INTO KHACHHANG (HoTen, Email, SDT, MatKhau) VALUES (?, ?, ?, ?)",
            (fullname, email, phone, password)
        )
        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Đăng ký tài khoản thành công!"
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- 3. API DÀNH CHO KHÁCH HÀNG ---


@app.route('/api/service_detail/<int:ma_dv>', methods=['GET'])
def service_detail_customer_api(ma_dv):
    conn = get_db()
    svc = conn.execute("SELECT * FROM DICHVU WHERE MaDV = ?", (ma_dv,)).fetchone()
    conn.close()
    if svc:
        return jsonify({"status": "success", "data": dict(svc)})
    return jsonify({"status": "error", "message": "Không tìm thấy dịch vụ"}), 404

@app.route('/api/cancel_booking/<int:ma_dp>', methods=['POST'])
def cancel_booking_customer_api(ma_dp):
    conn = get_db()
    try:
        conn.execute("UPDATE DATPHONG SET TrangThai = 'Đã hủy' WHERE MaDP = ?", (ma_dp,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


from admin_api import *
from customer_api import *
from receptionist_api import *


if __name__ == '__main__':
    # Chạy API ở cổng 5000
    app.run(debug=True, port=5000)