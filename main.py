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
        response = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if response.status_code == 200:
            top_rooms = response.json().get('data', [])

            # --- ĐOẠN CHỈNH SỬA Ở ĐÂY ---
            for r in top_rooms:
                path = r.get('HinhAnhDaiDien')
                if path and not path.startswith('http'):
                    # 1. Dọn sạch dấu gạch chéo ở đầu path (ví dụ: /images/... thành images/...)
                    clean_path = path.lstrip('/')

                    # 2. Kiểm tra xem trong path đã có chữ 'static/' chưa
                    # Nếu chưa có (vì DB chỉ lưu images/...) thì ta tự thêm vào
                    if not clean_path.startswith('static/'):
                        final_path = f"static/{clean_path}"
                    else:
                        final_path = clean_path

                    # 3. Nối với BASE_URL (cổng 5000)
                    r['HinhAnhDaiDien'] = f"{BASE_URL}/{final_path}"

            print(f"--- Da lay va fix duong dan cho {len(top_rooms)} phong ---")
            if top_rooms:
                # Dùng print không dấu để tránh lỗi OSError 22 trên Windows dcm mày
                print(f"DEBUG PATH TRANG CHU: {top_rooms[0]['HinhAnhDaiDien']}")

    except Exception as e:
        print(f"Loi goi API trang chu: {e}")

    # --- PHẦN PHÂN QUYỀN GIỮ NGUYÊN ---
    if 'current_user' in session:
        user = session['current_user']
        if user.get('ChucVu') == 'nhanvien':
            return redirect(url_for('dashboard_admin'))
        return render_template('customer/index.html', top_rooms=top_rooms)

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
    session.pop('cart', None) # Xóa giỏ hàng
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
    app.run(debug=True, port=5001, use_reloader=True)