from datetime import datetime, date
from extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    nik = db.Column(db.String(20), nullable=True)  # NIK/KTP
    ktp_image = db.Column(db.String(300), nullable=True)  # Path to uploaded KTP
    signature = db.Column(db.Text, nullable=True)  # Base64 signature
    is_admin = db.Column(db.Boolean, default=False)
    is_superadmin = db.Column(db.Boolean, default=False)  # Superadmin: bisa hapus transaksi
    created_at = db.Column(db.DateTime, default=datetime.now)

    bookings = db.relationship('Booking', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


class Drone(db.Model):
    __tablename__ = 'drones'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    specs = db.Column(db.Text, nullable=True)
    daily_rate = db.Column(db.Integer, nullable=False)
    deposit = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, default=1)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(300), nullable=True)
    is_available = db.Column(db.Boolean, default=True)
    # Serial Numbers
    serial_drone = db.Column(db.String(100), nullable=True)
    serial_remote = db.Column(db.String(100), nullable=True)
    serial_battery_1 = db.Column(db.String(100), nullable=True)
    serial_battery_2 = db.Column(db.String(100), nullable=True)
    serial_battery_3 = db.Column(db.String(100), nullable=True)
    registration_number = db.Column(db.String(100), nullable=True)  # Nomor Registrasi Drone
    created_at = db.Column(db.DateTime, default=datetime.now)

    bookings = db.relationship('Booking', backref='drone', lazy=True)
    images = db.relationship('DroneImage', backref='drone', lazy=True, cascade='all, delete-orphan')

    @property
    def available_stock(self):
        booked_today = Booking.query.filter(
            Booking.drone_id == self.id,
            Booking.status.in_(['pending', 'confirmed', 'active']),
            Booking.start_date <= date.today(),
            Booking.end_date >= date.today()
        ).count()
        return max(0, self.stock - booked_today)

    @property
    def rating(self):
        return 4.8

    def __repr__(self):
        return f'<Drone {self.name}>'


class DroneImage(db.Model):
    __tablename__ = 'drone_images'

    id = db.Column(db.Integer, primary_key=True)
    drone_id = db.Column(db.Integer, db.ForeignKey('drones.id'), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<DroneImage for drone {self.drone_id}>'


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    drone_id = db.Column(db.Integer, db.ForeignKey('drones.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Integer, nullable=False)
    deposit_paid = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    # Status: pending, confirmed, active, completed, cancelled
    notes = db.Column(db.Text, nullable=True)
    pickup_location = db.Column(db.String(200), nullable=True)
    return_location = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relasi ke Berita Acara
    handover_record = db.relationship('HandoverRecord', backref='booking', uselist=False, lazy=True)
    return_record = db.relationship('ReturnRecord', backref='booking', uselist=False, lazy=True)

    @property
    def status_label(self):
        labels = {
            'pending': 'Menunggu Konfirmasi',
            'confirmed': 'Dikonfirmasi',
            'active': 'Sedang Berlangsung',
            'completed': 'Selesai',
            'cancelled': 'Dibatalkan'
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'pending': 'warning',
            'confirmed': 'info',
            'active': 'primary',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return colors.get(self.status, 'secondary')

    def __repr__(self):
        return f'<Booking {self.id}: {self.drone.name} ({self.start_date} - {self.end_date})>'


# ============================================================
# BERITA ACARA - SERAH TERIMA DRONE
# ============================================================

class HandoverRecord(db.Model):
    """Berita Acara Serah Terima Drone (dari Admin ke User)"""
    __tablename__ = 'handover_records'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False, unique=True)
    
    # Nomor berita acara
    document_number = db.Column(db.String(50), nullable=True)
    
    # Data peralatan
    serial_drone = db.Column(db.String(100), nullable=True)
    serial_remote = db.Column(db.String(100), nullable=True)
    serial_battery_1 = db.Column(db.String(100), nullable=True)
    serial_battery_2 = db.Column(db.String(100), nullable=True)
    serial_battery_3 = db.Column(db.String(100), nullable=True)
    
    # Waktu serah terima
    handover_date = db.Column(db.DateTime, default=datetime.now)
    handover_time_out = db.Column(db.String(10), nullable=True)  # Jam keluar
    
    # Status pembayaran
    payment_status = db.Column(db.String(20), default='pending')  # pending, dp, lunas
    
    # ===== CHECKLIST KELENGKAPAN (JSON) =====
    # Format: [{"item": "Drone Body", "qty": 1, "condition": "baik", "notes": ""}, ...]
    checklist_equipment = db.Column(db.Text, nullable=True)
    
    # ===== CHECKLIST KONDISI DRONE (JSON) =====
    # Format: [{"item": "Body retak?", "status": "ok", "notes": ""}, ...]
    checklist_condition = db.Column(db.Text, nullable=True)
    
    # Catatan khusus / kerusakan awal
    notes_damage = db.Column(db.Text, nullable=True)
    
    # Dokumentasi foto
    photo_out_attached = db.Column(db.Boolean, default=False)
    photo_out_url = db.Column(db.String(500), nullable=True)
    photo_out_urls = db.Column(db.Text, nullable=True)  # JSON array of photo paths
    
    # Tanda tangan (base64 atau URL)
    admin_signature = db.Column(db.Text, nullable=True)
    user_signature = db.Column(db.Text, nullable=True)
    
    # Status serah terima
    is_completed = db.Column(db.Boolean, default=False)
    user_accepted_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<HandoverRecord Booking#{self.booking_id}>'


class ReturnRecord(db.Model):
    """Berita Acara Pengembalian Drone (dari User ke Admin)"""
    __tablename__ = 'return_records'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False, unique=True)
    
    # Waktu pengembalian
    return_date = db.Column(db.DateTime, default=datetime.now)
    return_time_in = db.Column(db.String(10), nullable=True)  # Jam kembali
    
    # ===== CHECKLIST KELENGKAPAN SAAT KEMBALI (JSON) =====
    checklist_equipment = db.Column(db.Text, nullable=True)
    
    # ===== CHECKLIST KONDISI DRONE SAAT KEMBALI (JSON) =====
    checklist_condition = db.Column(db.Text, nullable=True)
    
    # Catatan kerusakan / masalah
    notes_damage = db.Column(db.Text, nullable=True)
    
    # Biaya perbaikan / penggantian (jika ada kerusakan)
    damage_cost = db.Column(db.Integer, default=0)
    damage_description = db.Column(db.Text, nullable=True)
    
    # Status deposit
    deposit_returned = db.Column(db.Boolean, default=False)
    deposit_deducted = db.Column(db.Integer, default=0)
    
    # Dokumentasi foto
    photo_return_attached = db.Column(db.Boolean, default=False)
    photo_return_url = db.Column(db.String(500), nullable=True)
    photo_return_urls = db.Column(db.Text, nullable=True)  # JSON array of photo paths
    
    # Tanda tangan
    admin_signature = db.Column(db.Text, nullable=True)
    user_signature = db.Column(db.Text, nullable=True)
    
    # Status pengembalian
    is_completed = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<ReturnRecord Booking#{self.booking_id}>'
