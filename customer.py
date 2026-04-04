import requests
from flask import session, redirect, render_template, request, url_for, flash
from main import app, BASE_URL
from datetime import datetime

def calculate_days(checkin_str, checkout_str):
    try:
        try:
            ci = datetime.strptime(checkin_str, '%d/%m/%Y')
            co = datetime.strptime(checkout_str, '%d/%m/%Y')
        except ValueError:
            ci = datetime.strptime(checkin_str, '%Y-%m-%d')
            co = datetime.strptime(checkout_str, '%Y-%m-%d')
        days = (co - ci).days
        return days if days > 0 else 1
    except Exception:
        return 1


# --- HÀM HỖ TRỢ: Fix đường dẫn ảnh để luôn có /static/ ---
def fix_image_url(path):
    if not path:
        return f"{BASE_URL}/static/images/default_room.jpg"
    if path.startswith('http'):
        return path

    clean_path = path.lstrip('/')
    # Nếu DB/API trả về images/... thì ta thêm static/
    if not clean_path.startswith('static/'):
        return f"{BASE_URL}/static/{clean_path}"
    return f"{BASE_URL}/{clean_path}"


@app.route('/')
def index():
    rooms = []
    try:
        response = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if response.status_code == 200:
            rooms = response.json().get('data', [])
            for r in rooms:
                r['HinhAnhDaiDien'] = fix_image_url(r.get('HinhAnhDaiDien'))
    except Exception as e:
        print(f"Loi goi API Trang chu: {e}")
    return render_template('customer/index.html', top_rooms=rooms)

@app.route('/rooms_list')
def rooms_list():
    rooms = []
    all_types = []
    # Bổ sung: lấy thêm các field lọc từ file HTML (max_price, room_type, adults, children)
    max_price = request.args.get('max_price', 10000000)
    room_type = request.args.get('room_type', '')
    
    try:
        adults = int(request.args.get('adults', 1))
        children = int(request.args.get('children', 0))
        total_guests = adults + children
    except:
        total_guests = 1
        
    search_params = {
        'max_price': max_price,
        'room_type': room_type,
        'guests': total_guests,
        'checkin': request.args.get('checkin', '').strip(),
        'checkout': request.args.get('checkout', '').strip()
    }

    try:
        # Lấy danh sách loại phòng cho Dropdown menu
        res_types = requests.get(f"{BASE_URL}/api/all_room_types", timeout=5)
        if res_types.status_code == 200:
            all_types = res_types.json().get('data', [])

        response = requests.get(f"{BASE_URL}/api/search_rooms", params=search_params, timeout=5)
        if response.status_code == 200:
            rooms = response.json().get('data', [])
            for r in rooms:
                r['HinhAnhDaiDien'] = fix_image_url(r.get('HinhAnhDaiDien'))
    except Exception as e:
        print(f"Loi goi API Danh sach phong: {e}")
    return render_template('customer/rooms_list.html', loaiphong_list=rooms, all_types=all_types)


@app.route('/rooms_detail/<ma_loai>')
def room_detail(ma_loai):
    room_data = None
    top_rooms = []  # Thêm cái này để chứa phòng gợi ý
    try:
        # 1. Lấy chi tiết phòng
        response = requests.get(f"{BASE_URL}/api/room/{ma_loai}", timeout=5)
        if response.status_code == 200:
            result = response.json()
            room_data = result.get('data')

            # Cập nhật: API trả về gallery list trong ruột `room_data['DanhSachAnh']` chứ không nằm ngoài root tên `images`
            gallery = room_data.get('DanhSachAnh', []) if room_data else []

            if room_data:
                # Fix ảnh chính
                room_data['HinhAnhDaiDien'] = fix_image_url(room_data.get('HinhAnhDaiDien'))

                # Fix ảnh trong gallery
                for img in gallery:
                    img['HinhAnh'] = fix_image_url(img.get('HinhAnh'))

                # Đút lại vào room_data để HTML bốc ra được
                room_data['DanhSachAnh'] = gallery

        # 2. Lấy thêm top_rooms để hiện ở phần "Các lựa chọn khác" dưới đáy trang
        res_top = requests.get(f"{BASE_URL}/api/top_rooms", timeout=5)
        if res_top.status_code == 200:
            top_rooms = res_top.json().get('data', [])
            for r in top_rooms:
                r['HinhAnhDaiDien'] = fix_image_url(r.get('HinhAnhDaiDien'))

    except Exception as e:
        print(f"Loi goi API Chi tiet phong: {e}")

    if not room_data:
        return "<h1>Khong tim thay phong!</h1>", 404

    # Nhớ truyền cả top_rooms vào đây
    return render_template('customer/rooms_detail.html', room=room_data, top_rooms=top_rooms)


