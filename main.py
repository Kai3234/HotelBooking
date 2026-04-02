import os
import requests


from flask import Flask, render_template, request, redirect, flash, url_for, session, get_flashed_messages, \
    send_from_directory

#ĐOẠN NÀY: Để Flask mặc định lấy CSS ở thư mục 'static'
app = Flask(__name__)

# Set the secret key for flash messages
app.secret_key = 'FelixPham'

BASE_URL = 'http://127.0.0.1:5000'

# Route này là "cứu cánh" để lấy ảnh từ thư mục images nằm ngoài static
@app.route('/images/<path:filename>')
def serve_images(filename):
    # Đường dẫn trỏ thẳng vào thư mục 'images' ngang hàng với main.py
    image_path = os.path.join(app.root_path, 'images')
    return send_from_directory(image_path, filename)

@app.route('/')
def main_index():
    get_flashed_messages()

    top_rooms = []
    try:
        # Gọi sang API cổng 5000 để lấy dữ liệu
        response = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if response.status_code == 200:
            top_rooms = response.json().get('data', [])
            print(f"--- Đã lấy được {len(top_rooms)} phòng cho Trang Chủ ---")
    except Exception as e:
        print(f"Lỗi gọi API trang chủ: {e}")
    # ----------------------------------------------

    if 'current_user' in session:
        user = session['current_user']
        if user['ChucVu'] == 'nhanvien':
            if user.get('LaAdmin') == 1:
                return redirect(url_for('dashboard_admin'))
            return redirect(url_for('dashboard_admin'))
        # Truyền biến top_rooms vào đây
        return render_template('customer/index.html', top_rooms=top_rooms)

    # Truyền biến top_rooms vào đây cho khách vãng lai
    return render_template('customer/index.html', top_rooms=top_rooms)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Kiểm tra nếu đã đăng nhập thì đẩy về trang tương ứng
    if 'current_user' in session:
        if session['current_user']['ChucVu'] == 'nhanvien':
            return redirect(url_for('backend_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # value từ HTML form là 'khachhang' hoặc 'nhanvien'

        # Đóng gói dữ liệu gửi lên API
        payload = {
            "email": email,
            "password": password,
            "role": role
        }

        try:
            # GỌI API ĐĂNG NHẬP (Gửi request dạng POST chứa JSON)
            response = requests.post(f"{BASE_URL}/login", json=payload)

            # Phân tích kết quả trả về từ API
            if response.status_code == 200:
                result = response.json()

                # Giả sử API trả về JSON dạng:
                # {"status": "success", "data": {"MaTK": 1, "HoTen": "Nguyễn Văn A", "LaAdmin": 0}}
                if result.get('status') == 'success':
                    user_data = result['data']

                    # -----------------------------------------------------
                    # KHỞI TẠO SESSION THEO ĐÚNG CẤU TRÚC YÊU CẦU
                    # -----------------------------------------------------
                    session['current_user'] = {
                        'MaTK': user_data['MaTK'],
                        'HoTen': user_data['HoTen'],
                        'ChucVu': 'nhanvien' if role == 'nhanvien' else 'khach',
                        'LaAdmin': user_data.get('LaAdmin', 0)  # Khách hàng mặc định không có thì lấy 0
                    }

                    flash('Đăng nhập thành công!', 'success')

                    # Điều hướng dựa trên Chức vụ
                    if session['current_user']['ChucVu'] == 'nhanvien':
                        return redirect(url_for('backend_dashboard'))
                    else:
                        return redirect(url_for('index'))
                else:
                    # Nếu API trả về status fail kèm câu thông báo lỗi
                    flash(result.get('message', 'Email hoặc mật khẩu không đúng!'), 'danger')
            else:
                flash('Có lỗi xảy ra từ phía API server!', 'danger')

        except requests.exceptions.RequestException as e:
            # Lỗi khi không thể kết nối tới project API (VD: Project kia chưa bật)
            flash('Lỗi kết nối đến máy chủ API! Vui lòng kiểm tra lại.', 'danger')
            print("Lỗi API:", e)

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Kiểm tra nếu đã đăng nhập thì đẩy về trang tương ứng
    if 'current_user' in session:
        if session['current_user']['ChucVu'] == 'nhanvien':
            return redirect(url_for('backend_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Lấy dữ liệu từ form HTML
        payload = {
            "fullname": request.form.get('fullname'),
            "email": request.form.get('email'),
            "phone": request.form.get('phone'),
            "password": request.form.get('password')
        }

        # Gửi yêu cầu đến Backend API
        try:
            response = requests.post(f"{BASE_URL}/register", json=payload)
            result = response.json()

            if result['status'] == 'success':
                flash(result['message'], 'success')
                return redirect(url_for('login')) # Chuyển hướng sang đăng nhập
            else:
                flash(result['message'], 'danger')
        except Exception:
            flash("Không thể kết nối đến hệ thống máy chủ API!", "danger")

    return render_template('auth/register.html')

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
            return redirect(url_for('dashboard_admin'))
        return redirect(url_for('dashboard_rec'))
    return redirect(url_for('index'))

@app.route('/mockup/admin')
def mockup_admin():
    return render_template('mockup/base_backend_mockup.html')


@app.route('/mockup/customer')
def mockup_dashboard():
    return render_template('mockup/index_mockup.html')

# Import tất cả các hàm, biến và route
from admin import *
from receptionist import *
from customer import *




if __name__ == '__main__':
    #Đặt cổng khác bởi vì 5000 đã được sử dụng
    app.run(debug=True, port=5001, use_reloader=False)