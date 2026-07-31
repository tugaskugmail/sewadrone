from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from extensions import db
from models import User
import os
import uuid

auth_bp = Blueprint('auth', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_file(file, folder='uploads'):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        from flask import current_app
        filepath = os.path.join(current_app.root_path, 'static', folder)
        os.makedirs(filepath, exist_ok=True)
        file.save(os.path.join(filepath, filename))
        return f"/static/{folder}/{filename}"
    return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')

        user = User.query.filter_by(username=username).first()
        if not user:
            user = User.query.filter_by(email=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=bool(remember))
            next_page = request.args.get('next')
            flash(f'Selamat datang kembali, {user.full_name}!', 'success')
            if user.is_admin:
                return redirect(next_page or url_for('admin.dashboard'))
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Username/email atau password salah.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        nik = request.form.get('nik')
        address = request.form.get('address')
        
        # Handle signature (base64)
        signature = request.form.get('signature')
        
        # Handle KTP upload
        ktp_file = request.files.get('ktp_image')
        ktp_image_url = upload_file(ktp_file, 'uploads/ktp') if ktp_file else None

        # Validasi
        errors = []
        if not username or not email or not password or not full_name:
            errors.append('Username, Email, Password, dan Nama wajib diisi.')
        
        if not ktp_image_url:
            errors.append('Upload foto KTP wajib diperlukan.')
        
        if not signature:
            errors.append('Tanda tangan wajib diperlukan.')

        if User.query.filter_by(username=username).first():
            errors.append('Username sudah digunakan.')

        if User.query.filter_by(email=email).first():
            errors.append('Email sudah terdaftar.')

        if password != confirm_password:
            errors.append('Password tidak cocok.')

        if len(password) < 6:
            errors.append('Password minimal 6 karakter.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            full_name=full_name,
            phone=phone,
            nik=nik,
            address=address,
            ktp_image=ktp_image_url,
            signature=signature
        )
        db.session.add(user)
        db.session.commit()

        flash('Pendaftaran berhasil! Silakan login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    user = current_user
    user.full_name = request.form.get('full_name', user.full_name)
    user.phone = request.form.get('phone', user.phone)
    user.address = request.form.get('address', user.address)
    db.session.commit()
    flash('Profil berhasil diperbarui!', 'success')
    return redirect(url_for('auth.profile'))
