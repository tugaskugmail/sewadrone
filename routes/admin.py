from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from datetime import date, datetime
from extensions import db
from models import User, Drone, Booking, HandoverRecord, ReturnRecord
from werkzeug.security import generate_password_hash
import json
import os
import tempfile
import base64

# ReportLab imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.platypus import KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Akses admin diperlukan.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.before_request
def check_admin():
    if not current_user.is_authenticated or not current_user.is_admin:
        if request.endpoint and request.endpoint.startswith('admin.'):
            flash('Akses admin diperlukan.', 'danger')
            return redirect(url_for('main.index'))


@admin_bp.route('/')
def dashboard():
    total_drones = Drone.query.count()
    total_users = User.query.count()
    active_bookings = Booking.query.filter(Booking.status.in_(['pending', 'confirmed', 'active'])).count()
    total_revenue = db.session.query(db.func.sum(Booking.total_price)).filter(Booking.status == 'completed').scalar() or 0
    today = date.today()

    todays_bookings = Booking.query.filter(
        Booking.start_date <= today,
        Booking.end_date >= today,
        Booking.status.in_(['confirmed', 'active'])
    ).count()

    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                         total_drones=total_drones,
                         total_users=total_users,
                         active_bookings=active_bookings,
                         total_revenue=total_revenue,
                         todays_bookings=todays_bookings,
                         recent_bookings=recent_bookings)


# ============================================================
# DRONES CRUD
# ============================================================
@admin_bp.route('/drones')
def drones():
    all_drones = Drone.query.order_by(Drone.created_at.desc()).all()
    return render_template('admin/drones.html', drones=all_drones)


@admin_bp.route('/drones/create', methods=['GET', 'POST'])
def drone_create():
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        model = request.form.get('model')
        description = request.form.get('description')
        specs = request.form.get('specs')
        daily_rate = request.form.get('daily_rate', type=int)
        deposit = request.form.get('deposit', type=int)
        stock = request.form.get('stock', type=int, default=1)
        category = request.form.get('category')

        # Handle file upload atau URL
        image_url = '/static/img/drone-placeholder.jpg'
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                import uuid, os
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in {'jpg', 'jpeg', 'png', 'webp', 'gif'}:
                    fname = f"drone_{uuid.uuid4().hex}.{ext}"
                    fpath = os.path.join(current_app.root_path, 'static', 'uploads', 'drones')
                    os.makedirs(fpath, exist_ok=True)
                    file.save(os.path.join(fpath, fname))
                    image_url = f"/static/uploads/drones/{fname}"
        if not image_url or image_url == '/static/img/drone-placeholder.jpg':
            url_input = request.form.get('image_url', '').strip()
            if url_input:
                image_url = url_input

        drone = Drone(
            name=name, brand=brand, model=model,
            description=description, specs=specs,
            daily_rate=daily_rate, deposit=deposit,
            stock=stock, category=category,
            image_url=image_url
        )
        db.session.add(drone)
        db.session.commit()
        flash(f'Drone "{name}" berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.drones'))

    return render_template('admin/drone_form.html', drone=None)


@admin_bp.route('/drones/<int:drone_id>/edit', methods=['GET', 'POST'])
def drone_edit(drone_id):
    drone = Drone.query.get_or_404(drone_id)
    if request.method == 'POST':
        drone.name = request.form.get('name')
        drone.brand = request.form.get('brand')
        drone.model = request.form.get('model')
        drone.description = request.form.get('description')
        drone.specs = request.form.get('specs')
        drone.daily_rate = request.form.get('daily_rate', type=int)
        drone.deposit = request.form.get('deposit', type=int)
        drone.stock = request.form.get('stock', type=int, default=1)
        drone.category = request.form.get('category')
        drone.is_available = request.form.get('is_available') == 'on'

        # Handle file upload atau URL
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename:
                import uuid, os
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in {'jpg', 'jpeg', 'png', 'webp', 'gif'}:
                    fname = f"drone_{uuid.uuid4().hex}.{ext}"
                    fpath = os.path.join(current_app.root_path, 'static', 'uploads', 'drones')
                    os.makedirs(fpath, exist_ok=True)
                    file.save(os.path.join(fpath, fname))
                    drone.image_url = f"/static/uploads/drones/{fname}"
        url_input = request.form.get('image_url', '').strip()
        if url_input and url_input != drone.image_url:
            drone.image_url = url_input

        db.session.commit()
        flash(f'Drone "{drone.name}" berhasil diperbarui!', 'success')
        return redirect(url_for('admin.drones'))

    return render_template('admin/drone_form.html', drone=drone)


@admin_bp.route('/drones/<int:drone_id>/delete', methods=['POST'])
def drone_delete(drone_id):
    drone = Drone.query.get_or_404(drone_id)
    db.session.delete(drone)
    db.session.commit()
    flash(f'Drone "{drone.name}" berhasil dihapus.', 'success')
    return redirect(url_for('admin.drones'))


@admin_bp.route('/drones/<int:drone_id>/serial', methods=['GET', 'POST'])
def drone_serial(drone_id):
    """Isi/edit serial number drone, remote, dan battery"""
    drone = Drone.query.get_or_404(drone_id)
    if request.method == 'POST':
        drone.serial_drone    = request.form.get('serial_drone', '').strip() or None
        drone.serial_remote   = request.form.get('serial_remote', '').strip() or None
        drone.serial_battery_1 = request.form.get('serial_battery_1', '').strip() or None
        drone.serial_battery_2 = request.form.get('serial_battery_2', '').strip() or None
        drone.serial_battery_3 = request.form.get('serial_battery_3', '').strip() or None
        drone.registration_number = request.form.get('registration_number', '').strip() or None
        db.session.commit()
        flash(f'Serial number & registrasi "{drone.name}" berhasil disimpan!', 'success')
        return redirect(url_for('admin.drones'))
    return render_template('admin/drone_serial.html', drone=drone)


