import sqlite3
import os
from flask import session, redirect, render_template, request, url_for, flash, jsonify
from main import app

DB_PATH = 'db/website.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    """Tự động thêm các cột mới nếu chưa tồn tại (tránh lỗi ALTER TABLE khi đã có)."""
    conn = get_db()
    c = conn.cursor()

    def add_column_if_not_exists(table, column, definition):
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.commit()
        except Exception:
            pass  # Cột đã tồn tại

    add_column_if_not_exists('KHACHHANG', 'TrangThai', "TEXT NOT NULL DEFAULT 'Hoạt động'")
    add_column_if_not_exists('NHANVIEN',  'TrangThai', "TEXT NOT NULL DEFAULT 'Hoạt động'")
    add_column_if_not_exists('NHANVIEN',  'Email',     "TEXT")
    add_column_if_not_exists('LOAIPHONG', 'TrangThai', "TEXT NOT NULL DEFAULT 'Hiển thị'")
    add_column_if_not_exists('LOAIPHONG', 'MoTa',      "TEXT")
    add_column_if_not_exists('PHONG',     'MoTa',      "TEXT")          # ← DB cũ chưa có
    add_column_if_not_exists('HINHANH_LOAIPHONG', 'ThuTu',        "INTEGER NOT NULL DEFAULT 0")
    add_column_if_not_exists('HINHANH_LOAIPHONG', 'LaAnhDaiDien', "INTEGER NOT NULL DEFAULT 0")
    conn.close()


# Gọi init schema ngay khi import
init_schema()


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
    conn = get_db()
    stats = {
        'total_rooms': conn.execute("SELECT COUNT(*) FROM PHONG").fetchone()[0],
        'available_rooms': conn.execute("SELECT COUNT(*) FROM PHONG WHERE TrangThai = 'Sẵn sàng'").fetchone()[0],
        'total_customers': conn.execute("SELECT COUNT(*) FROM KHACHHANG").fetchone()[0],
        'total_bookings': conn.execute("SELECT COUNT(*) FROM DATPHONG").fetchone()[0],
        'pending_bookings': conn.execute("SELECT COUNT(*) FROM DATPHONG WHERE TrangThai = 'Chờ xác nhận'").fetchone()[0],
        'staying_bookings': conn.execute("SELECT COUNT(*) FROM DATPHONG WHERE TrangThai = 'Đang lưu trú'").fetchone()[0],
    }
    conn.close()
    return render_template('admin/dashboard_admin.html', stats=stats)


# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ PHÒNG
# ─────────────────────────────────────────────
@app.route('/rooms_admin')
@require_admin
def rooms_admin():
    conn = get_db()
    search = request.args.get('search', '').strip()
    filter_floor = request.args.get('tang', '')
    filter_type = request.args.get('ma_loai', '')
    filter_status = request.args.get('trang_thai', '')

    query = """
        SELECT p.*, lp.TenLoai
        FROM PHONG p
        JOIN LOAIPHONG lp ON p.MaLoai = lp.MaLoai
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.SoPhong LIKE ? OR p.MoTa LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if filter_floor:
        try:
            query += " AND p.Tang = ?"
            params.append(int(filter_floor))
        except ValueError:
            pass
    if filter_type:
        query += " AND p.MaLoai = ?"
        params.append(filter_type)
    if filter_status:
        query += " AND p.TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY p.Tang, p.SoPhong"

    rooms = conn.execute(query, params).fetchall()
    room_types = conn.execute("SELECT * FROM LOAIPHONG ORDER BY TenLoai").fetchall()
    floors = conn.execute("SELECT DISTINCT Tang FROM PHONG ORDER BY Tang").fetchall()
    conn.close()
    return render_template('admin/rooms_admin.html',
                           rooms=rooms, room_types=room_types, floors=floors,
                           search=search, filter_floor=filter_floor,
                           filter_type=filter_type, filter_status=filter_status)


@app.route('/rooms_admin/add', methods=['POST'])
@require_admin
def rooms_admin_add():
    so_phong = request.form.get('so_phong', '').strip()
    tang = request.form.get('tang', '').strip()
    ma_loai = request.form.get('ma_loai', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()
    trang_thai = request.form.get('trang_thai', 'Sẵn sàng')

    if not so_phong or not tang or not ma_loai:
        flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'danger')
        return redirect(url_for('rooms_admin'))

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM PHONG WHERE SoPhong = ?", (so_phong,)).fetchone()
        if existing:
            flash(f'Số phòng "{so_phong}" đã tồn tại!', 'danger')
        else:
            conn.execute(
                "INSERT INTO PHONG (SoPhong, Tang, MaLoai, MoTa, TrangThai) VALUES (?, ?, ?, ?, ?)",
                (so_phong, int(tang), int(ma_loai), mo_ta, trang_thai)
            )
            conn.commit()
            flash(f'Đã thêm phòng {so_phong} thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('rooms_admin'))


@app.route('/rooms_admin/edit/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_edit(ma_phong):
    so_phong = request.form.get('so_phong', '').strip()
    tang = request.form.get('tang', '').strip()
    ma_loai = request.form.get('ma_loai', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()
    trang_thai = request.form.get('trang_thai', 'Sẵn sàng')

    conn = get_db()
    try:
        conn.execute(
            "UPDATE PHONG SET SoPhong=?, Tang=?, MaLoai=?, MoTa=?, TrangThai=? WHERE MaPhong=?",
            (so_phong, int(tang), int(ma_loai), mo_ta, trang_thai, ma_phong)
        )
        conn.commit()
        flash('Cập nhật phòng thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('rooms_admin'))


@app.route('/rooms_admin/toggle/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_toggle(ma_phong):
    """Toggle Sẵn sàng ↔ Bảo trì (chỉ khi phòng không bị Khóa)."""
    conn = get_db()
    try:
        room = conn.execute("SELECT TrangThai FROM PHONG WHERE MaPhong=?", (ma_phong,)).fetchone()
        if room:
            if room['TrangThai'] == 'Khóa':
                return jsonify({'success': False, 'error': 'Phòng đang bị khóa, không thể thay đổi trạng thái!'})
            new_status = 'Bảo trì' if room['TrangThai'] == 'Sẵn sàng' else 'Sẵn sàng'
            conn.execute("UPDATE PHONG SET TrangThai=? WHERE MaPhong=?", (new_status, ma_phong))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


@app.route('/rooms_admin/lock/<int:ma_phong>', methods=['POST'])
@require_admin
def rooms_admin_lock(ma_phong):
    """Khóa / Mở khóa phòng (thay cho xóa)."""
    conn = get_db()
    try:
        room = conn.execute("SELECT TrangThai FROM PHONG WHERE MaPhong=?", (ma_phong,)).fetchone()
        if room:
            if room['TrangThai'] == 'Khóa':
                # Mở khóa → trả về Sẵn sàng
                new_status = 'Sẵn sàng'
            else:
                # Khóa phòng
                new_status = 'Khóa'
            conn.execute("UPDATE PHONG SET TrangThai=? WHERE MaPhong=?", (new_status, ma_phong))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ LOẠI PHÒNG
# ─────────────────────────────────────────────
@app.route('/rooms_types_admin')
@require_admin
def rooms_types_admin():
    conn = get_db()
    search = request.args.get('search', '').strip()
    filter_status = request.args.get('trang_thai', '')

    query = "SELECT * FROM LOAIPHONG WHERE 1=1"
    params = []
    if search:
        query += " AND TenLoai LIKE ?"
        params.append(f'%{search}%')
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY TenLoai"

    room_types = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin/rooms_types_admin.html',
                           room_types=room_types,
                           search=search, filter_status=filter_status)


@app.route('/rooms_types_admin/add', methods=['POST'])
@require_admin
def rooms_types_admin_add():
    ten_loai = request.form.get('ten_loai', '').strip()
    gia_tien = request.form.get('gia_tien', '').strip()
    so_nguoi = request.form.get('so_nguoi', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()

    if not ten_loai or not gia_tien or not so_nguoi:
        flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'danger')
        return redirect(url_for('rooms_types_admin'))

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO LOAIPHONG (TenLoai, GiaTien, SoNguoiToiDa, MoTa, TrangThai) VALUES (?, ?, ?, ?, 'Hiển thị')",
            (ten_loai, int(gia_tien), int(so_nguoi), mo_ta)
        )
        conn.commit()
        flash(f'Đã thêm loại phòng "{ten_loai}" thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('rooms_types_admin'))


@app.route('/rooms_types_admin/edit/<int:ma_loai>', methods=['POST'])
@require_admin
def rooms_types_admin_edit(ma_loai):
    ten_loai = request.form.get('ten_loai', '').strip()
    gia_tien = request.form.get('gia_tien', '').strip()
    so_nguoi = request.form.get('so_nguoi', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()
    trang_thai = request.form.get('trang_thai', 'Hiển thị')

    conn = get_db()
    try:
        conn.execute(
            "UPDATE LOAIPHONG SET TenLoai=?, GiaTien=?, SoNguoiToiDa=?, MoTa=?, TrangThai=? WHERE MaLoai=?",
            (ten_loai, int(gia_tien), int(so_nguoi), mo_ta, trang_thai, ma_loai)
        )
        conn.commit()
        flash('Cập nhật loại phòng thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('rooms_types_admin'))


@app.route('/rooms_types_admin/toggle/<int:ma_loai>', methods=['POST'])
@require_admin
def rooms_types_admin_toggle(ma_loai):
    conn = get_db()
    try:
        rt = conn.execute("SELECT TrangThai FROM LOAIPHONG WHERE MaLoai=?", (ma_loai,)).fetchone()
        if rt:
            new_status = 'Ẩn' if rt['TrangThai'] == 'Hiển thị' else 'Hiển thị'
            conn.execute("UPDATE LOAIPHONG SET TrangThai=? WHERE MaLoai=?", (new_status, ma_loai))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


# --- Quản lý ảnh loại phòng ---
@app.route('/rooms_types_admin/<int:ma_loai>/images')
@require_admin
def room_type_images(ma_loai):
    conn = get_db()
    images = conn.execute(
        "SELECT * FROM HINHANH_LOAIPHONG WHERE MaLoai=? ORDER BY LaAnhDaiDien DESC, ThuTu ASC",
        (ma_loai,)
    ).fetchall()
    room_type = conn.execute("SELECT * FROM LOAIPHONG WHERE MaLoai=?", (ma_loai,)).fetchone()
    conn.close()
    return jsonify({
        'images': [dict(img) for img in images],
        'room_type': dict(room_type) if room_type else {}
    })


@app.route('/rooms_types_admin/<int:ma_loai>/images/add', methods=['POST'])
@require_admin
def room_type_images_add(ma_loai):
    hinh_anh = request.form.get('hinh_anh', '').strip()
    la_anh_dai_dien = int(request.form.get('la_anh_dai_dien', 0))
    thu_tu = request.form.get('thu_tu', 0)

    if not hinh_anh:
        flash('Vui lòng nhập đường dẫn ảnh!', 'danger')
        return redirect(url_for('rooms_types_admin'))

    conn = get_db()
    try:
        # Nếu đặt làm ảnh đại diện, reset ảnh đại diện cũ
        if la_anh_dai_dien == 1:
            conn.execute(
                "UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=0 WHERE MaLoai=?", (ma_loai,)
            )
        conn.execute(
            "INSERT INTO HINHANH_LOAIPHONG (MaLoai, HinhAnh, ThuTu, LaAnhDaiDien) VALUES (?, ?, ?, ?)",
            (ma_loai, hinh_anh, int(thu_tu), la_anh_dai_dien)
        )
        conn.commit()
        flash('Đã thêm ảnh thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('rooms_types_admin'))


@app.route('/rooms_types_admin/images/set_avatar/<int:ma_anh>', methods=['POST'])
@require_admin
def room_type_images_set_avatar(ma_anh):
    conn = get_db()
    try:
        img = conn.execute("SELECT MaLoai FROM HINHANH_LOAIPHONG WHERE MaAnh=?", (ma_anh,)).fetchone()
        if img:
            conn.execute("UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=0 WHERE MaLoai=?", (img['MaLoai'],))
            conn.execute("UPDATE HINHANH_LOAIPHONG SET LaAnhDaiDien=1 WHERE MaAnh=?", (ma_anh,))
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


@app.route('/rooms_types_admin/images/delete/<int:ma_anh>', methods=['POST'])
@require_admin
def room_type_images_delete(ma_anh):
    """Xóa ảnh (cho phép xóa thực sự vì ảnh không phải dữ liệu nghiệp vụ quan trọng)."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM HINHANH_LOAIPHONG WHERE MaAnh=?", (ma_anh,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


@app.route('/rooms_types_admin/images/reorder', methods=['POST'])
@require_admin
def room_type_images_reorder():
    """Cập nhật thứ tự hiển thị ảnh."""
    data = request.get_json()
    orders = data.get('orders', [])  # [{ma_anh: 1, thu_tu: 0}, ...]
    conn = get_db()
    try:
        for item in orders:
            conn.execute(
                "UPDATE HINHANH_LOAIPHONG SET ThuTu=? WHERE MaAnh=?",
                (item['thu_tu'], item['ma_anh'])
            )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ DỊCH VỤ
# ─────────────────────────────────────────────
@app.route('/services_admin')
@require_admin
def services_admin():
    conn = get_db()
    search = request.args.get('search', '').strip()
    filter_status = request.args.get('trang_thai', '')

    query = "SELECT * FROM DICHVU WHERE 1=1"
    params = []
    if search:
        query += " AND (TenDV LIKE ? OR MoTa LIKE ?)"
        params += [f'%{search}%', f'%{search}%']
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY TenDV"

    services = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin/services_admin.html',
                           services=services,
                           search=search, filter_status=filter_status)


