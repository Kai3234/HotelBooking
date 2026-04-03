import requests
from flask import session, redirect, render_template, request, url_for, flash
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
                # DB đã có 'static/images/...', chỉ cần nối BASE_URL và dấu /
                if r.get('HinhAnhDaiDien') and not r['HinhAnhDaiDien'].startswith('http'):
                    r['HinhAnhDaiDien'] = f"{BASE_URL}/{r['HinhAnhDaiDien']}"
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
                    r['HinhAnhDaiDien'] = f"{BASE_URL}/{r['HinhAnhDaiDien']}"
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
                # Sửa đường dẫn ảnh chính
                if room_data.get('HinhAnhDaiDien') and not room_data['HinhAnhDaiDien'].startswith('http'):
                    room_data['HinhAnhDaiDien'] = f"{BASE_URL}/{room_data['HinhAnhDaiDien']}"
                # Sửa danh sách ảnh con
                for img in images:
                    if not img['HinhAnh'].startswith('http'):
                        img['HinhAnh'] = f"{BASE_URL}/{img['HinhAnh']}"
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
                # XÓA BỎ đoạn cộng thêm '/images/'. Để DB tự lo.
                if sv.get('HinhAnh') and not sv['HinhAnh'].startswith('http'):
                    sv['HinhAnh'] = f"{BASE_URL}/{sv['HinhAnh']}"
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

    if 'cart' not in session:
        session['cart'] = []

    try:
        response = requests.get(f"{BASE_URL}/api/room/{ma_loai}", timeout=5)
        if response.status_code == 200:
            room_data = response.json().get('data')

            # --- FIX ĐƯỜNG DẪN ẢNH TRIỆT ĐỂ ---
            path = room_data.get('HinhAnhDaiDien')
            if path and not path.startswith('http'):
                # Xóa dấu / ở đầu path nếu có để nối chuỗi không bị lỗi //
                clean_path = path.lstrip('/')
                room_data['HinhAnhDaiDien'] = f"{BASE_URL}/{clean_path}"

            room_data.update({'checkin': checkin, 'checkout': checkout, 'services': []})
            session['cart'].append(room_data)
            session.modified = True

    except Exception as e:
        print(f"Lỗi thêm giỏ hàng: {e}")

    return redirect(url_for('cart_view'))


@app.route('/checkout')
def checkout():
    if 'current_user' not in session:
        return redirect(url_for('login'))

    cart_items = session.get('cart', [])

    # --- QUAN TRỌNG: Sửa 'index' thành 'main_index' ---
    if not cart_items:
        return redirect(url_for('main_index'))

    tong_cong = 0
    for item in cart_items:
        # Ép kiểu int để tính toán không bị lỗi chuỗi
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
    if 'current_user' not in session:
        return redirect(url_for('login'))

    ma_kh = session['current_user']['MaTK']
    print(f"--- Đang lấy lịch sử cho MaKH: {ma_kh} ---")  # DEBUG DÒNG NÀY

    lich_su = []
    try:
        response = requests.get(f"{BASE_URL}/api/history/{ma_kh}", timeout=5)
        print(f"API Response Status: {response.status_code}")  # DEBUG DÒNG NÀY

        if response.status_code == 200:
            lich_su = response.json().get('data', [])
            print(f"Số lượng đơn hàng tìm thấy: {len(lich_su)}")  # DEBUG DÒNG NÀY

            # (Phần ép URL ảnh giữ nguyên như tao dạy lúc nãy)
            for dp in lich_su:
                for ct in dp.get('DanhSachChiTiet', []):
                    path = ct.get('HinhAnh') or ct.get('HinhAnhDaiDien')
                    ct['HinhAnhHienThi'] = f"{BASE_URL}/{path.lstrip('/')}" if path else ""

    except Exception as e:
        print(f"Lỗi kết nối API History: {e}")

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
    ma_dp = request.form.get('ma_dp')
    if not ma_dp: return redirect(url_for('history'))
    try:
        res = requests.post(f"{BASE_URL}/api/cancel_booking/{ma_dp}", timeout=5)
        if res.status_code == 200:
            print(f"--- Đã hủy đơn {ma_dp} thành công ---")
    except Exception as e:
        print(f"Lỗi khi hủy: {e}")
    return redirect(url_for('history'))


@app.route('/remove_from_cart/<int:index>')
def remove_from_cart(index):
    # Lấy giỏ hàng từ session
    cart = session.get('cart', [])

    # Kiểm tra xem cái chỉ số index có hợp lệ không
    if 0 <= index < len(cart):
        # Xóa thằng tại vị trí index
        removed_item = cart.pop(index)
        session['cart'] = cart
        session.modified = True
        flash(f"Đã gỡ bỏ phòng {removed_item.get('TenLoai')} khỏi giỏ hàng!", "info")

    return redirect(url_for('cart_view'))