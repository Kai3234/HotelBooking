import sqlite3
from datetime import datetime, timedelta, date
import requests
from flask import session, redirect, render_template, request, flash, url_for, jsonify

from main import app

API_BASE_URL = 'http://127.0.0.1:5000/api/rec'


@app.route('/dashboard_rec')
def dashboard_rec():
    # 1. Lấy tham số từ trình duyệt
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)

    # 2. Gọi API lấy năm (Sử dụng trực tiếp requests.get)
    try:
        res_y = requests.get(f"{API_BASE_URL}/years-range-rec")
        data_y = res_y.json()
        years_list = list(range(data_y['min_year'], data_y['max_year'] + 1))
    except:
        years_list = [datetime.now().year]

    # 3. Gọi API lấy thống kê (Sử dụng trực tiếp requests.get)
    try:
        res_s = requests.get(f"{API_BASE_URL}/stats", params={'month': month, 'year': year})
        stats = res_s.json()
    except:
        # Fallback dữ liệu trống nếu API sập
        stats = {
            "general": {"occupied": 0, "available": 0, "ci_today": 0, "co_today": 0},
            "monthly": {"staying": 0, "ci": 0, "co": 0},
            "chart": {"labels": [], "ci": [], "co": [], "stay": []}
        }

    return render_template('receptionist/dashboard_rec.html',
                           stats=stats,
                           current_month=month,
                           current_year=year,
                           years_list=years_list)

# Kt dashboard_rec

# rooms_layout_rec
def get_ui_assets(status_data):
    """
    Hàm bổ trợ để map dữ liệu từ API sang giao diện
    """
    code = status_data.get('status_code')

    if code == 'MAINTENANCE':
        return "status-maintenance", "fa-screwdriver-wrench", "Phòng đang bảo trì"

    if code == 'LOCKED':
        # Trạng thái phòng bị khóa
        return "status-locked", "fa-lock", "Phòng đang bị khóa"

    if code == 'OCCUPIED':
        icon = "fa-bed"
        if status_data.get('is_checkout_today'):
            icon = "fa-suitcase-rolling" # Icon trả phòng
        return "status-occupied", icon, status_data.get('description')

    # Mặc định là phòng trống
    return "status-available", "fa-door-open", "Phòng trống"


# rooms_layout_rec
@app.route('/rooms_layout_rec', methods=['GET'])
def rooms_layout_rec():
    # 1. Lấy tham số từ URL người dùng gửi lên Client
    checkin_str = request.args.get('checkin_date', date.today().isoformat())
    checkout_str = request.args.get('checkout_date', date.today().isoformat())
    ma_loai_filter = request.args.get('ma_loai', 'all')

    try:
        # 2. Gọi API lấy danh sách loại phòng (để hiện Select box)
        # Giả sử bạn đã tạo API này ở Server: /api/room-types
        res_types = requests.get(f"{API_BASE_URL}/room-types-rec")
        danh_sach_loai = res_types.json() if res_types.status_code == 200 else []

        # 3. Gọi API lấy danh sách các tầng
        res_floors = requests.get(f"{API_BASE_URL}/floors")
        floors = res_floors.json() if res_floors.status_code == 200 else []

        dict_tang = {}

        # 4. Duyệt qua từng tầng để lấy danh sách phòng và trạng thái
        for tang in floors:
            tang_name = f"Tầng {tang}"

            # Gọi API lấy danh sách phòng của tầng này
            res_rooms = requests.get(f"{API_BASE_URL}/floors/{tang}/rooms")
            rooms_in_floor = res_rooms.json() if res_rooms.status_code == 200 else []

            floor_list = []
            for r in rooms_in_floor:
                # Nếu có lọc theo MaLoai, kiểm tra tại đây (Hoặc lọc ở Server)
                # Lưu ý: API /floors/X/rooms cần trả về MaLoai để lọc
                if ma_loai_filter != 'all' and str(r.get('MaLoai')) != ma_loai_filter:
                    continue

                # Gọi API lấy trạng thái chi tiết cho từng phòng
                params = {'checkin_date': checkin_str, 'checkout_date': checkout_str}
                res_status = requests.get(f"{API_BASE_URL}/room-status/{r['MaPhong']}", params=params)

                if res_status.status_code == 200:
                    status_data = res_status.json()

                    # Map dữ liệu API sang định dạng Template cần
                    status_class, icon, tooltip = get_ui_assets(status_data)

                    floor_list.append({
                        'so_phong': status_data['SoPhong'],
                        'ten_loai': status_data['TenLoai'],
                        'status_class': status_class,
                        'icon': icon,
                        'tooltip': tooltip,
                        'is_checkout_today': status_data.get('is_checkout_today', False)
                    })

            if floor_list:
                dict_tang[tang_name] = floor_list

    except Exception as e:
        print(f"Lỗi gọi API: {e}")
        dict_tang = {}
        danh_sach_loai = []

    # 5. Render ra template với dữ liệu đã xử lý từ API
    return render_template('receptionist/rooms_layout_rec.html',
                           dict_tang=dict_tang,
                           danh_sach_loai=danh_sach_loai,
                           checkin_date=checkin_str,
                           checkout_date=checkout_str,
                           ma_loai_filter=ma_loai_filter)

