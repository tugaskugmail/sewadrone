from flask import Flask
from extensions import db, login_manager, csrf
from werkzeug.security import generate_password_hash
from flask_login import UserMixin
import os


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'drone-rental-secret-key-2026')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///drone_rental.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Inisialisasi ekstensi
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'

    # Import models AFTER db init
    from models import User, Drone, Booking
    import json

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Custom Jinja2 filter
    @app.template_filter('from_json')
    def from_json_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception:
            return []

    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Context processor
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        from flask_login import current_user
        ctx = {'now': datetime.now()}
        try:
            if current_user.is_authenticated and current_user.is_admin:
                from models import Booking
                ctx['pending_count'] = Booking.query.filter_by(status='pending').count()
        except Exception:
            pass
        return ctx

    # Buat database & seed
    with app.app_context():
        db.create_all()
        if Drone.query.count() == 0:
            _seed_data()

    return app


def _seed_data():
    from models import User, Drone
    from werkzeug.security import generate_password_hash

    admin = User(
        username='admin',
        email='admin@drone-rental.com',
        password=generate_password_hash('admin123'),
        full_name='Administrator',
        phone='081234567890',
        is_admin=True
    )
    db.session.add(admin)

    drones = [
        Drone(
            name='DJI Mavic 3 Pro', brand='DJI', model='Mavic 3 Pro',
            description='Drone professional dengan kamera Hasselblad 4/3 CMOS, video 5.1K, transmission range 15km, flight time 43 menit.',
            specs='Kamera: Hasselblad 4/3 CMOS\nVideo: 5.1K/50fps, 4K/120fps\nTransmission: O3+ 15km\nFlight Time: 43 menit\nBobot: 895g\nWind Resistance: Level 5',
            daily_rate=750000, deposit=3000000, stock=3, category='Professional',
            image_url='/static/img/drone-mavic3.jpg', is_available=True),
        Drone(
            name='DJI Mini 4 Pro', brand='DJI', model='Mini 4 Pro',
            description='Drone compact dengan bobot <249g, kamera 48MP, video 4K/100fps, omnidirectional obstacle sensing.',
            specs='Kamera: 48MP 1/1.3" CMOS\nVideo: 4K/100fps, 1080p/200fps\nTransmission: O4 20km\nFlight Time: 34 menit\nBobot: <249g (tanpa SIM)\nObstacle Sensing: Omnidirectional',
            daily_rate=450000, deposit=1500000, stock=5, category='Compact',
            image_url='/static/img/drone-mini4.jpg', is_available=True),
        Drone(
            name='Autel Evo Lite+', brand='Autel', model='Evo Lite+',
            description='Alternatif Mavic dengan sensor 1" CMOS 50MP, video 6K/30fps, adjustable aperture f/2.8-f/11.',
            specs='Kamera: 50MP 1" CMOS\nVideo: 6K/30fps, 4K/60fps\nAperture: f/2.8 - f/11 (adjustable)\nTransmission: SkyLink 12km\nFlight Time: 40 menit\nBobot: 835g',
            daily_rate=650000, deposit=2500000, stock=2, category='Professional',
            image_url='/static/img/drone-autel.jpg', is_available=True),
        Drone(
            name='DJI Matrice 350 RTK', brand='DJI', model='Matrice 350 RTK',
            description='Drone enterprise untuk mapping, inspeksi, dan survey. Dilengkapi RTK module, IP55 rating.',
            specs='Payload Max: 2.7kg\nFlight Time: 55 menit\nIP Rating: IP55\nRTK: Built-in\nTransmission: O3 20km\nMax Wind: 15 m/s\nOperating Temp: -20°C s/d 50°C',
            daily_rate=3500000, deposit=10000000, stock=1, category='Enterprise',
            image_url='/static/img/drone-m350.jpg', is_available=True),
        Drone(
            name='DJI Air 3', brand='DJI', model='Air 3',
            description='Drone dual-camera: wide 24mm f/1.7 + tele 70mm f/2.8. Video 4K HDR, flight time 46 menit.',
            specs='Kamera: Dual (Wide 24mm + Tele 70mm)\nSensor: Dual 1/1.3" CMOS\nVideo: 4K/100fps HDR\nTransmission: O4 20km\nFlight Time: 46 menit\nBobot: 720g\nObstacle Sensing: Omnidirectional',
            daily_rate=550000, deposit=2000000, stock=3, category='Mid-range',
            image_url='/static/img/drone-air3.jpg', is_available=True),
        Drone(
            name='DJI Mavic 3 Classic', brand='DJI', model='Mavic 3 Classic',
            description='Versi ekonomis dari Mavic 3 Pro dengan kamera Hasselblad utama tanpa tele kamera.',
            specs='Kamera: Hasselblad 4/3 CMOS\nVideo: 5.1K/50fps, 4K/120fps\nTransmission: O3+ 15km\nFlight Time: 46 menit\nBobot: 895g\nStorage: 8GB Internal',
            daily_rate=550000, deposit=2000000, stock=2, category='Professional',
            image_url='/static/img/drone-mavic3c.jpg', is_available=True),
    ]
    for d in drones:
        db.session.add(d)
    db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
