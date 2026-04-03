import sqlite3
from datetime import datetime, timedelta, date
import requests
from flask import session, redirect, render_template, request, flash, url_for, jsonify

from main import app

API_BASE_URL = 'http://127.0.0.1:5000/api/rec'

@app.route('/dashboard_rec')
def dashboard_rec():
    return render_template('receptionist/dashboard_rec.html')


def get_ui_assets(room_data):
    """
    Hàm phụ trợ để chuyển đổi dữ liệu thô từ API thành
    class CSS, Icon và Tooltip cho giao diện.
    """
    status = room_data.get('status_code')
    is_checkout_today = room_data.get('is_checkout_today', False)

    if status == 'MAINTENANCE':
        return "status-maintenance", "fa-screwdriver-wrench", "Đang bảo trì"
    elif status == 'OCCUPIED':
        icon = "fa-suitcase-rolling" if is_checkout_today else "fa-bed"
        tooltip = f"Khách: {room_data.get('customer_name')} - Trả: {room_data.get('checkout_booked')}"
        return "status-occupied", icon, tooltip
    else:
        return "status-available", "fa-door-open", "Phòng trống"


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


@app.route('/checkin/<int:ma_ctdp>')
def checkin(ma_ctdp):
    # Gọi API thực hiện checkin
    requests.post(f"{API_BASE_URL}/checkin/{ma_ctdp}")
    flash("Khách đã nhận phòng!", "success")
    return redirect(url_for('rooms_assign_rec'))

# End rooms_assign_rec

@app.route('/checkin_rec')
def checkin_rec():
    return render_template('receptionist/checkin_rec.html')

@app.route('/checkout_rec')
def checkout_rec():
    return render_template('receptionist/checkout_rec.html')

@app.route('/services_manage_rec')
def services_manage_rec():
    return render_template('receptionist/services_manage_rec.html')


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