# ket thuc rooms_layout_rec

# rooms_assign_rec
@app.route('/rooms_assign_rec', methods=['GET'])
def rooms_assign_rec():
    # 1. Danh sách tham số (Thêm ma_loai)
    keys = ['search', 'status', 'ma_loai']

    for key in keys:
        if key in request.args:
            session[f'ra_{key}'] = request.args.get(key)
        elif f'ra_{key}' not in session:
            session[f'ra_{key}'] = 'all' if key != 'search' else ''

    search_query = session.get('ra_search')
    status_filter = session.get('ra_status')
    ma_loai_filter = session.get('ra_ma_loai')

    # 2. Gọi API lấy danh sách loại phòng cho Dropdown
    res_types = requests.get(f"{API_BASE_URL}/room-types-rec")
    room_types = res_types.json() if res_types.status_code == 200 else []

    # 3. Gọi API lấy danh sách đặt phòng kèm bộ lọc ma_loai
    params = {
        'search': search_query,
        'status': status_filter,
        'ma_loai': ma_loai_filter
    }
    res_bookings = requests.get(f"{API_BASE_URL}/bookings", params=params)
    bookings = res_bookings.json() if res_bookings.status_code == 200 else []

    # 4. Gọi API metadata phòng
    res_meta = requests.get(f"{API_BASE_URL}/rooms-metadata")
    meta_data = res_meta.json() if res_meta.status_code == 200 else {"rooms": [], "booked_intervals": []}

    return render_template('receptionist/rooms_assign_rec.html',
                           bookings=bookings,
                           room_types=room_types,  # Gửi sang HTML
                           all_rooms=meta_data['rooms'],
                           all_booked_intervals=meta_data['booked_intervals'],
                           search_query=search_query,
                           status_filter=status_filter,
                           ma_loai_filter=ma_loai_filter)


@app.route('/rooms_assign_rec/reset')
def rooms_assign_rec_reset():
    for key in ['ra_search', 'ra_status', 'ra_ma_loai']:
        session.pop(key, None)
    return redirect(url_for('rooms_assign_rec'))


@app.route('/assign_room', methods=['POST'])
def assign_room():
    ma_ctdp = request.form.get('ma_ctdp')
    ma_phong = request.form.get('ma_phong')

    if ma_phong:
        # Gọi API để lưu vào DB
        requests.post(f"{API_BASE_URL}/assign-room", json={'ma_ctdp': ma_ctdp, 'ma_phong': ma_phong})
        flash("Gán phòng thành công!", "success")

    return redirect(url_for('rooms_assign_rec'))


@app.route('/unassign_room/<int:ma_ctdp>')
def unassign_room(ma_ctdp):
    # Gọi sang API Server để thực hiện xóa số phòng gán
    try:
        res = requests.post(f"{API_BASE_URL}/unassign-room", json={'ma_ctdp': ma_ctdp})
        if res.status_code == 200:
            flash("Đã hủy gán phòng thành công!", "success")
        else:
            flash("Lỗi: " + res.json().get('message'), "danger")
    except Exception as e:
        flash("Lỗi kết nối API: " + str(e), "danger")

    return redirect(url_for('rooms_assign_rec'))
# End rooms_assign_rec

# checkin_rec
@app.route('/checkin_rec', methods=['GET'])
def checkin_rec():
    # 1. Danh sách các phím cần lưu trữ trong session
    keys = ['search', 'status_filter', 'process_date']

    # 2. Xử lý đồng bộ giữa URL Params và Session
    for key in keys:
        # Nếu người dùng vừa nhấn "Lọc" hoặc "Tìm kiếm" (có giá trị trên URL)
        if key in request.args:
            session[f'ci_{key}'] = request.args.get(key)
        # Nếu không có trên URL nhưng trong session đã có (do lần lọc trước đó)
        elif f'ci_{key}' not in session:
            # Gán giá trị mặc định cho lần đầu tiên truy cập
            if key == 'process_date':
                session[f'ci_{key}'] = date.today().isoformat()
            elif key == 'search':
                session[f'ci_{key}'] = ''
            else:
                session[f'ci_{key}'] = 'all'

    # 3. Lấy giá trị thực tế từ session để thực hiện gọi API
    search = session.get('ci_search')
    status_filter = session.get('ci_status_filter')
    today = session.get('ci_process_date')

    # 4. Gọi API lấy danh sách với các tham số từ session
    params = {
        'search': search,
        'status_filter': status_filter
    }

    try:
        res = requests.get(f"{API_BASE_URL}/checkin-list", params=params)
        bookings = res.json() if res.status_code == 200 else []
    except:
        bookings = []

    # 5. Render template và truyền lại các giá trị để hiển thị trên input/select
    return render_template('receptionist/checkin_rec.html',
                           bookings=bookings,
                           search_query=search,
                           status_filter=status_filter,
                           today=today)