@admin_bp.route('/report')
@login_required
def report():
    """Report Penghasilan — hanya superadmin"""
    if not current_user.is_superadmin:
        flash('Akses ditolak. Hanya Superadmin.', 'danger')
        return redirect(url_for('admin.dashboard'))

    from datetime import datetime, timedelta
    from sqlalchemy import func

    # Default range: bulan ini
    today = date.today()
    default_from = today.replace(day=1).strftime('%Y-%m-%d')
    default_to   = today.strftime('%Y-%m-%d')

    date_from_str = request.args.get('date_from', default_from)
    date_to_str   = request.args.get('date_to', default_to)

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to   = datetime.strptime(date_to_str,   '%Y-%m-%d').date()
    except ValueError:
        date_from = today.replace(day=1)
        date_to   = today

    # Query booking completed dalam range
    bookings = Booking.query.filter(
        Booking.status == 'completed',
        Booking.start_date >= date_from,
        Booking.start_date <= date_to
    ).order_by(Booking.start_date.desc()).all()

    # Summary stats
    total_revenue   = sum(b.total_price for b in bookings)
    total_bookings  = len(bookings)
    total_days      = sum(b.total_days for b in bookings)
    avg_per_booking = total_revenue // total_bookings if total_bookings else 0

    # Breakdown per drone
    drone_stats = {}
    for b in bookings:
        name = b.drone.name
        if name not in drone_stats:
            drone_stats[name] = {'count': 0, 'revenue': 0, 'days': 0}
        drone_stats[name]['count']   += 1
        drone_stats[name]['revenue'] += b.total_price
        drone_stats[name]['days']    += b.total_days
    drone_stats = sorted(drone_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)

    # Breakdown per user
    user_stats = {}
    for b in bookings:
        name = b.user.full_name
        if name not in user_stats:
            user_stats[name] = {'count': 0, 'revenue': 0}
        user_stats[name]['count']   += 1
        user_stats[name]['revenue'] += b.total_price
    user_stats = sorted(user_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)

    # Date shortcuts untuk template
    from datetime import datetime
    first_day_this_month  = today.replace(day=1)
    first_day_last_month  = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_day_last_month   = today.replace(day=1) - timedelta(days=1)

    return render_template('admin/report.html',
        bookings=bookings,
        date_from=date_from_str,
        date_to=date_to_str,
        total_revenue=total_revenue,
        total_bookings=total_bookings,
        total_days=total_days,
        avg_per_booking=avg_per_booking,
        drone_stats=drone_stats,
        user_stats=user_stats,
        today=today.strftime('%Y-%m-%d'),
        today_month_start=first_day_this_month.strftime('%Y-%m-%d'),
        last_month_start=first_day_last_month.strftime('%Y-%m-%d'),
        last_month_end=last_day_last_month.strftime('%Y-%m-%d'),
        year_start=today.strftime('%Y-01-01'),
    )


