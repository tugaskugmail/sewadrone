from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, datetime, timedelta
from extensions import db
from models import Drone, Booking, User, HandoverRecord, ReturnRecord
import json

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    featured_drones = Drone.query.filter_by(is_available=True).limit(6).all()
    categories = db.session.query(Drone.category).distinct().all()
    return render_template('index.html', featured_drones=featured_drones, categories=[c[0] for c in categories])


@main_bp.route('/drones')
def drones():
    category = request.args.get('category')
    brand = request.args.get('brand')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    search = request.args.get('search')

    query = Drone.query.filter_by(is_available=True)

    if category:
        query = query.filter_by(category=category)
    if brand:
        query = query.filter(Drone.brand.ilike(f'%{brand}%'))
    if min_price:
        query = query.filter(Drone.daily_rate >= min_price)
    if max_price:
        query = query.filter(Drone.daily_rate <= max_price)
    if search:
        query = query.filter(
            db.or_(
                Drone.name.ilike(f'%{search}%'),
                Drone.brand.ilike(f'%{search}%'),
                Drone.description.ilike(f'%{search}%')
            )
        )

    drones = query.order_by(Drone.created_at.desc()).all()
    categories = db.session.query(Drone.category).distinct().all()
    brands = db.session.query(Drone.brand).distinct().all()

    return render_template('drones.html',
                           drones=drones,
                           categories=[c[0] for c in categories],
                           brands=[b[0] for b in brands])


@main_bp.route('/drones/<int:drone_id>')
def drone_detail(drone_id):
    drone = Drone.query.get_or_404(drone_id)
    related_drones = Drone.query.filter(
        Drone.category == drone.category,
        Drone.id != drone.id,
        Drone.is_available == True
    ).limit(4).all()
    return render_template('drone_detail.html', drone=drone, related_drones=related_drones)


@main_bp.route('/booking/<int:drone_id>', methods=['GET', 'POST'])
@login_required
def booking(drone_id):
    drone = Drone.query.get_or_404(drone_id)

    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        notes = request.form.get('notes')
        pickup = request.form.get('pickup_location')
        return_loc = request.form.get('return_location')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Format tanggal tidak valid.', 'danger')
            return render_template('booking.html', drone=drone)

        if start_date < date.today():
            flash('Tanggal mulai tidak boleh di masa lalu.', 'danger')
            return render_template('booking.html', drone=drone)

        if end_date < start_date:
            flash('Tanggal selesai harus setelah tanggal mulai.', 'danger')
            return render_template('booking.html', drone=drone)

        total_days = (end_date - start_date).days + 1

        # Cek ketersediaan
        conflicting = Booking.query.filter(
            Booking.drone_id == drone.id,
            Booking.status.in_(['pending', 'confirmed', 'active']),
            Booking.start_date <= end_date,
            Booking.end_date >= start_date
        ).count()

        if conflicting >= drone.stock:
            flash('Drone tidak tersedia untuk rentang tanggal tersebut.', 'danger')
            return render_template('booking.html', drone=drone)

        total_price = drone.daily_rate * total_days
        deposit_paid = drone.deposit

        booking = Booking(
            user_id=current_user.id,
            drone_id=drone.id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            total_price=total_price,
            deposit_paid=deposit_paid,
            status='pending',
            notes=notes,
            pickup_location=pickup,
            return_location=return_loc
        )
        db.session.add(booking)
        db.session.commit()

        flash(f'Booking berhasil! ID Booking: #{booking.id}. Silakan tunggu konfirmasi.', 'success')
        return redirect(url_for('main.my_bookings'))

    return render_template('booking.html', drone=drone)


@main_bp.route('/my-bookings')
@login_required
def my_bookings():
    status_filter = request.args.get('status')
    query = Booking.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    bookings = query.order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)


@main_bp.route('/booking/<int:booking_id>/cancel')
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Anda tidak memiliki izin.', 'danger')
        return redirect(url_for('main.index'))

    if booking.status in ['pending', 'confirmed']:
        booking.status = 'cancelled'
        db.session.commit()
        flash('Booking berhasil dibatalkan.', 'success')
    else:
        flash('Booking tidak dapat dibatalkan pada status ini.', 'warning')

    return redirect(url_for('main.my_bookings'))