# 6. Route Reset để xóa bộ lọc
@app.route('/checkin_rec/reset')
def checkin_rec_reset():
    # Xóa các biến liên quan đến trang checkin trong session
    session.pop('ci_search', None)
    session.pop('ci_status_filter', None)
    session.pop('ci_process_date', None)
    return redirect(url_for('checkin_rec'))


@app.route('/confirm_checkin_detail/<int:ma_ctdp>')
def confirm_checkin_detail(ma_ctdp):
    requests.post(f"{API_BASE_URL}/checkin-detail/{ma_ctdp}")
    flash("Đã thực hiện nhận phòng thành công!", "success")
    return redirect(url_for('checkin_rec'))


# Xác nhận đơn (Chuyển từ Chờ xác nhận -> Đã xác nhận)
@app.route('/confirm_booking_rec/<ma_dp>')
def confirm_booking_rec(ma_dp):
    requests.post(f"{API_BASE_URL}/update-booking-status",
                  json={'ma_dp': ma_dp, 'status': 'Đã xác nhận'})
    flash(f"Đã xác nhận đơn #{ma_dp}!", "success")
    return redirect(url_for('checkin_rec'))

# Route hủy đơn
@app.route('/cancel_booking/<ma_dp>')
def cancel_booking(ma_dp):
    requests.post(f"{API_BASE_URL}/update-booking-status",
                  json={'ma_dp': ma_dp, 'status': 'Đã hủy'})
    flash(f"Đã hủy đơn #{ma_dp}!", "warning")
    return redirect(url_for('checkin_rec'))

# Kt checkin_rec

# checkout_rec
@app.route('/checkout_rec', methods=['GET'])
def checkout_rec():
    # 1. Danh sách các tham số cần theo dõi
    keys = ['search', 'pay_filter', 'booking_filter', 'process_date']

    # 2. Đồng bộ hóa giữa URL và Session
    for key in keys:
        # Nếu có trên URL (người dùng vừa nhấn Lọc hoặc đổi trang)
        if key in request.args:
            session[f'ck_{key}'] = request.args.get(key)
        # Nếu không có trên URL nhưng cũng chưa có trong session -> Gán mặc định
        elif f'ck_{key}' not in session:
            if key == 'process_date':
                session[f'ck_{key}'] = date.today().isoformat()
            elif key == 'search':
                session[f'ck_{key}'] = ''
            else:
                session[f'ck_{key}'] = 'all'

    # 3. Lấy giá trị cuối cùng từ session để làm việc
    search = session.get('ck_search')
    pay_filter = session.get('ck_pay_filter')
    booking_filter = session.get('ck_booking_filter')
    today = session.get('ck_process_date')

    # 4. Gọi API với các tham số đã lấy từ session
    params = {
        'search': search,
        'pay_filter': pay_filter,
        'booking_filter': booking_filter
    }

    try:
        res = requests.get(f"{API_BASE_URL}/checkout-list", params=params)
        bookings = res.json() if res.status_code == 200 else []
    except:
        bookings = []

    return render_template('receptionist/checkout_rec.html',
                           bookings=bookings,
                           search_query=search,
                           pay_filter=pay_filter,
                           booking_filter=booking_filter,
                           today=today)

# Route Reset bộ lọc (Dùng khi muốn xóa hết session lọc)
@app.route('/checkout_rec/reset')
def checkout_rec_reset():
    keys = ['ck_search', 'ck_pay_filter', 'ck_booking_filter', 'ck_process_date']
    for key in keys:
        session.pop(key, None)
    return redirect(url_for('checkout_rec'))

@app.route('/pay_booking/<int:ma_dp>', methods=['POST'])
def pay_booking(ma_dp):
    # 1. Lấy dữ liệu từ form HTML
    tong_tien = request.form.get('total')
    # Đây là giá trị từ <select name="payment_method">
    phuong_thuc_moi = request.form.get('payment_method')

    # 2. Lấy ID nhân viên từ session (người đang trực máy)
    ma_nv = session['current_user']['MaTK']

    if not ma_nv:
        flash("Vui lòng đăng nhập để thực hiện thanh toán!", "danger")
        return redirect(url_for('login'))

    # 3. Gọi API xử lý logic cập nhật DB
    try:
        payload = {
            'ma_dp': ma_dp,
            'ma_nv': ma_nv,
            'tong_tien': tong_tien,
            'phuong_thuc': phuong_thuc_moi  # Gửi giá trị mới này lên Server
        }
        res = requests.post(f"{API_BASE_URL}/process-payment", json=payload)

        if res.status_code == 200:
            flash(f"Thanh toán đơn #{ma_dp} thành công!", "success")
        else:
            flash("Lỗi xử lý thanh toán: " + res.json().get('message', 'Unknown'), "danger")

    except Exception as e:
        flash("Lỗi kết nối API: " + str(e), "danger")

    return redirect(url_for('checkout_rec'))