@app.route('/services')
def services():
    dichvu = []
    try:
        response = requests.get(f"{BASE_URL}/api/services", timeout=5)
        if response.status_code == 200:
            dichvu = response.json().get('data', [])
            for sv in dichvu:
                path = sv.get('HinhAnh')
                if path and not path.startswith('http'):
                    # 1. Dọn dẹp dấu gạch chéo thừa ở đầu
                    clean_path = path.lstrip('/')

                    # 2. Kiểm tra nếu trong path chưa có 'static/' thì tự thêm vào
                    if not clean_path.startswith('static/'):
                        final_path = f"static/{clean_path}"
                    else:
                        final_path = clean_path

                    # 3. Nối với BASE_URL (cổng 5000)
                    sv['HinhAnh'] = f"{BASE_URL}/{final_path}"

    except Exception as e:
        # Dùng print không dấu để tránh lỗi OSError 22 trên Windows
        print(f"Loi dich vu: {e}")

    return render_template('customer/services.html', dichvu_list=dichvu)

@app.route('/cart')
def cart_view():
    if 'current_user' not in session:
        return redirect(url_for('login'))

    cart_items = session.get('cart', [])
    tong_tien_phong = 0
    tong_tien_dichvu = 0
    for item in cart_items:
        days = calculate_days(item.get('checkin', ''), item.get('checkout', ''))
        item['so_ngay'] = days
        tong_tien_phong += int(item.get('GiaTien', 0)) * days
        for sv in item.get('services', []):
            cost = int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))
            if sv.get('TinhTheoNgay') == 1:
                cost *= days
            tong_tien_dichvu += cost
    return render_template('customer/cart.html', cart_items=cart_items, tong_tien_phong=tong_tien_phong,
                           tong_tien_dichvu=tong_tien_dichvu)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'current_user' not in session:
        return redirect(url_for('login'))

    ma_loai = request.form.get('ma_loai')
    checkin = request.form.get('checkin', '').strip()
    checkout = request.form.get('checkout', '').strip()
    action_type = request.form.get('action_type', '')

    if not checkin or not checkout or checkin == "Chua chon" or checkout == "Chua chon":
        flash("Lỗi hệ thống: Bắt buộc chọn Ngày Nhận Phòng và Ngày Trả Phòng!", "danger")
        return redirect(request.referrer or url_for('rooms_list'))

    try:
        try:
            ci_date = datetime.strptime(checkin, '%d/%m/%Y')
            co_date = datetime.strptime(checkout, '%d/%m/%Y')
        except ValueError:
            ci_date = datetime.strptime(checkin, '%Y-%m-%d')
            co_date = datetime.strptime(checkout, '%Y-%m-%d')
        
        if (co_date - ci_date).days < 1:
            flash("Lỗi: Ngày trả phòng phải sau ngày nhận phòng ít nhất 1 ngày!", "danger")
            return redirect(request.referrer or url_for('rooms_list'))

        try:
            # Gọi API search để kiểm tra xem với ngày này thì MaLoai này còn phòng thực tế không
            params = {
                'room_type': ma_loai,
                'checkin': ci_date.strftime('%d/%m/%Y'),
                'checkout': co_date.strftime('%d/%m/%Y')
            }
            check_res = requests.get(f"{BASE_URL}/api/search_rooms", params=params, timeout=5)
            if check_res.status_code == 200:
                data = check_res.json().get('data', [])
                # Nếu mảng data rỗng tức là loại phòng này đã hết phòng trống (theo logic SQL ở api.py)
                if not any(str(r['MaLoai']) == str(ma_loai) for r in data):
                    flash("Rất tiếc, loại phòng này đã hết phòng trống trong khoảng thời gian bạn chọn!", "danger")
                    return redirect(request.referrer or url_for('rooms_list'))
        except Exception as e:
            print(f"Lỗi check trống: {e}")

    except Exception:
        flash("Lỗi định dạng ngày không hợp lệ!", "danger")
        return redirect(request.referrer or url_for('rooms_list'))

    if 'cart' not in session: session['cart'] = []
    try:
        response = requests.get(f"{BASE_URL}/api/room/{ma_loai}", timeout=5)
        if response.status_code == 200:
            room_data = response.json().get('data')
            # Phải fix ảnh ngay khi bỏ vào giỏ hàng dcm mày
            room_data['HinhAnhDaiDien'] = fix_image_url(room_data.get('HinhAnhDaiDien'))
            room_data.update({'checkin': checkin, 'checkout': checkout, 'services': []})
            session['cart'].append(room_data)
            session.modified = True

            if action_type == 'add_only':
                flash(f"Thành công! Đã thêm {room_data.get('TenLoai', 'phòng')} vào giỏ hàng.", "success")
                return redirect(request.referrer or url_for('rooms_list'))

    except Exception as e:
        print(f"Loi them gio hang: {e}")
    return redirect(url_for('cart_view'))