# ============================================================
# BERITA ACARA - USER SIDE
# ============================================================

@main_bp.route('/booking/<int:booking_id>/accept')
@login_required
def accept_handover(booking_id):
    """User menerima drone (konfirmasi Berita Acara Serah Terima)"""
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != current_user.id:
        flash('Anda tidak memiliki izin.', 'danger')
        return redirect(url_for('main.my_bookings'))
    
    if booking.status != 'confirmed':
        flash('Booking belum dikonfirmasi oleh admin.', 'warning')
        return redirect(url_for('main.my_bookings'))
    
    # Cek apakah handover record ada dan sudah lengkap
    handover = HandoverRecord.query.filter_by(booking_id=booking_id).first()
    if not handover or not handover.is_completed:
        flash('Belum ada Berita Acara Serah Terima dari admin.', 'warning')
        return redirect(url_for('main.my_bookings'))
    
    # Update handover record - user sudah terima
    handover.user_accepted_at = datetime.now()
    handover.is_completed = True
    
    # Update booking status ke active
    booking.status = 'active'
    db.session.commit()
    
    flash('Drone berhasil diterima! Selamat menggunakan.', 'success')
    return redirect(url_for('main.my_bookings'))


@main_bp.route('/booking/<int:booking_id>/handover')
@login_required
def view_handover(booking_id):
    """User lihat Berita Acara Serah Terima"""
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != current_user.id:
        flash('Anda tidak memiliki izin.', 'danger')
        return redirect(url_for('main.my_bookings'))
    
    handover = HandoverRecord.query.filter_by(booking_id=booking_id).first()
    
    # Parse JSON checklist
    equipment_list = json.loads(handover.checklist_equipment) if handover and handover.checklist_equipment else []
    condition_list = json.loads(handover.checklist_condition) if handover and handover.checklist_condition else []
    
    return render_template('user_handover_view.html', 
                         booking=booking, 
                         handover=handover,
                         equipment_list=equipment_list,
                         condition_list=condition_list)


@main_bp.route('/booking/<int:booking_id>/return-view')
@login_required
def view_return(booking_id):
    """User lihat Berita Acara Pengembalian"""
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.user_id != current_user.id:
        flash('Anda tidak memiliki izin.', 'danger')
        return redirect(url_for('main.my_bookings'))
    
    handover = HandoverRecord.query.filter_by(booking_id=booking_id).first()
    return_record = ReturnRecord.query.filter_by(booking_id=booking_id).first()
    
    # Parse JSON checklist
    equipment_list = json.loads(return_record.checklist_equipment) if return_record and return_record.checklist_equipment else []
    condition_list = json.loads(return_record.checklist_condition) if return_record and return_record.checklist_condition else []
    
    return render_template('user_return_view.html',
                         booking=booking,
                         handover=handover,
                         return_record=return_record,
                         equipment_list=equipment_list,
                         condition_list=condition_list)


@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/contact')
def contact():
    return render_template('contact.html')


# ============================================================
# API endpoint untuk cek ketersediaan (AJAX)
# ============================================================
@main_bp.route('/api/check-availability/<int:drone_id>')
def check_availability(drone_id):
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    drone = Drone.query.get_or_404(drone_id)

    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()
    except:
        return jsonify({'available': False, 'error': 'Invalid date'})

    conflicting = Booking.query.filter(
        Booking.drone_id == drone.id,
        Booking.status.in_(['pending', 'confirmed', 'active']),
        Booking.start_date <= end,
        Booking.end_date >= start
    ).count()

    available = conflicting < drone.stock
    total_days = (end - start).days + 1
    total_price = drone.daily_rate * total_days if total_days > 0 and available else 0

    return jsonify({
        'available': available,
        'total_days': max(0, total_days),
        'total_price': total_price,
        'daily_rate': drone.daily_rate,
        'deposit': drone.deposit,
        'stock_left': drone.stock - conflicting
    })