@admin_bp.route('/report/pdf')
@login_required
def report_pdf():
    """Cetak Report Penghasilan ke PDF — hanya superadmin"""
    if not current_user.is_superadmin:
        flash('Akses ditolak. Hanya Superadmin.', 'danger')
        return redirect(url_for('admin.dashboard'))

    from datetime import datetime, timedelta
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from io import BytesIO

    today = date.today()
    date_from_str = request.args.get('date_from', today.replace(day=1).strftime('%Y-%m-%d'))
    date_to_str   = request.args.get('date_to',   today.strftime('%Y-%m-%d'))

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        date_to   = datetime.strptime(date_to_str,   '%Y-%m-%d').date()
    except ValueError:
        date_from = today.replace(day=1)
        date_to   = today

    bookings = Booking.query.filter(
        Booking.status == 'completed',
        Booking.start_date >= date_from,
        Booking.start_date <= date_to
    ).order_by(Booking.start_date.desc()).all()

    total_revenue   = sum(b.total_price for b in bookings)
    total_bookings  = len(bookings)
    total_days      = sum(b.total_days for b in bookings)
    avg_per_booking = total_revenue // total_bookings if total_bookings else 0

    drone_stats = {}
    for b in bookings:
        n = b.drone.name
        if n not in drone_stats:
            drone_stats[n] = {'count': 0, 'revenue': 0, 'days': 0}
        drone_stats[n]['count']   += 1
        drone_stats[n]['revenue'] += b.total_price
        drone_stats[n]['days']    += b.total_days
    drone_stats = sorted(drone_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)

    # ── Build PDF ────────────────────────────────────────────
    buf    = BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm,  bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    W      = A4[0] - 3*cm

    title_s  = ParagraphStyle('T',  parent=styles['Title'],  fontSize=14, alignment=TA_CENTER,
                               textColor=colors.HexColor('#003366'), spaceAfter=2)
    sub_s    = ParagraphStyle('S',  parent=styles['Normal'], fontSize=10, alignment=TA_CENTER,
                               textColor=colors.grey, spaceAfter=10)
    head_s   = ParagraphStyle('H',  parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold',
                               textColor=colors.HexColor('#003366'), spaceBefore=10, spaceAfter=4)
    normal_s = ParagraphStyle('N',  parent=styles['Normal'], fontSize=9)
    right_s  = ParagraphStyle('R',  parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)

    def tbl_style(header_color='#003366'):
        return TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), colors.HexColor(header_color)),
            ('TEXTCOLOR',     (0,0), (-1,0), colors.white),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [colors.white, colors.HexColor('#f0f4ff')]),
            ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#cccccc')),
            ('LEFTPADDING',   (0,0), (-1,-1), 5),
            ('RIGHTPADDING',  (0,0), (-1,-1), 5),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ])

    story = []

    # Header
    story.append(Paragraph('REPORT PENGHASILAN', title_s))
    story.append(Paragraph('SewaDroneCilegonBanten', sub_s))
    story.append(Paragraph(f'Periode: {date_from_str} s/d {date_to_str}  |  Dicetak: {today.strftime("%d/%m/%Y")}', sub_s))
    story.append(HRFlowable(width=W, color=colors.HexColor('#003366'), thickness=1.5))
    story.append(Spacer(1, 0.3*cm))

    # Summary
    story.append(Paragraph('RINGKASAN', head_s))
    summary_data = [
        ['Keterangan', 'Nilai'],
        ['Total Penghasilan',    f'Rp {total_revenue:,}'],
        ['Total Transaksi',      f'{total_bookings} booking'],
        ['Total Hari Sewa',      f'{total_days} hari'],
        ['Rata-rata per Booking', f'Rp {avg_per_booking:,}'],
    ]
    t = Table(summary_data, colWidths=[8*cm, W-8*cm])
    t.setStyle(tbl_style())
    story.append(t)
    story.append(Spacer(1, 0.3*cm))

    # Breakdown per Drone
    if drone_stats:
        story.append(Paragraph('BREAKDOWN PER DRONE', head_s))
        drone_data = [['Drone', 'Booking', 'Hari', 'Revenue', '%']]
        for name, s in drone_stats:
            pct = f"{s['revenue']/total_revenue*100:.1f}%" if total_revenue else '0%'
            drone_data.append([name[:30], str(s['count']), str(s['days']),
                                f"Rp {s['revenue']:,}", pct])
        drone_data.append(['TOTAL', str(total_bookings), str(total_days),
                            f'Rp {total_revenue:,}', '100%'])
        t2 = Table(drone_data, colWidths=[7*cm, 1.8*cm, 1.8*cm, 5*cm, 2*cm])
        st2 = tbl_style()
        st2.add('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
        st2.add('BACKGROUND',(0,-1),(-1,-1), colors.HexColor('#e8f0fe'))
        t2.setStyle(st2)
        story.append(t2)
        story.append(Spacer(1, 0.3*cm))

    # Detail Transaksi
    story.append(Paragraph('DETAIL TRANSAKSI', head_s))
    if bookings:
        detail_data = [['#', 'Penyewa', 'Drone', 'Tanggal', 'Hari', 'Total']]
        for b in bookings:
            detail_data.append([
                str(b.id),
                b.user.full_name[:20],
                b.drone.name[:20],
                b.start_date.strftime('%d/%m/%y'),
                str(b.total_days),
                f'Rp {b.total_price:,}',
            ])
        detail_data.append(['', '', '', '', 'TOTAL', f'Rp {total_revenue:,}'])
        t3 = Table(detail_data, colWidths=[1*cm, 4.5*cm, 4.5*cm, 2.5*cm, 1.2*cm, 4*cm])
        st3 = tbl_style()
        st3.add('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold')
        st3.add('BACKGROUND',(0,-1),(-1,-1), colors.HexColor('#e8f0fe'))
        t3.setStyle(st3)
        story.append(t3)
    else:
        story.append(Paragraph('<i>Tidak ada transaksi dalam periode ini.</i>', normal_s))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width=W, color=colors.grey, thickness=0.5))
    story.append(Paragraph(f'Dicetak oleh: {current_user.full_name}  |  {today.strftime("%d %B %Y")}  |  SewaDroneCilegonBanten', sub_s))

    doc.build(story)
    buf.seek(0)
    fname = f"report_{date_from_str}_{date_to_str}.pdf"
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=False,
                     download_name=fname)



@admin_bp.route('/bookings')
def bookings():
    status = request.args.get('status')
    sort   = request.args.get('sort', 'created_at')
    order  = request.args.get('order', 'desc')

    query = Booking.query
    if status:
        query = query.filter_by(status=status)

    # Sort mapping
    sort_map = {
        'id':          Booking.id,
        'user':        Booking.user_id,
        'drone':       Booking.drone_id,
        'start_date':  Booking.start_date,
        'total_days':  Booking.total_days,
        'total_price': Booking.total_price,
        'status':      Booking.status,
        'created_at':  Booking.created_at,
    }
    col = sort_map.get(sort, Booking.created_at)
    all_bookings = query.order_by(col.asc() if order == 'asc' else col.desc()).all()
    return render_template('admin/bookings.html', bookings=all_bookings,
                           current_sort=sort, current_order=order)


@admin_bp.route('/bookings/<int:booking_id>/delete', methods=['POST'])
def booking_delete(booking_id):
    """Hapus booking — hanya superadmin"""
    if not current_user.is_superadmin:
        flash('Akses ditolak. Hanya Superadmin yang bisa menghapus transaksi.', 'danger')
        return redirect(url_for('admin.bookings'))
    
    booking = Booking.query.get_or_404(booking_id)
    
    # Hapus handover & return record dulu
    HandoverRecord.query.filter_by(booking_id=booking_id).delete()
    ReturnRecord.query.filter_by(booking_id=booking_id).delete()
    db.session.delete(booking)
    db.session.commit()
    
    flash(f'Booking #{booking_id} berhasil dihapus.', 'success')
    return redirect(url_for('admin.bookings'))



@admin_bp.route('/bookings/<int:booking_id>/update-status', methods=['POST'])
def booking_update_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status in ['confirmed', 'active', 'completed', 'cancelled']:
        booking.status = new_status
        db.session.commit()
        flash(f'Status booking #{booking.id} diubah ke "{booking.status_label}".', 'success')
    return redirect(url_for('admin.bookings'))


# ============================================================
# BERITA ACARA - SERAH TERIMA DRONE
# ============================================================