@app.route('/checkout')
def checkout():
    if 'current_user' not in session:
        return redirect(url_for('login'))

    cart_items = session.get('cart', [])

    # --- Cập nhật: Đã sửa 'main_index' về lại 'index' do bị ghi đè route ---
    if not cart_items:
        return redirect(url_for('index'))

    tong_cong = 0
    tong_phong = 0
    tong_dichvu = 0
    for item in cart_items:
        days = calculate_days(item.get('checkin', ''), item.get('checkout', ''))
        item['so_ngay'] = days
        tong_phong += int(item.get('GiaTien', 0)) * days
        for sv in item.get('services', []):
            cost = int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))
            if sv.get('TinhTheoNgay') == 1:
                cost *= days
            tong_dichvu += cost
    tong_cong += tong_phong + tong_dichvu

    return render_template('customer/checkout.html', cart_items=cart_items, tong_cong=tong_cong, tong_phong=tong_phong, tong_dichvu=tong_dichvu)


@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('index'))  # Đổi main_index thành index cho chắc
    if 'current_user' not in session:
        return redirect(url_for('login'))

    # TÍNH TỔNG TIỀN (BAO GỒM TIỀN PHÒNG * SỐ NGÀY + DỊCH VỤ)
    tong_cong = 0
    for item in session['cart']:
        days = calculate_days(item.get('checkin', ''), item.get('checkout', ''))
        item['so_ngay'] = days
        tong_cong += int(item.get('GiaTien', 0)) * days
        for sv in item.get('services', []):
            cost = int(sv.get('GiaTien', 0)) * int(sv.get('SoLuong', 1))
            if sv.get('TinhTheoNgay') == 1:
                cost *= days
            tong_cong += cost

    # DEBUG: Kiểm tra xem MaTK có thực sự tồn tại không
    print(f"DEBUG: User session: {session['current_user']}")

    booking_data = {
        "ma_kh": session['current_user'].get('MaTK') or session['current_user'].get('MaKH'),
        "cart": session['cart'],
        "total_price": tong_cong,
        "payment": request.form.get('payment_method', 'Tien mat')
    }

    try:
        response = requests.post(f"{BASE_URL}/api/save_booking", json=booking_data, timeout=10)
        result = response.json()
        if response.status_code == 200 and result.get('status') == 'success':
            session.pop('cart', None)
            session.modified = True
            return render_template('customer/booking_success.html')
        else:
            print(f"Loi tu API: {result.get('message')}")
    except Exception as e:
        print(f"Loi confirm: {e}")

    return "Loi he thong luu don!", 500


