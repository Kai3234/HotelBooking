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
    # 1. Lấy param từ URL
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')

    # 2. Gọi API lấy danh sách đặt phòng
    res_bookings = requests.get(f"{API_BASE_URL}/bookings", params={'search': search, 'status': status})
    bookings = res_bookings.json() if res_bookings.status_code == 200 else []

    # 3. Gọi API lấy dữ liệu phòng và lịch bận (Dùng cho Modal gán phòng)
    res_meta = requests.get(f"{API_BASE_URL}/rooms-metadata")
    meta_data = res_meta.json() if res_meta.status_code == 200 else {"rooms": [], "booked_intervals": []}

    return render_template('receptionist/rooms_assign_rec.html',
                           bookings=bookings,
                           all_rooms=meta_data['rooms'],
                           all_booked_intervals=meta_data['booked_intervals'],
                           search_query=search,
                           status_filter=status)


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
@app.route('/checkin_rec')
def checkin_rec():
    search = request.args.get('search', '')
    status_filter = request.args.get('status_filter', 'all')  # Lấy từ request

    # Gửi tham số lọc sang API
    res = requests.get(f"{API_BASE_URL}/checkin-list", params={
        'search': search,
        'status_filter': status_filter
    })

    bookings = res.json() if res.status_code == 200 else []
    today = date.today().isoformat()

    return render_template('receptionist/checkin_rec.html',
                           bookings=bookings,
                           search_query=search,
                           status_filter=status_filter,  # Truyền lại sang HTML để giữ trạng thái select
                           today=today)


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
@app.route('/checkout_rec')
def checkout_rec():
    return render_template('receptionist/checkout_rec.html')


# Kt Checkout_rec


# services_manage_rec
@app.route('/services_manage_rec')
def services_manage_rec():
    status = request.args.get('status', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search = request.args.get('search', '')

    # 1. Gọi API lấy các yêu cầu (Orders)
    params = {'status': status, 'start_date': start_date, 'end_date': end_date, 'search': search}
    res_orders = requests.get(f"{API_BASE_URL}/service-orders", params=params)
    orders = res_orders.json() if res_orders.status_code == 200 else []

    # 2. Gọi API lấy danh mục dịch vụ (Catalog)
    res_catalog = requests.get(f"{API_BASE_URL}/service-catalog")
    catalog = res_catalog.json() if res_catalog.status_code == 200 else []

    return render_template('receptionist/services_manage_rec.html',
                           orders=orders,
                           catalog=catalog,
                           status_filter=status,
                           start_date=start_date,
                           end_date=end_date,
                           search_query=search)


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