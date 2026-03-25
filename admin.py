from flask import session, redirect, render_template, request

from main import app

# 🔹 Dashboard Admin
@app.route('/dashboard_admin')
def dashboard_admin():
    return render_template('admin/dashboard_admin.html')


# 🔹 Quản lý Phòng
@app.route('/rooms_admin')
def rooms_admin():
    return render_template('admin/rooms_admin.html')


# 🔹 Quản lý Loại phòng
@app.route('/rooms_types_admin')
def rooms_types_admin():
    return render_template('admin/rooms_types_admin.html')


# 🔹 Quản lý Dịch vụ
@app.route('/services_admin')
def services_admin():
    return render_template('admin/services_admin.html')


# 🔹 Quản lý Nhân viên
@app.route('/staffs_admin')
def staffs_admin():
    return render_template('admin/staffs_admin.html')


# 🔹 Quản lý Khách hàng
@app.route('/customers_admin')
def customers_admin():
    return render_template('admin/customers_admin.html')