@app.route('/confirm_checkout_detail/<int:ma_ctdp>')
def confirm_checkout_detail(ma_ctdp):
    # Gọi sang API Server cập nhật trạng thái 'Đã trả'
    res = requests.post(f"{API_BASE_URL}/update-detail-status",
                        json={'ma_ctdp': ma_ctdp, 'status': 'Đã trả'})
    if res.status_code == 200:
        flash("Cập nhật trạng thái phòng thành công!", "success")
    else:
        flash("Lỗi khi trả phòng!", "danger")
    return redirect(url_for('checkout_rec'))

@app.route('/complete_booking/<int:ma_dp>')
def complete_booking(ma_dp):
    requests.post(f"{API_BASE_URL}/update-booking-status", json={'ma_dp': ma_dp, 'status': 'Hoàn tất'})
    flash("Đơn đặt đã hoàn tất!", "success")
    return redirect(url_for('checkout_rec'))
# Kt Checkout_rec


# services_manage_rec
@app.route('/services_manage_rec')
def services_manage_rec():
    # 1. Quản lý lưu trữ bộ lọc vào Session
    filter_keys = ['status', 'start_date', 'end_date', 'search']

    for key in filter_keys:
        # Nếu có trên URL (người dùng vừa submit form) -> Lưu vào session
        if key in request.args:
            session[f'srv_{key}'] = request.args.get(key)
        # Nếu không có trên URL nhưng trong session cũng chưa có -> Gán mặc định
        elif f'srv_{key}' not in session:
            session[f'srv_{key}'] = 'all' if key == 'status' else ''

    # 2. Lấy giá trị từ session để gửi API
    status = session.get('srv_status')
    start_date = session.get('srv_start_date')
    end_date = session.get('srv_end_date')
    search = session.get('srv_search')

    # 3. Gọi API
    params = {'status': status, 'start_date': start_date, 'end_date': end_date, 'search': search}
    res_orders = requests.get(f"{API_BASE_URL}/service-orders", params=params)
    orders = res_orders.json() if res_orders.status_code == 200 else []

    res_catalog = requests.get(f"{API_BASE_URL}/service-catalog")
    catalog = res_catalog.json() if res_catalog.status_code == 200 else []

    return render_template('receptionist/services_manage_rec.html',
                           orders=orders,
                           catalog=catalog,
                           status_filter=status,
                           start_date=start_date,
                           end_date=end_date,
                           search_query=search)


# Thêm route reset lọc nếu cần
@app.route('/services_manage_rec/reset')
def services_manage_rec_reset():
    for key in ['srv_status', 'srv_start_date', 'srv_end_date', 'srv_search']:
        session.pop(key, None)
    return redirect(url_for('services_manage_rec'))


@app.route('/update_service_order/<int:ma_pdv>/<status>')
def update_service_order(ma_pdv, status):
    # Mapping status từ URL sang tiếng Việt chuẩn DB
    status_map = {'served': 'Đã phục vụ', 'canceled': 'Đã hủy'}
    new_status = status_map.get(status)

    if new_status:
        requests.post(f"{API_BASE_URL}/update-service-status", json={
            'ma_pdv': ma_pdv,
            'status': new_status
        })
        flash(f"Đã cập nhật trạng thái: {new_status}", "success")

    return redirect(url_for('services_manage_rec'))

# Kt services_manage_rec

# customer_list_rec

# Cầu nối (Proxy) để Javascript gọi lấy lịch sử
@app.route('/api/customer-history/<int:ma_kh>')
def customer_history_proxy(ma_kh):
    # Gọi sang API Server (Port 5000)
    response = requests.get(f"{API_BASE_URL}/customer-history/{ma_kh}")
    return jsonify(response.json())

@app.route('/customer_list_rec')
def customer_list_rec():
    search = request.args.get('search', '')
    status_filter = request.args.get('status_filter', 'all')
    response = requests.get(f"{API_BASE_URL}/customers", params={'search': search, 'status_filter': status_filter})
    customers = response.json() if response.status_code == 200 else []

    return render_template('receptionist/customer_list_rec.html',
                           customers=customers,
                           search_query=search,
                           status_filter=status_filter)


# Kt customer_list_rec