@admin_bp.route('/bookings/<int:booking_id>/handover', methods=['GET', 'POST'])
def handover_create(booking_id):
    """Form Berita Acara Serah Terima (Admin -> User)"""
    booking = Booking.query.get_or_404(booking_id)
    
    # Cek apakah booking sudah confirmed atau active (allow edit BAST)
    if booking.status not in ['confirmed', 'active', 'completed']:
        flash('Booking harus dalam status "Dikonfirmasi" atau "Aktif" untuk mengakses BAST.', 'warning')
        return redirect(url_for('admin.bookings'))
    
    # Cek apakah sudah ada handover record (allow re-open for PDF)
    existing = HandoverRecord.query.filter_by(booking_id=booking_id).first()
    
    if request.method == 'GET' and not existing:
        pass  # Show empty form
    elif request.method == 'GET' and existing:
        pass  # Show pre-filled form with PDF button
    
    if request.method == 'POST':
        # Ambil data dari form
        serial_drone = request.form.get('serial_drone', '')
        serial_remote = request.form.get('serial_remote', '')
        serial_battery_1 = request.form.get('serial_battery_1', '')
        serial_battery_2 = request.form.get('serial_battery_2', '')
        serial_battery_3 = request.form.get('serial_battery_3', '')
        handover_time_out = request.form.get('handover_time_out', '')
        payment_status = request.form.get('payment_status', 'pending')
        
        # Checklist kelengkapan (JSON)
        equipment_items = [
            'drone_body', 'remote_controller', 'battery', 'charger', 
            'usb_cable', 'nd_filter', 'sd_card', 'propeller', 'hardcase', 'manual'
        ]
        checklist_equipment = []
        for item in equipment_items:
            qty = request.form.get(f'eq_{item}_qty', '0')
            condition = request.form.get(f'eq_{item}_condition', '')
            notes = request.form.get(f'eq_{item}_notes', '')
            checklist_equipment.append({
                'item': item.replace('_', ' ').title(),
                'qty': int(qty) if qty.isdigit() else 0,
                'condition': condition,
                'notes': notes
            })
        
        # Checklist kondisi (JSON)
        condition_items = [
            'body_frame', 'gimbal_camera', 'obstacle_sensor', 
            'motor_propeller', 'remote_connection', 'battery_condition', 'ready_to_fly'
        ]
        checklist_condition = []
        for item in condition_items:
            status = request.form.get(f'cond_{item}', '')
            notes = request.form.get(f'cond_{item}_notes', '')
            checklist_condition.append({
                'item': item.replace('_', ' ').title(),
                'status': status,
                'notes': notes
            })
        
        notes_damage = request.form.get('notes_damage', '')
        photo_out_attached = request.form.get('photo_out_attached') == 'on'

        # Handle upload multiple foto BAST keluar
        photo_out_urls = None
        if 'photo_out_file' in request.files:
            files = request.files.getlist('photo_out_file')
            uploaded = []
            for file in files:
                if file and file.filename:
                    ext = file.filename.rsplit('.', 1)[-1].lower()
                    if ext in {'jpg', 'jpeg', 'png', 'webp'}:
                        import uuid, os
                        fname = f"handover_{uuid.uuid4().hex}.{ext}"
                        fpath = os.path.join(current_app.root_path, 'static', 'uploads', 'handover')
                        os.makedirs(fpath, exist_ok=True)
                        file.save(os.path.join(fpath, fname))
                        uploaded.append(f"/static/uploads/handover/{fname}")
            if uploaded:
                # Merge dengan foto yang sudah ada
                existing_urls = json.loads(existing.photo_out_urls) if existing and existing.photo_out_urls else []
                all_urls = existing_urls + uploaded
                photo_out_urls = json.dumps(all_urls)
                photo_out_attached = True
        # Signature otomatis dari database (tidak perlu tanda tangan manual)
        # Checkbox persetujuan menampilkan tanda tangan yang tersimpan
        admin_signature = current_user.signature if request.form.get('admin_approve') == '1' else None
        user_signature  = booking.user.signature if request.form.get('user_approve') == '1' else None
        
        # Generate nomor dokumen
        today = datetime.now()
        doc_number = f"BAST-{booking_id:04d}/{today.strftime('%m')}/{today.year}"
        
        if existing:
            # Update existing
            existing.serial_drone = serial_drone
            existing.serial_remote = serial_remote
            existing.serial_battery_1 = serial_battery_1
            existing.serial_battery_2 = serial_battery_2
            existing.serial_battery_3 = serial_battery_3
            existing.handover_time_out = handover_time_out
            existing.payment_status = payment_status
            existing.checklist_equipment = json.dumps(checklist_equipment)
            existing.checklist_condition = json.dumps(checklist_condition)
            existing.notes_damage = notes_damage
            existing.photo_out_attached = photo_out_attached
            if photo_out_urls:
                existing.photo_out_urls = photo_out_urls
            existing.document_number = doc_number
            if admin_signature: existing.admin_signature = admin_signature
            if user_signature:  existing.user_signature  = user_signature
        else:
            # Create new
            handover = HandoverRecord(
                booking_id=booking_id,
                document_number=doc_number,
                serial_drone=serial_drone,
                serial_remote=serial_remote,
                serial_battery_1=serial_battery_1,
                serial_battery_2=serial_battery_2,
                serial_battery_3=serial_battery_3,
                handover_time_out=handover_time_out,
                payment_status=payment_status,
                checklist_equipment=json.dumps(checklist_equipment),
                checklist_condition=json.dumps(checklist_condition),
                notes_damage=notes_damage,
                photo_out_attached=photo_out_attached,
                admin_signature=admin_signature,
                user_signature=user_signature,
                photo_out_urls=photo_out_urls,
                is_completed=True  # Admin sudah isi, tinggal user konfirmasi
            )
            db.session.add(handover)
        
        # Booking tetap 'confirmed' — user harus klik "Terima Drone" untuk aktifkan
        db.session.commit()
        
        flash('Berita Acara Serah Terima berhasil disimpan. Menunggu konfirmasi penerimaan dari user.', 'success')
        return redirect(url_for('admin.bookings'))
    
    return render_template('admin/handover_form.html', booking=booking, handover=existing)