@app.route('/services_admin/add', methods=['POST'])
@require_admin
def services_admin_add():
    ten_dv = request.form.get('ten_dv', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()
    gia_tien = request.form.get('gia_tien', '').strip()
    thay_doi_sl = int(request.form.get('thay_doi_sl', 0))
    hinh_anh = request.form.get('hinh_anh', '').strip()

    if not ten_dv or not gia_tien:
        flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'danger')
        return redirect(url_for('services_admin'))

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO DICHVU (TenDV, MoTa, GiaTien, ThayDoiSL, TrangThai, HinhAnh) VALUES (?, ?, ?, ?, 'Đang có', ?)",
            (ten_dv, mo_ta, int(gia_tien), thay_doi_sl, hinh_anh or None)
        )
        conn.commit()
        flash(f'Đã thêm dịch vụ "{ten_dv}" thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('services_admin'))


@app.route('/services_admin/edit/<int:ma_dv>', methods=['POST'])
@require_admin
def services_admin_edit(ma_dv):
    ten_dv = request.form.get('ten_dv', '').strip()
    mo_ta = request.form.get('mo_ta', '').strip()
    gia_tien = request.form.get('gia_tien', '').strip()
    thay_doi_sl = int(request.form.get('thay_doi_sl', 0))
    trang_thai = request.form.get('trang_thai', 'Đang có')
    hinh_anh = request.form.get('hinh_anh', '').strip()

    conn = get_db()
    try:
        conn.execute(
            "UPDATE DICHVU SET TenDV=?, MoTa=?, GiaTien=?, ThayDoiSL=?, TrangThai=?, HinhAnh=? WHERE MaDV=?",
            (ten_dv, mo_ta, int(gia_tien), thay_doi_sl, trang_thai, hinh_anh or None, ma_dv)
        )
        conn.commit()
        flash('Cập nhật dịch vụ thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('services_admin'))


@app.route('/services_admin/toggle/<int:ma_dv>', methods=['POST'])
@require_admin
def services_admin_toggle(ma_dv):
    conn = get_db()
    try:
        svc = conn.execute("SELECT TrangThai FROM DICHVU WHERE MaDV=?", (ma_dv,)).fetchone()
        if svc:
            new_status = 'Đang khóa' if svc['TrangThai'] == 'Đang có' else 'Đang có'
            conn.execute("UPDATE DICHVU SET TrangThai=? WHERE MaDV=?", (new_status, ma_dv))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ NHÂN VIÊN
# ─────────────────────────────────────────────
@app.route('/staffs_admin')
@require_admin
def staffs_admin():
    conn = get_db()
    search = request.args.get('search', '').strip()
    filter_role = request.args.get('la_admin', '')
    filter_status = request.args.get('trang_thai', '')

    query = "SELECT * FROM NHANVIEN WHERE 1=1"
    params = []
    if search:
        query += " AND (HoTen LIKE ? OR SDT LIKE ? OR Email LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if filter_role != '':
        query += " AND LaAdmin = ?"
        params.append(int(filter_role))
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY LaAdmin DESC, HoTen"

    staffs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin/staffs_admin.html',
                           staffs=staffs,
                           search=search, filter_role=filter_role, filter_status=filter_status)


@app.route('/staffs_admin/add', methods=['POST'])
@require_admin
def staffs_admin_add():
    ho_ten = request.form.get('ho_ten', '').strip()
    email = request.form.get('email', '').strip()
    sdt = request.form.get('sdt', '').strip()
    mat_khau = request.form.get('mat_khau', '').strip()
    la_admin = int(request.form.get('la_admin', 0))

    if not ho_ten or not sdt or not mat_khau:
        flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'danger')
        return redirect(url_for('staffs_admin'))

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM NHANVIEN WHERE SDT=?", (sdt,)).fetchone()
        if existing:
            flash(f'Số điện thoại "{sdt}" đã được sử dụng!', 'danger')
        else:
            conn.execute(
                "INSERT INTO NHANVIEN (HoTen, Email, SDT, MatKhau, LaAdmin, TrangThai) VALUES (?, ?, ?, ?, ?, 'Hoạt động')",
                (ho_ten, email, sdt, mat_khau, la_admin)
            )
            conn.commit()
            flash(f'Đã thêm nhân viên "{ho_ten}" thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('staffs_admin'))


@app.route('/staffs_admin/edit/<int:ma_nv>', methods=['POST'])
@require_admin
def staffs_admin_edit(ma_nv):
    ho_ten = request.form.get('ho_ten', '').strip()
    email = request.form.get('email', '').strip()
    sdt = request.form.get('sdt', '').strip()
    mat_khau = request.form.get('mat_khau', '').strip()
    la_admin = int(request.form.get('la_admin', 0))
    trang_thai = request.form.get('trang_thai', 'Hoạt động')

    conn = get_db()
    try:
        if mat_khau:
            conn.execute(
                "UPDATE NHANVIEN SET HoTen=?, Email=?, SDT=?, MatKhau=?, LaAdmin=?, TrangThai=? WHERE MaNV=?",
                (ho_ten, email, sdt, mat_khau, la_admin, trang_thai, ma_nv)
            )
        else:
            conn.execute(
                "UPDATE NHANVIEN SET HoTen=?, Email=?, SDT=?, LaAdmin=?, TrangThai=? WHERE MaNV=?",
                (ho_ten, email, sdt, la_admin, trang_thai, ma_nv)
            )
        conn.commit()
        flash('Cập nhật nhân viên thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('staffs_admin'))


@app.route('/staffs_admin/toggle/<int:ma_nv>', methods=['POST'])
@require_admin
def staffs_admin_toggle(ma_nv):
    # Không cho phép khóa chính mình
    if session.get('current_user', {}).get('MaTK') == ma_nv:
        return jsonify({'success': False, 'error': 'Không thể khóa tài khoản đang đăng nhập!'})

    conn = get_db()
    try:
        nv = conn.execute("SELECT TrangThai FROM NHANVIEN WHERE MaNV=?", (ma_nv,)).fetchone()
        if nv:
            new_status = 'Khóa' if nv['TrangThai'] == 'Hoạt động' else 'Hoạt động'
            conn.execute("UPDATE NHANVIEN SET TrangThai=? WHERE MaNV=?", (new_status, ma_nv))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})