@app.route('/history')
def history():
    if 'current_user' not in session:
        return redirect(url_for('login'))

    # Phải lấy đúng ID, tao dùng .get cho chắc
    user = session['current_user']
    ma_kh = user.get('MaTK') or user.get('MaKH')

    print(f"DEBUG: Dang lay lich su cho MaKH = {ma_kh}")

    lich_su = []
    try:
        response = requests.get(f"{BASE_URL}/api/history/{ma_kh}", timeout=5)
        if response.status_code == 200:
            result = response.json()
            lich_su = result.get('data', [])

            # Fix ảnh cho từng chi tiết trong đơn hàng
            for dp in lich_su:
                for ct in dp.get('DanhSachChiTiet', []):
                    # Ưu tiên lấy HinhAnhHienThi từ API trả về
                    path = ct.get('HinhAnhHienThi') or ct.get('HinhAnhPath') or ct.get('HinhAnh')
                    ct['HinhAnhHienThi'] = fix_image_url(path)
    except Exception as e:
        print(f"Loi lay lich su: {e}")

    return render_template('customer/history.html', lich_su_dat=lich_su)

@app.route('/profile')
def profile():
    if 'current_user' not in session: return redirect(url_for('login'))
    return render_template('customer/profile.html')


@app.route('/add_service_to_cart', methods=['POST'])
def add_service_to_cart():
    if 'current_user' not in session: 
        return redirect(url_for('login'))

    if 'cart' not in session: return redirect(url_for('rooms_list'))

    item_index = int(request.form.get('item_index', 0))
    ma_dv = request.form.get('ma_dv')
    so_luong = int(request.form.get('so_luong', 1))
    gio_dat = request.form.get('gio_dat', '08:00:00')
    tinh_theo_ngay = int(request.form.get('tinh_theo_ngay', 0))

    try:
        # Gọi sang API lấy chi tiết dịch vụ (đảm bảo API trả về GiaTien, MaDV, TinhTheoNgay)
        response = requests.get(f"{BASE_URL}/api/service_detail/{ma_dv}", timeout=5)
        if response.status_code == 200:
            sv_data = response.json().get('data')

            # Gắn thêm thông tin khách vừa chọn
            sv_data['SoLuong'] = so_luong
            sv_data['gio_dat'] = gio_dat
            sv_data['TinhTheoNgay'] = tinh_theo_ngay

            if 0 <= item_index < len(session['cart']):
                session['cart'][item_index]['services'].append(sv_data)
                session.modified = True
                flash(f"Đã thêm {sv_data['TenDV']} vào phòng!", "success")
    except Exception as e:
        print(f"Loi add service: {e}")

    return redirect(request.referrer or url_for('services'))

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
    if 'current_user' not in session:
        return redirect(url_for('login'))

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

@app.route('/remove_service_from_cart/<int:room_index>/<int:service_index>')
def remove_service_from_cart(room_index, service_index):
    if 'current_user' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', [])
    if 0 <= room_index < len(cart):
        services = cart[room_index].get('services', [])
        if 0 <= service_index < len(services):
            removed_sv = services.pop(service_index)
            session.modified = True
            flash(f"Đã gỡ dịch vụ {removed_sv.get('TenDV')} khỏi phòng!", "info")

    return redirect(url_for('cart_view'))