@admin_bp.route('/bookings/<int:booking_id>/return', methods=['GET', 'POST'])
def return_create(booking_id):
    """Form Berita Acara Pengembalian (User -> Admin)"""
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.status != 'active':
        flash('Booking harus dalam status "Aktif" untuk pengembalian.', 'warning')
        return redirect(url_for('admin.bookings'))
    
    existing = ReturnRecord.query.filter_by(booking_id=booking_id).first()
    if existing and existing.is_completed:
        flash('Berita Acara Pengembalian sudah selesai.', 'info')
        return redirect(url_for('admin.bookings'))
    
    handover = HandoverRecord.query.filter_by(booking_id=booking_id).first()
    
    if request.method == 'POST':
        return_time_in = request.form.get('return_time_in', '')
        
        # Checklist kelengkapan saat kembali
        equipment_items = [
            'drone_body', 'remote_controller', 'battery', 'charger', 
            'usb_cable', 'nd_filter', 'sd_card', 'propeller', 'hardcase', 'manual'
        ]
        checklist_equipment = []
        for item in equipment_items:
            qty = request.form.get(f'eq_{item}_qty', '0')
            condition = request.form.get(f'eq_{item}_condition', '')
            notes = request.form.get(f'eq_{item}_notes', '')
            checklist_equipment.append({
                'item': item.replace('_', ' ').title(),
                'qty': int(qty) if qty.isdigit() else 0,
                'condition': condition,
                'notes': notes
            })
        
        # Checklist kondisi saat kembali
        condition_items = [
            'body_frame', 'gimbal_camera', 'obstacle_sensor', 
            'motor_propeller', 'remote_connection', 'battery_condition', 'ready_to_fly'
        ]
        checklist_condition = []
        for item in condition_items:
            status = request.form.get(f'cond_{item}', '')
            notes = request.form.get(f'cond_{item}_notes', '')
            checklist_condition.append({
                'item': item.replace('_', ' ').title(),
                'status': status,
                'notes': notes
            })
        
        notes_damage = request.form.get('notes_damage', '')
        damage_cost = request.form.get('damage_cost', type=int, default=0)
        damage_description = request.form.get('damage_description', '')
        deposit_returned = request.form.get('deposit_returned') == 'on'
        deposit_deducted = request.form.get('deposit_deducted', type=int, default=0)
        photo_return_attached = request.form.get('photo_return_attached') == 'on'
        # Signature otomatis dari database (tidak perlu tanda tangan manual)
        # Checkbox persetujuan menampilkan tanda tangan yang tersimpan
        admin_signature = current_user.signature if request.form.get('admin_approve') == '1' else None
        user_signature  = booking.user.signature if request.form.get('user_approve') == '1' else None

        # Handle upload foto pengembalian
        photo_return_url = None
        if 'photo_return_file' in request.files:
            files = request.files.getlist('photo_return_file')
            uploaded = []
            for file in files:
                if file and file.filename:
                    import uuid, os
                    ext = file.filename.rsplit('.', 1)[-1].lower()
                    if ext in {'jpg', 'jpeg', 'png', 'webp'}:
                        fname = f"return_{uuid.uuid4().hex}.{ext}"
                        fpath = os.path.join(current_app.root_path, 'static', 'uploads', 'returns')
                        os.makedirs(fpath, exist_ok=True)
                        file.save(os.path.join(fpath, fname))
                        uploaded.append(f"/static/uploads/returns/{fname}")
            if uploaded:
                photo_return_url = ','.join(uploaded)
                photo_return_attached = True
        
        if existing:
            existing.return_time_in = return_time_in
            existing.checklist_equipment = json.dumps(checklist_equipment)
            existing.checklist_condition = json.dumps(checklist_condition)
            existing.notes_damage = notes_damage
            existing.damage_cost = damage_cost
            existing.damage_description = damage_description
            existing.deposit_returned = deposit_returned
            existing.deposit_deducted = deposit_deducted
            existing.photo_return_attached = photo_return_attached
            if photo_return_url:
                existing.photo_return_url = photo_return_url
                # Merge foto baru ke JSON array
                existing_urls = json.loads(existing.photo_return_urls) if existing.photo_return_urls else []
                new_urls = photo_return_url.split(',') if photo_return_url else []
                existing.photo_return_urls = json.dumps(existing_urls + new_urls)
            if admin_signature: existing.admin_signature = admin_signature
            if user_signature:  existing.user_signature  = user_signature
            existing.is_completed = True
        else:
            return_record = ReturnRecord(
                booking_id=booking_id,
                return_time_in=return_time_in,
                checklist_equipment=json.dumps(checklist_equipment),
                checklist_condition=json.dumps(checklist_condition),
                notes_damage=notes_damage,
                damage_cost=damage_cost,
                damage_description=damage_description,
                deposit_returned=deposit_returned,
                deposit_deducted=deposit_deducted,
                photo_return_attached=photo_return_attached,
                admin_signature=admin_signature,
                user_signature=user_signature,
                is_completed=True
            )
            db.session.add(return_record)
        
        # Update booking status ke completed
        booking.status = 'completed'
        db.session.commit()
        
        flash('Berita Acara Pengembalian berhasil disimpan. Booking selesai.', 'success')
        return redirect(url_for('admin.bookings'))
    
    return render_template('admin/return_form.html', booking=booking, handover=handover, return_record=existing)


