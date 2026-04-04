import os
import requests


from flask import Flask, render_template, request, redirect, flash, url_for, session, get_flashed_messages, \
    send_from_directory

#ĐOẠN NÀY: Để Flask mặc định lấy CSS ở thư mục 'static'
app = Flask(__name__)

# Set the secret key for flash messages
app.secret_key = 'FelixPham'

BASE_URL = 'http://127.0.0.1:5000'


@app.route('/')
def main_index():
    get_flashed_messages()

    top_rooms = []
    try:
        # Gọi sang API cổng 5000 để lấy dữ liệu
        response = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if response.status_code == 200:
            top_rooms = response.json().get('data', [])

            # --- FIX ĐƯỜNG DẪN ẢNH (GIỮ NGUYÊN VÌ ĐÃ CHUẨN) ---
            for r in top_rooms:
                path = r.get('HinhAnhDaiDien')
                if path and not path.startswith('http'):
                    clean_path = path.lstrip('/')
                    # Đảm bảo có dấu / giữa BASE_URL và clean_path
                    r['HinhAnhDaiDien'] = f"{BASE_URL}/{clean_path}"

            print(f"--- Đã lấy và fix đường dẫn cho {len(top_rooms)} phòng ---")
            if top_rooms:
                print(f"DEBUG PATH TRANG CHU: {top_rooms[0]['HinhAnhDaiDien']}")

    except Exception as e:
        print(f"Lỗi gọi API trang chủ: {e}")

    # --- LOGIC PHÂN QUYỀN GỌN GÀNG ---
    if 'current_user' in session:
        user = session['current_user']
        # Nếu là nhân viên thì tống vào trang quản trị ngay và luôn
        if user.get('ChucVu') == 'nhanvien':
            # Phải chắc chắn có route tên dashboard_admin nhé dcm mày
            return redirect(url_for('dashboard_admin'))

        # Nếu là khách đã đăng nhập thì cho xem trang chủ
        return render_template('customer/index.html', top_rooms=top_rooms)

    # Cho khách vãng lai chưa đăng nhập
    return render_template('customer/index.html', top_rooms=top_rooms)

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = None
    category = None  # 'success' hoặc 'danger'

    if 'current_user' in session:
        if session['current_user']['ChucVu'] == 'nhanvien':
            return redirect(url_for('backend_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        payload = {"email": email, "password": password, "role": role}

        try:
            response = requests.post(f"{BASE_URL}/login", json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    user_data = result['data']
                    session['current_user'] = {
                        'MaTK': user_data['MaTK'],
                        'HoTen': user_data['HoTen'],
                        'ChucVu': 'nhanvien' if role == 'nhanvien' else 'khach',
                        'LaAdmin': user_data.get('LaAdmin', 0)
                    }
                    # Có thể set message thành success nếu muốn hiển thị ở login
                    message = "Đăng nhập thành công!"
                    category = "success"
                    return redirect(url_for('backend_dashboard') if role=='nhanvien' else url_for('index'))
                else:
                    message = result.get('message', 'Email hoặc mật khẩu không đúng!')
                    category = "danger"
            else:
                message = 'Có lỗi xảy ra từ phía API server!'
                category = "danger"

        except requests.exceptions.RequestException as e:
            message = 'Lỗi kết nối đến máy chủ API! Vui lòng kiểm tra lại.'
            category = "danger"
            print("Lỗi API:", e)

    return render_template('auth/login.html', message=message, category=category)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None
    alert_message = request.args.get('alert')  # Lấy từ query param nếu có

    if 'current_user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        payload = {
            "fullname": request.form.get('fullname'),
            "email": request.form.get('email'),
            "phone": request.form.get('phone'),
            "password": request.form.get('password')
        }

        try:
            response = requests.post(f"{BASE_URL}/register", json=payload)
            result = response.json()

            if result.get('status') == 'success':
                # Redirect chính page register kèm alert_message
                return redirect(url_for('register', alert="Đăng ký thành công! Vui lòng đăng nhập."))
            else:
                error_message = result.get('message', 'Có lỗi xảy ra!')
        except Exception:
            error_message = "Không thể kết nối đến hệ thống API!"

    return render_template('auth/register.html', error_message=error_message, alert_message=alert_message)

@app.route('/logout')
def logout():
    session.pop('current_user', None)  # Xóa dict current_user khỏi session
    return redirect(url_for('login'))


@app.route('/backend_dashboard')
def backend_dashboard():
    get_flashed_messages()
    if 'current_user' in session:
        if session['current_user']['ChucVu'] == 'nhanvien':
            if session['current_user']['LaAdmin'] == 1:
                return redirect(url_for('dashboard_admin'))
            return redirect(url_for('dashboard_rec'))
        return redirect(url_for('dashboard_rec'))
    return redirect(url_for('index'))

# Import tất cả các hàm, biến và route
from admin import *
from receptionist import *
from customer import *




if __name__ == '__main__':
    #Đặt cổng khác bởi vì 5000 đã được sử dụng
    app.run(debug=True, port=5001, use_reloader=False)