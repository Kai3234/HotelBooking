import requests
from flask import session, redirect, render_template, request, url_for
from main import app

# Cấu hình URL của API Server (Cổng 5000)
BASE_URL = "http://127.0.0.1:5000"


@app.route('/')
def index():
    rooms = []
    try:
        response = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if response.status_code == 200:
            rooms = response.json().get('data', [])
            for r in rooms:
                if r.get('HinhAnhDaiDien') and not r['HinhAnhDaiDien'].startswith('http'):
                    r['HinhAnhDaiDien'] = f"{BASE_URL}{r['HinhAnhDaiDien']}"
    except Exception as e:
        print(f"Lỗi kết nối API Trang chủ: {e}")
    return render_template('customer/index.html', top_rooms=rooms)


@app.route('/rooms_list')
def rooms_list():
    rooms = []
    checkin = request.args.get('checkin', '')
    checkout = request.args.get('checkout', '')
    try:
        params = {'checkin': checkin, 'checkout': checkout}
        response = requests.get(f"{BASE_URL}/api/search_rooms", params=params, timeout=5)
        if response.status_code == 200:
            rooms = response.json().get('data', [])
            for r in rooms:
                if r.get('HinhAnhDaiDien') and not r['HinhAnhDaiDien'].startswith('http'):
                    r['HinhAnhDaiDien'] = f"{BASE_URL}{r['HinhAnhDaiDien']}"
    except Exception as e:
        print(f"Lỗi kết nối API Danh sách phòng: {e}")
    return render_template('customer/rooms_list.html', loaiphong_list=rooms)


@app.route('/rooms_detail/<ma_loai>')
def room_detail(ma_loai):
    room_data = None
    try:
        response = requests.get(f"{BASE_URL}/api/room/{ma_loai}", timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                room_data = result.get('data')
                images = result.get('images', [])
                if room_data.get('HinhAnhDaiDien'):
                    room_data['HinhAnhDaiDien'] = f"{BASE_URL}{room_data['HinhAnhDaiDien']}"
                for img in images:
                    if not img['HinhAnh'].startswith('http'):
                        img['HinhAnh'] = f"{BASE_URL}{img['HinhAnh']}"
                room_data['DanhSachAnh'] = images
    except Exception as e:
        print(f"Lỗi kết nối API Chi tiết phòng: {e}")
    if room_data is None:
        return "<h1>Lỗi: Không tìm thấy phòng!</h1>", 404
    return render_template('customer/rooms_detail.html', room=room_data)


@app.route('/services')
def services():
    dichvu = []
    try:
        response = requests.get(f"{BASE_URL}/api/services", timeout=5)
        if response.status_code == 200:
            dichvu = response.json().get('data', [])
            for sv in dichvu:
                if sv.get('HinhAnh') and not sv['HinhAnh'].startswith('http'):
                    sv['HinhAnh'] = f"{BASE_URL}/images/{sv['HinhAnh']}"
    except Exception as e:
        print(f"Lỗi dịch vụ: {e}")
    return render_template('customer/services.html', dichvu_list=dichvu)


@app.route('/cart')
def cart_view():
    cart_items = session.get('cart', [])
    tong_tien_phong = sum(int(item.get('GiaTien', 0)) for item in cart_items)
    tong_tien_dichvu = 0
    for item in cart_items:
        for sv in item.get('services', []):
            tong_tien_dichvu += int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))
    return render_template('customer/cart.html', cart_items=cart_items, tong_tien_phong=tong_tien_phong,
                           tong_tien_dichvu=tong_tien_dichvu)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    ma_loai = request.form.get('ma_loai')
    checkin = request.form.get('checkin') or "Chưa chọn"
    checkout = request.form.get('checkout') or "Chưa chọn"
    if 'cart' not in session: session['cart'] = []
    try:
        response = requests.get(f"{BASE_URL}/api/room/{ma_loai}", timeout=5)
        if response.status_code == 200:
            room_data = response.json().get('data')
            if room_data.get('HinhAnhDaiDien') and not room_data['HinhAnhDaiDien'].startswith('http'):
                room_data['HinhAnhDaiDien'] = f"{BASE_URL}{room_data['HinhAnhDaiDien']}"
            room_data.update({'checkin': checkin, 'checkout': checkout, 'services': []})
            session['cart'].append(room_data)
            session.modified = True
    except Exception as e:
        print(f"Lỗi thêm giỏ hàng: {e}")
    return redirect(url_for('cart_view'))