# ============================================================
# USERS MANAGEMENT
# ============================================================
@admin_bp.route('/users')
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
def user_create():
    """Tambah user manual dari admin"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        nik = request.form.get('nik')
        address = request.form.get('address')
        is_admin = request.form.get('is_admin') == 'on'

        # Validasi
        errors = []
        if not username or not email or not password or not full_name:
            errors.append('Username, Email, Password, dan Nama wajib diisi.')
        
        if User.query.filter_by(username=username).first():
            errors.append('Username sudah digunakan.')
        if User.query.filter_by(email=email).first():
            errors.append('Email sudah terdaftar.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('admin/user_form.html', user=None)

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            full_name=full_name,
            phone=phone,
            nik=nik,
            address=address,
            is_admin=is_admin,
            ktp_image=None,
            signature=None
        )
        db.session.add(user)
        db.session.commit()
        
        flash(f'User "{full_name}" berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', user=None)


@admin_bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
def user_toggle_role(user_id):
    """Ubah role user (admin ↔ user) — hanya superadmin bisa ubah role"""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('Tidak dapat mengubah role sendiri!', 'danger')
        return redirect(url_for('admin.users'))
    
    # Superadmin tidak bisa di-toggle oleh admin biasa
    if user.is_superadmin and not current_user.is_superadmin:
        flash('Tidak dapat mengubah role Superadmin!', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = 'Admin' if user.is_admin else 'User'
    flash(f'Role {user.username} diubah menjadi {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle-superadmin', methods=['POST'])
def user_toggle_superadmin(user_id):
    """Toggle superadmin — hanya superadmin yang bisa"""
    if not current_user.is_superadmin:
        flash('Akses ditolak. Hanya Superadmin.', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Tidak dapat mengubah role sendiri!', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_superadmin = not user.is_superadmin
    if user.is_superadmin:
        user.is_admin = True  # Superadmin otomatis admin
    db.session.commit()
    
    status = 'Superadmin' if user.is_superadmin else 'Admin'
    flash(f'{user.username} diubah menjadi {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def user_edit(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name)
        user.phone = request.form.get('phone', user.phone)
        user.nik = request.form.get('nik', user.nik)
        user.address = request.form.get('address', user.address)
        
        # Ganti password kalau diisi
        new_password = request.form.get('new_password')
        if new_password and len(new_password) >= 6:
            user.password = generate_password_hash(new_password)

        # Update signature kalau ada yang baru digambar
        new_sig = request.form.get('signature', '').strip()
        if new_sig and new_sig.startswith('data:image'):
            user.signature = new_sig
        
        db.session.commit()
        flash(f'User "{user.full_name}" berhasil diperbarui!', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=user)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
def user_delete(user_id):
    """Hapus user"""
    user = User.query.get_or_404(user_id)
    
    # Jangan hapus diri sendiri
    if user.id == current_user.id:
        flash('Tidak dapat menghapus akun sendiri!', 'danger')
        return redirect(url_for('admin.users'))
    
    # Jangan hapus jika ada booking aktif
    active_bookings = Booking.query.filter(
        Booking.user_id == user.id,
        Booking.status.in_(['pending', 'confirmed', 'active'])
    ).count()
    
    if active_bookings > 0:
        flash(f'Tidak dapat menghapus user dengan {active_bookings} booking aktif!', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{username}" berhasil dihapus.', 'success')
    return redirect(url_for('admin.users'))


# ============================================================
# PDF EXPORT
# ============================================================

def _sig_image(b64_data, max_w=7*cm, max_h=2.5*cm):
    """Convert base64 PNG signature string to a ReportLab Image, or return None."""
    if not b64_data:
        return None
    try:
        # strip data-url prefix if present
        if ',' in b64_data:
            b64_data = b64_data.split(',', 1)[1]
        img_bytes = base64.b64decode(b64_data)
        
        # Validate & convert via PIL to ensure clean PNG for ReportLab
        from PIL import Image as PILImage
        import io
        pil_img = PILImage.open(io.BytesIO(img_bytes))
        
        # Convert to RGBA then RGB to avoid broken data stream issues
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            bg = PILImage.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode == 'P':
                pil_img = pil_img.convert('RGBA')
            if pil_img.mode in ('RGBA', 'LA'):
                bg.paste(pil_img, mask=pil_img.split()[-1])
            pil_img = bg
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        
        # Must be at least 10x10 to render
        if pil_img.width < 10 or pil_img.height < 10:
            return None
        
        buf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        pil_img.save(buf.name, 'PNG')
        buf.close()
        img = Image(buf.name, width=max_w, height=max_h)
        img._tmp_path = buf.name
        return img
    except Exception:
        return None


def _build_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Title'],
        fontSize=14, leading=18, alignment=TA_CENTER,
        spaceAfter=4, textColor=colors.HexColor('#003366')
    )
    sub_style = ParagraphStyle(
        'DocSub', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, spaceAfter=12,
        textColor=colors.HexColor('#555555')
    )
    heading_style = ParagraphStyle(
        'SecHead', parent=styles['Normal'],
        fontSize=11, leading=14, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#003366'), spaceBefore=10, spaceAfter=4
    )
    normal_style = ParagraphStyle(
        'DocNormal', parent=styles['Normal'],
        fontSize=9, leading=13
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER,
        textColor=colors.grey, spaceBefore=6
    )
    return title_style, sub_style, heading_style, normal_style, footer_style


def _checklist_table(checklist_json, normal_style):
    """Parse a JSON checklist (list of dicts) and return a ReportLab Table flowable."""
    try:
        items = json.loads(checklist_json) if checklist_json else []
    except Exception:
        items = []
    if not items:
        return Paragraph('<i>— tidak ada data —</i>', normal_style)

    tbl_data = [['Item', 'Qty', 'Kondisi', 'Catatan']]
    for row in items:
        if isinstance(row, dict):
            item  = row.get('item', '-')
            qty   = str(row.get('qty', '1'))
            cond  = row.get('condition', row.get('status', '-'))
            notes = row.get('notes', '')
        else:
            item, qty, cond, notes = str(row), '1', '-', ''
        tbl_data.append([item, qty, cond or '-', notes or ''])

    tbl = Table(tbl_data, colWidths=[7*cm, 1.5*cm, 3.5*cm, 4*cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')]),
        ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LEFTPADDING',  (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))
    return tbl


@admin_bp.route('/bookings/<int:booking_id>/bast-pdf')
def bast_pdf(booking_id):
    """Generate PDF Berita Acara Serah Terima."""
    booking  = Booking.query.get_or_404(booking_id)
    handover = HandoverRecord.query.filter_by(booking_id=booking_id).first()

    title_style, sub_style, heading_style, normal_style, footer_style = _build_styles()

    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    story = []

    # ── Header ──────────────────────────────────────────────
    story.append(Paragraph('BERITA ACARA SERAH TERIMA DRONE', title_style))
    story.append(Paragraph('SewaDroneCilegonBanten', sub_style))
    story.append(HRFlowable(width='100%', thickness=1.5,
                             color=colors.HexColor('#003366')))
    story.append(Spacer(1, 0.3*cm))

    # ── Info booking ────────────────────────────────────────
    tanggal_bast = ''
    if handover and handover.handover_time_out:
        tanggal_bast = str(handover.handover_time_out)
    elif booking.start_date:
        tanggal_bast = str(booking.start_date)

    info_data = [
        ['No. Booking', f'#{booking.id}'],
        ['Tanggal BAST', tanggal_bast or '-'],
        ['Status Pembayaran',
         (handover.payment_status if handover and handover.payment_status else '-')],
    ]
    info_tbl = Table(info_data, colWidths=[5*cm, 11*cm])
    info_tbl.setStyle(TableStyle([
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Data penyewa ────────────────────────────────────────
    story.append(Paragraph('DATA PENYEWA', heading_style))
    u = booking.user
    penyewa_data = [
        ['Nama Lengkap', u.full_name or '-'],
        ['NIK',          u.nik or '-'],
        ['No. HP',       u.phone or '-'],
        ['Alamat',       u.address or '-'],
    ]
    penyewa_tbl = Table(penyewa_data, colWidths=[5*cm, 11*cm])
    penyewa_tbl.setStyle(TableStyle([
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND',(0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID',      (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))
    story.append(penyewa_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── Data drone ──────────────────────────────────────────
    story.append(Paragraph('DATA DRONE', heading_style))
    d = booking.drone
    drone_data = [
        ['Nama Drone',      d.name or '-'],
        ['Merk/Brand',      d.brand or '-'],
        ['No. Registrasi',  d.registration_number or '-'],
        ['Serial Drone',    (handover.serial_drone if handover and handover.serial_drone
                             else (d.serial_drone or '-'))],
        ['Serial Remote',   (handover.serial_remote if handover and handover.serial_remote
                             else (d.serial_remote or '-'))],
        ['Serial Baterai 1', (handover.serial_battery_1 if handover and handover.serial_battery_1 else '-')],
        ['Serial Baterai 2', (handover.serial_battery_2 if handover and handover.serial_battery_2 else '-')],
        ['Serial Baterai 3', (handover.serial_battery_3 if handover and handover.serial_battery_3 else '-')],
        ['Tanggal Sewa',    f'{booking.start_date} s/d {booking.end_date}'],
        ['Total Biaya',     f'Rp {booking.total_price:,}'],
    ]
    drone_tbl = Table(drone_data, colWidths=[5*cm, 11*cm])
    drone_tbl.setStyle(TableStyle([
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND',(0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID',      (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))
    story.append(drone_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── Checklist kelengkapan ───────────────────────────────
    if handover:
        story.append(Paragraph('CHECKLIST KELENGKAPAN', heading_style))
        story.append(_checklist_table(handover.checklist_equipment, normal_style))
        story.append(Spacer(1, 0.3*cm))

        story.append(Paragraph('CHECKLIST KONDISI', heading_style))
        story.append(_checklist_table(handover.checklist_condition, normal_style))
        story.append(Spacer(1, 0.4*cm))

    # ── Tanda tangan ────────────────────────────────────────
    story.append(Paragraph('TANDA TANGAN', heading_style))

    admin_sig_img  = _sig_image(handover.admin_signature  if handover else None)
    user_sig_img   = _sig_image(handover.user_signature   if handover else None)

    def sig_cell(img):
        return img if img else Paragraph(
            '<br/><br/>__________________________', normal_style)

    sig_tbl = Table(
        [['Admin / Pengelola', 'Penyewa'],
         [sig_cell(admin_sig_img), sig_cell(user_sig_img)]],
        colWidths=[8*cm, 8*cm]
    )
    sig_tbl.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX',        (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('INNERGRID',  (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ROWHEIGHT',  (0, 1), (-1, 1), 2.8*cm),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Footer ──────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=colors.HexColor('#cccccc')))
    story.append(Paragraph(
        f'SewaDroneCilegonBanten — Dicetak: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        footer_style
    ))

    doc.build(story)

    # cleanup temp signature images
    for img in [admin_sig_img, user_sig_img]:
        if img and hasattr(img, '_tmp_path'):
            try:
                os.unlink(img._tmp_path)
            except Exception:
                pass

    fname = f'BAST_Booking{booking_id}_{booking.drone.name.replace(" ", "_")}.pdf'
    return send_file(
        tmp.name,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=fname
    )


@admin_bp.route('/bookings/<int:booking_id>/return-pdf')
def return_pdf(booking_id):
    """Generate PDF Berita Acara Pengembalian."""
    booking       = Booking.query.get_or_404(booking_id)
    return_record = ReturnRecord.query.filter_by(booking_id=booking_id).first()

    title_style, sub_style, heading_style, normal_style, footer_style = _build_styles()

    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    doc = SimpleDocTemplate(
        tmp.name, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    story = []

    # ── Header ──────────────────────────────────────────────
    story.append(Paragraph('BERITA ACARA PENGEMBALIAN DRONE', title_style))
    story.append(Paragraph('SewaDroneCilegonBanten', sub_style))
    story.append(HRFlowable(width='100%', thickness=1.5,
                             color=colors.HexColor('#006633')))
    story.append(Spacer(1, 0.3*cm))

    # ── Info booking ────────────────────────────────────────
    tanggal_kembali = ''
    if return_record and return_record.return_time_in:
        tanggal_kembali = str(return_record.return_time_in)
    elif booking.end_date:
        tanggal_kembali = str(booking.end_date)

    info_data = [
        ['No. Booking',    f'#{booking.id}'],
        ['Tanggal Kembali', tanggal_kembali or '-'],
        ['Status Booking',  booking.status or '-'],
    ]
    info_tbl = Table(info_data, colWidths=[5*cm, 11*cm])
    info_tbl.setStyle(TableStyle([
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Data penyewa ────────────────────────────────────────
    story.append(Paragraph('DATA PENYEWA', heading_style))
    u = booking.user
    penyewa_data = [
        ['Nama Lengkap', u.full_name or '-'],
        ['No. HP',       u.phone or '-'],
    ]
    penyewa_tbl = Table(penyewa_data, colWidths=[5*cm, 11*cm])
    penyewa_tbl.setStyle(TableStyle([
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND',(0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID',      (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))
    story.append(penyewa_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── Data drone & sewa ───────────────────────────────────
    story.append(Paragraph('DATA SEWA', heading_style))
    d = booking.drone
    sewa_data = [
        ['Drone',         d.name or '-'],
        ['Merk/Brand',    d.brand or '-'],
        ['No. Registrasi', d.registration_number or '-'],
        ['Tanggal Sewa',  f'{booking.start_date} s/d {booking.end_date}'],
        ['Total Biaya',   f'Rp {booking.total_price:,}'],
    ]
    sewa_tbl = Table(sewa_data, colWidths=[5*cm, 11*cm])
    sewa_tbl.setStyle(TableStyle([
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND',(0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID',      (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
    ]))
    story.append(sewa_tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── Detail pengembalian ─────────────────────────────────
    if return_record:
        story.append(Paragraph('DETAIL PENGEMBALIAN', heading_style))
        detail_data = [
            ['Catatan Kerusakan',
             return_record.notes_damage or '-'],
            ['Deskripsi Kerusakan',
             return_record.damage_description or '-'],
            ['Biaya Kerusakan',
             f'Rp {return_record.damage_cost:,}' if return_record.damage_cost else 'Rp 0'],
            ['Deposit Dipotong',
             f'Rp {return_record.deposit_deducted:,}' if return_record.deposit_deducted else 'Rp 0'],
            ['Deposit Dikembalikan',
             'Ya' if return_record.deposit_returned else 'Tidak'],
        ]
        detail_tbl = Table(detail_data, colWidths=[5*cm, 11*cm])
        detail_tbl.setStyle(TableStyle([
            ('FONTSIZE',  (0, 0), (-1, -1), 9),
            ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND',(0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID',      (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
            ('LEFTPADDING',  (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        story.append(detail_tbl)
        story.append(Spacer(1, 0.3*cm))

        # Checklist kondisi pengembalian
        if return_record.checklist_condition:
            story.append(Paragraph('CHECKLIST KONDISI PENGEMBALIAN', heading_style))
            story.append(_checklist_table(return_record.checklist_condition, normal_style))
            story.append(Spacer(1, 0.3*cm))

        if return_record.checklist_equipment:
            story.append(Paragraph('CHECKLIST KELENGKAPAN PENGEMBALIAN', heading_style))
            story.append(_checklist_table(return_record.checklist_equipment, normal_style))
            story.append(Spacer(1, 0.3*cm))

    # ── Tanda tangan ────────────────────────────────────────
    story.append(Paragraph('TANDA TANGAN', heading_style))

    admin_sig_img = _sig_image(return_record.admin_signature if return_record else None)
    user_sig_img  = _sig_image(return_record.user_signature  if return_record else None)

    def sig_cell(img):
        return img if img else Paragraph(
            '<br/><br/>__________________________', normal_style)

    sig_tbl = Table(
        [['Admin / Pengelola', 'Penyewa'],
         [sig_cell(admin_sig_img), sig_cell(user_sig_img)]],
        colWidths=[8*cm, 8*cm]
    )
    sig_tbl.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX',        (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('INNERGRID',  (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ROWHEIGHT',  (0, 1), (-1, 1), 2.8*cm),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Footer ──────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5,
                             color=colors.HexColor('#cccccc')))
    story.append(Paragraph(
        f'SewaDroneCilegonBanten — Dicetak: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        footer_style
    ))

    doc.build(story)

    # cleanup temp signature images
    for img in [admin_sig_img, user_sig_img]:
        if img and hasattr(img, '_tmp_path'):
            try:
                os.unlink(img._tmp_path)
            except Exception:
                pass

    fname = f'Pengembalian_Booking{booking_id}_{booking.drone.name.replace(" ", "_")}.pdf'
    return send_file(
        tmp.name,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=fname
    )