# ─────────────────────────────────────────────
# 🔹 QUẢN LÝ KHÁCH HÀNG
# ─────────────────────────────────────────────
@app.route('/customers_admin')
@require_admin
def customers_admin():
    conn = get_db()
    search = request.args.get('search', '').strip()
    filter_status = request.args.get('trang_thai', '')

    query = "SELECT * FROM KHACHHANG WHERE 1=1"
    params = []
    if search:
        query += " AND (HoTen LIKE ? OR Email LIKE ? OR SDT LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if filter_status:
        query += " AND TrangThai = ?"
        params.append(filter_status)
    query += " ORDER BY HoTen"

    customers = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin/customers_admin.html',
                           customers=customers,
                           search=search, filter_status=filter_status)


@app.route('/customers_admin/add', methods=['POST'])
@require_admin
def customers_admin_add():
    ho_ten = request.form.get('ho_ten', '').strip()
    email = request.form.get('email', '').strip()
    sdt = request.form.get('sdt', '').strip()
    mat_khau = request.form.get('mat_khau', '').strip()

    if not ho_ten or not email or not sdt or not mat_khau:
        flash('Vui lòng nhập đầy đủ thông tin bắt buộc!', 'danger')
        return redirect(url_for('customers_admin'))

    conn = get_db()
    try:
        existing = conn.execute("SELECT * FROM KHACHHANG WHERE Email=?", (email,)).fetchone()
        if existing:
            flash(f'Email "{email}" đã được sử dụng!', 'danger')
        else:
            conn.execute(
                "INSERT INTO KHACHHANG (HoTen, Email, SDT, MatKhau, TrangThai) VALUES (?, ?, ?, ?, 'Hoạt động')",
                (ho_ten, email, sdt, mat_khau)
            )
            conn.commit()
            flash(f'Đã thêm khách hàng "{ho_ten}" thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('customers_admin'))


@app.route('/customers_admin/edit/<int:ma_kh>', methods=['POST'])
@require_admin
def customers_admin_edit(ma_kh):
    ho_ten = request.form.get('ho_ten', '').strip()
    email = request.form.get('email', '').strip()
    sdt = request.form.get('sdt', '').strip()
    mat_khau = request.form.get('mat_khau', '').strip()
    trang_thai = request.form.get('trang_thai', 'Hoạt động')

    conn = get_db()
    try:
        if mat_khau:
            conn.execute(
                "UPDATE KHACHHANG SET HoTen=?, Email=?, SDT=?, MatKhau=?, TrangThai=? WHERE MaKH=?",
                (ho_ten, email, sdt, mat_khau, trang_thai, ma_kh)
            )
        else:
            conn.execute(
                "UPDATE KHACHHANG SET HoTen=?, Email=?, SDT=?, TrangThai=? WHERE MaKH=?",
                (ho_ten, email, sdt, trang_thai, ma_kh)
            )
        conn.commit()
        flash('Cập nhật khách hàng thành công!', 'success')
    except Exception as e:
        flash(f'Lỗi: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('customers_admin'))


@app.route('/customers_admin/toggle/<int:ma_kh>', methods=['POST'])
@require_admin
def customers_admin_toggle(ma_kh):
    conn = get_db()
    try:
        kh = conn.execute("SELECT TrangThai FROM KHACHHANG WHERE MaKH=?", (ma_kh,)).fetchone()
        if kh:
            new_status = 'Khóa' if kh['TrangThai'] == 'Hoạt động' else 'Hoạt động'
            conn.execute("UPDATE KHACHHANG SET TrangThai=? WHERE MaKH=?", (new_status, ma_kh))
            conn.commit()
            return jsonify({'success': True, 'new_status': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
    return jsonify({'success': False})