@app.route('/checkout')
def checkout():
    if 'current_user' not in session: return redirect(url_for('login'))
    cart_items = session.get('cart', [])
    if not cart_items: return redirect(url_for('index'))

    tong_cong = 0
    for item in cart_items:
        tong_cong += int(item.get('GiaTien', 0))
        for sv in item.get('services', []):
            tong_cong += int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))
    return render_template('customer/checkout.html', cart_items=cart_items, tong_cong=tong_cong)


@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    if 'cart' not in session or not session['cart']: return redirect(url_for('index'))
    if 'current_user' not in session: return redirect(url_for('login'))

    booking_data = {
        "ma_kh": session['current_user']['MaTK'],
        "cart": session['cart'],
        "payment": request.form.get('payment_method', 'Tiền mặt')
    }
    try:
        response = requests.post(f"{BASE_URL}/api/save_booking", json=booking_data, timeout=10)
        if response.status_code == 200 and response.json().get('status') == 'success':
            session.pop('cart', None)
            session.modified = True
            return render_template('customer/booking_success.html')
    except Exception as e:
        print(f"Lỗi confirm: {e}")
    return "Lỗi hệ thống lưu đơn!", 500


@app.route('/history')
def history():
    if 'current_user' not in session: return redirect(url_for('login'))
    lich_su = []
    try:
        ma_kh = session['current_user']['MaTK']
        response = requests.get(f"{BASE_URL}/api/history/{ma_kh}", timeout=5)
        if response.status_code == 200:
            lich_su = response.json().get('data', [])
    except Exception as e:
        print(f"Lỗi lấy lịch sử: {e}")
    return render_template('customer/history.html', lich_su_dat=lich_su)


@app.route('/profile')
def profile():
    if 'current_user' not in session: return redirect(url_for('login'))
    return render_template('customer/profile.html')


@app.route('/add_service_to_cart', methods=['POST'])
def add_service_to_cart():
    if 'cart' not in session: return redirect(url_for('rooms_list'))
    item_index = int(request.form.get('item_index', 0))
    ma_dv = request.form.get('ma_dv')
    so_luong = int(request.form.get('so_luong', 1))
    try:
        response = requests.get(f"{BASE_URL}/api/service_detail/{ma_dv}", timeout=5)
        if response.status_code == 200:
            sv_data = response.json().get('data')
            sv_data['SoLuong'] = so_luong
            if 0 <= item_index < len(session['cart']):
                session['cart'][item_index]['services'].append(sv_data)
                session.modified = True
    except Exception as e:
        print(f"Service Error: {e}")
    return redirect(url_for('cart_view'))


@app.route('/cancel_booking', methods=['POST'])
def cancel_booking_route():
    if 'current_user' not in session: return redirect(url_for('login'))

    # Lấy ma_dp từ form hidden của mày
    ma_dp = request.form.get('ma_dp')
    if not ma_dp: return redirect(url_for('history'))

    try:
        # Gọi sang API hủy đơn
        res = requests.post(f"{BASE_URL}/api/cancel_booking/{ma_dp}", timeout=5)
        if res.status_code == 200:
            print(f"--- Đã hủy đơn {ma_dp} thành công ---")
    except Exception as e:
        print(f"Lỗi khi hủy: {e}")

    return redirect(url_for('history'))