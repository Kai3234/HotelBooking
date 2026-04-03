import requests
import uuid

import os
from flask import session, redirect, render_template, request, url_for, flash, jsonify
from main import app

# Địa chỉ Backend API (webapi.py chạy ở cổng 5000)
API_URL = "http://127.0.0.1:5000/api"

def call_api(endpoint, method='GET', data=None, params=None):
    """Helper function để gọi Backend API (webapi.py)."""
    url = f"{API_URL}/{endpoint.lstrip('/')}"
    try:
        if method == 'GET':
            response = requests.get(url, params=params)
        elif method == 'POST':
            response = requests.post(url, json=data)
        else:
            return None
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"API Error ({url}): {str(e)}")
        return None

# ─────────────────────────────────────────────
# 🔹 UPLOAD ẢNH TRỰC TIẾP (Dành cho AJAX/Fetch)
# ─────────────────────────────────────────────
@app.route('/api/upload_image', methods=['POST'])
def direct_upload_image():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Không tìm thấy file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Chưa chọn file"}), 400
    
    folder = request.form.get('folder', 'services')
    # Lưu vào thư mục static của ứng dụng hiện tại (Admin/Main)
    upload_folder = os.path.join('static', 'images', folder)
    
    try:
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
            
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        
        file.save(filepath)
        
        # Trả về URL tương đối cho Frontend
        return jsonify({
            "status": "success",
            "url": f"images/{folder}/{filename}"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Upload Error: {str(e)}"}), 500



def require_admin(f):
    """Decorator kiểm tra quyền admin."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'current_user' not in session:
            return redirect(url_for('login'))
        if session['current_user'].get('LaAdmin') != 1:
            flash('Bạn không có quyền truy cập trang này!', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# 🔹 DASHBOARD ADMIN
# ─────────────────────────────────────────────
@app.route('/dashboard_admin')
@require_admin
def dashboard_admin():
    res = call_api('/admin/stats')
    stats = res.get('data') if res else {}
    return render_template('admin/dashboard_admin.html', stats=stats)



# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ PHÒNG
# ─────────────────────────────────────────────
@app.route('/rooms_admin')
@require_admin
def rooms_admin():
    params = {
        'search': request.args.get('search', '').strip(),
        'tang': request.args.get('tang', ''),
        'ma_loai': request.args.get('ma_loai', ''),
        'trang_thai': request.args.get('trang_thai', '')
    }

    res = call_api('/rooms', params=params)
    if not res:
        flash('Không thể kết nối Backend API!', 'danger')
        return render_template('admin/rooms_admin.html', rooms=[], room_types=[], floors=[])

    return render_template('admin/rooms_admin.html',
                           rooms=res.get('rooms', []),
                           room_types=res.get('room_types', []),
                           floors=res.get('floors', []),
                           search=params['search'],
                           filter_floor=params['tang'],
                           filter_type=params['ma_loai'],
                           filter_status=params['trang_thai'])



@app.route('/rooms_admin/add', methods=['POST'])
@require_admin
def rooms_admin_add():
    data = {
        'so_phong': request.form.get('so_phong', '').strip(),
        'tang': request.form.get('tang', '').strip(),
        'ma_loai': request.form.get('ma_loai', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip(),
        'trang_thai': request.form.get('trang_thai', 'Sẵn sàng')
    }

    if not data['so_phong'] or not data['tang'] or not data['ma_loai']:
        flash('Vui lòng nhập đầy đủ thông tin!', 'danger')
        return redirect(url_for('rooms_admin'))

    res = call_api('/rooms/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash(f"Đã thêm phòng {data['so_phong']} thành công!", 'success')
    else:
        error_msg = res.get('message') if res else 'Lỗi kết nối API'
        flash(f'Lỗi: {error_msg}', 'danger')
        
    return redirect(url_for('rooms_admin'))



@app.route('/rooms_admin/edit/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_edit(ma_phong):
    data = {
        'so_phong': request.form.get('so_phong', '').strip(),
        'tang': request.form.get('tang', '').strip(),
        'ma_loai': request.form.get('ma_loai', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip(),
        'trang_thai': request.form.get('trang_thai')
    }

    res = call_api(f'/rooms/edit/{ma_phong}', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash('Cập nhật phòng thành công!', 'success')
    else:
        error_msg = res.get('message') if res else 'Lỗi kết nối API'
        flash(f'Lỗi: {error_msg}', 'danger')
        
    return redirect(url_for('rooms_admin'))



@app.route('/rooms_admin/toggle/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_toggle(ma_phong):
    res = call_api(f'/rooms/toggle/{ma_phong}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': res.get('message') if res else 'Lỗi API'})



@app.route('/rooms_admin/lock/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_lock(ma_phong):
    res = call_api(f'/rooms/lock/{ma_phong}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': res.get('message') if res else 'Lỗi API'})



# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ LOẠI PHÒNG
# ─────────────────────────────────────────────
@app.route('/rooms_types_admin')
@require_admin
def rooms_types_admin():
    params = {
        'search': request.args.get('search', '').strip(),
        'trang_thai': request.args.get('trang_thai', '')
    }

    res = call_api('/room-types', params=params)
    return render_template('admin/rooms_types_admin.html',
                           room_types=res.get('room_types', []) if res else [],
                           search=params['search'], 
                           filter_status=params['trang_thai'])



@app.route('/rooms_types_admin/add', methods=['POST'])
@require_admin
def rooms_types_admin_add():
    data = {
        'ten_loai': request.form.get('ten_loai', '').strip(),
        'gia_tien': request.form.get('gia_tien', '').strip(),
        'so_nguoi': request.form.get('so_nguoi', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip()
    }

    if not data['ten_loai'] or not data['gia_tien'] or not data['so_nguoi']:
        flash('Vui lòng nhập đầy đủ thông tin!', 'danger')
        return redirect(url_for('rooms_types_admin'))

    res = call_api('/room-types/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash(f"Đã thêm loại phòng \"{data['ten_loai']}\" thành công!", 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('rooms_types_admin'))



@app.route('/rooms_types_admin/edit/<int:ma_loai>', methods=['POST'])
@require_admin
def rooms_types_admin_edit(ma_loai):
    data = {
        'ten_loai': request.form.get('ten_loai', '').strip(),
        'gia_tien': request.form.get('gia_tien', '').strip(),
        'so_nguoi': request.form.get('so_nguoi', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip(),
        'trang_thai': request.form.get('trang_thai')
    }

    res = call_api(f'/room-types/edit/{ma_loai}', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash('Cập nhật loại phòng thành công!', 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('rooms_types_admin'))



@app.route('/rooms_types_admin/toggle/<int:ma_loai>', methods=['POST'])
@require_admin
def rooms_types_admin_toggle(ma_loai):
    res = call_api(f'/room-types/toggle/{ma_loai}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': 'Lỗi API'})



# --- Quản lý ảnh loại phòng ---
@app.route('/rooms_types_admin/<int:ma_loai>/images')
@require_admin
def room_type_images(ma_loai):
    res = call_api(f'/room-types/{ma_loai}/images')
    if res:
        return jsonify({
            'images': res.get('images', []),
            'room_type': res.get('room_type', {})
        })
    return jsonify({'images': [], 'room_type': {}})



@app.route('/rooms_types_admin/<int:ma_loai>/images/add', methods=['POST'])
@require_admin
def room_type_images_add(ma_loai):
    # Hỗ trợ cả JSON (AJAX) và Form (truyền thống)
    if request.is_json:
        data_in = request.get_json()
    else:
        data_in = request.form

    data = {
        'hinh_anh': data_in.get('hinh_anh', '').strip(),
        'la_anh_dai_dien': int(data_in.get('la_anh_dai_dien', 0)),
        'thu_tu': int(data_in.get('thu_tu', 0))
    }

    if not data['hinh_anh']:
        return jsonify({"status": "error", "message": "Vui lòng nhập đường dẫn ảnh!"}), 400
        
    res = call_api(f'/room-types/{ma_loai}/images/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        return jsonify({"status": "success", "message": "Đã thêm ảnh thành công!"})
    
    return jsonify({"status": "error", "message": "Lỗi kết nối API Backend"}), 500



@app.route('/rooms_types_admin/images/set_avatar/<int:ma_anh>', methods=['POST'])
@require_admin
def room_type_images_set_avatar(ma_anh):
    res = call_api(f'/room-types/images/set-avatar/{ma_anh}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Lỗi API'})



@app.route('/rooms_types_admin/images/delete/<int:ma_anh>', methods=['POST'])
@require_admin
def room_type_images_delete(ma_anh):
    res = call_api(f'/room-types/images/delete/{ma_anh}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Lỗi API'})



@app.route('/rooms_types_admin/images/reorder', methods=['POST'])
@require_admin
def room_type_images_reorder():
    data = request.get_json()
    res = call_api('/room-types/images/reorder', method='POST', data=data)
    if res and res.get('status') == 'success':
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Lỗi API'})



# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ DỊCH VỤ
# ─────────────────────────────────────────────
@app.route('/services_admin')
@require_admin
def services_admin():
    params = {
        'search': request.args.get('search', '').strip(),
        'trang_thai': request.args.get('trang_thai', '')
    }

    res = call_api('/services_admin', params=params)
    return render_template('admin/services_admin.html',
                           services=res.get('services', []) if res else [],
                           search=params['search'], filter_status=params['trang_thai'])



@app.route('/services_admin/add', methods=['POST'])
@require_admin
def services_admin_add():
    data = {
        'ten_dv': request.form.get('ten_dv', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip(),
        'gia_tien': request.form.get('gia_tien', '').strip(),
        'thay_doi_sl': int(request.form.get('thay_doi_sl', 0)),
        'tinh_theo_ngay': int(request.form.get('tinh_theo_ngay', 0)),
        'hinh_anh': request.form.get('hinh_anh', '').strip()
    }

    if not data['ten_dv'] or not data['gia_tien']:
        flash('Vui lòng nhập đầy đủ thông tin!', 'danger')
        return redirect(url_for('services_admin'))

    res = call_api('/services/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash(f"Đã thêm dịch vụ \"{data['ten_dv']}\" thành công!", 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('services_admin'))



@app.route('/services_admin/edit/<int:ma_dv>', methods=['POST'])
@require_admin
def services_admin_edit(ma_dv):
    data = {
        'ten_dv': request.form.get('ten_dv', '').strip(),
        'mo_ta': request.form.get('mo_ta', '').strip(),
        'gia_tien': request.form.get('gia_tien', '').strip(),
        'thay_doi_sl': int(request.form.get('thay_doi_sl', 0)),
        'tinh_theo_ngay': int(request.form.get('tinh_theo_ngay', 0)),
        'trang_thai': request.form.get('trang_thai', 'Đang có'),
        'hinh_anh': request.form.get('hinh_anh', '').strip()
    }

    res = call_api(f'/services/edit/{ma_dv}', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash('Cập nhật dịch vụ thành công!', 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('services_admin'))



@app.route('/services_admin/toggle/<int:ma_dv>', methods=['POST'])
@require_admin
def services_admin_toggle(ma_dv):
    res = call_api(f'/services/toggle/{ma_dv}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': 'Lỗi API'})



# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ NHÂN VIÊN
# ─────────────────────────────────────────────
@app.route('/staffs_admin')
@require_admin
def staffs_admin():
    params = {
        'search': request.args.get('search', '').strip(),
        'la_admin': request.args.get('la_admin', ''),
        'trang_thai': request.args.get('trang_thai', '')
    }

    res = call_api('/staffs', params=params)
    return render_template('admin/staffs_admin.html',
                           staffs=res.get('staffs', []) if res else [],
                           search=params['search'], filter_role=params['la_admin'], 
                           filter_status=params['trang_thai'])



@app.route('/staffs_admin/add', methods=['POST'])
@require_admin
def staffs_admin_add():
    data = {
        'ho_ten': request.form.get('ho_ten', '').strip(),
        'email': request.form.get('email', '').strip(),
        'sdt': request.form.get('sdt', '').strip(),
        'mat_khau': request.form.get('mat_khau', '').strip(),
        'la_admin': int(request.form.get('la_admin', 0))
    }

    if not data['ho_ten'] or not data['sdt'] or not data['mat_khau']:
        flash('Vui lòng nhập đầy đủ thông tin!', 'danger')
        return redirect(url_for('staffs_admin'))

    res = call_api('/staffs/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash(f"Đã thêm nhân viên \"{data['ho_ten']}\" thành công!", 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('staffs_admin'))



@app.route('/staffs_admin/edit/<int:ma_nv>', methods=['POST'])
@require_admin
def staffs_admin_edit(ma_nv):
    data = {
        'ho_ten': request.form.get('ho_ten', '').strip(),
        'email': request.form.get('email', '').strip(),
        'sdt': request.form.get('sdt', '').strip(),
        'mat_khau': request.form.get('mat_khau', '').strip(),
        'la_admin': int(request.form.get('la_admin', 0)),
        'trang_thai': request.form.get('trang_thai', 'Hoạt động')
    }

    res = call_api(f'/staffs/edit/{ma_nv}', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash('Cập nhật nhân viên thành công!', 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('staffs_admin'))



@app.route('/staffs_admin/toggle/<int:ma_nv>', methods=['POST'])
@require_admin
def staffs_admin_toggle(ma_nv):
    # Không cho phép khóa chính mình
    if session.get('current_user', {}).get('MaTK') == ma_nv:
        return jsonify({'success': False, 'error': 'Không thể khóa tài khoản đang đăng nhập!'})

    res = call_api(f'/staffs/toggle/{ma_nv}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': 'Lỗi API'})



# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ KHÁCH HÀNG
# ─────────────────────────────────────────────
@app.route('/customers_admin')
@require_admin
def customers_admin():
    params = {
        'search': request.args.get('search', '').strip(),
        'trang_thai': request.args.get('trang_thai', '')
    }

    res = call_api('/customers_admin', params=params)
    return render_template('admin/customers_admin.html',
                           customers=res.get('customers', []) if res else [],
                           search=params['search'], filter_status=params['trang_thai'])



@app.route('/customers_admin/add', methods=['POST'])
@require_admin
def customers_admin_add():
    data = {
        'ho_ten': request.form.get('ho_ten', '').strip(),
        'email': request.form.get('email', '').strip(),
        'sdt': request.form.get('sdt', '').strip(),
        'mat_khau': request.form.get('mat_khau', '').strip()
    }

    if not data['ho_ten'] or not data['email'] or not data['sdt'] or not data['mat_khau']:
        flash('Vui lòng nhập đầy đủ thông tin!', 'danger')
        return redirect(url_for('customers_admin'))

    res = call_api('/customers/add', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash(f"Đã thêm khách hàng \"{data['ho_ten']}\" thành công!", 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('customers_admin'))



@app.route('/customers_admin/edit/<int:ma_kh>', methods=['POST'])
@require_admin
def customers_admin_edit(ma_kh):
    data = {
        'ho_ten': request.form.get('ho_ten', '').strip(),
        'email': request.form.get('email', '').strip(),
        'sdt': request.form.get('sdt', '').strip(),
        'mat_khau': request.form.get('mat_khau', '').strip(),
        'trang_thai': request.form.get('trang_thai', 'Hoạt động')
    }

    res = call_api(f'/customers/edit/{ma_kh}', method='POST', data=data)
    if res and res.get('status') == 'success':
        flash('Cập nhật khách hàng thành công!', 'success')
    else:
        flash('Lỗi kết nối API', 'danger')
    return redirect(url_for('customers_admin'))



@app.route('/customers_admin/toggle/<int:ma_kh>', methods=['POST'])
@require_admin
def customers_admin_toggle(ma_kh):
    res = call_api(f'/customers/toggle/{ma_kh}', method='POST')
    if res and res.get('status') == 'success':
        return jsonify({'success': True, 'new_status': res.get('new_status')})
    return jsonify({'success': False, 'error': 'Lỗi API'})