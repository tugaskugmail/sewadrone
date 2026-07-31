from flask import Blueprint, jsonify, request
from datetime import datetime, date
from extensions import db
from models import Drone, Booking

api_bp = Blueprint('api', __name__)


@api_bp.route('/stats')
def stats():
    total_drones = Drone.query.count()
    available_drones = Drone.query.filter_by(is_available=True).count()
    today = date.today()

    active_bookings = Booking.query.filter(
        Booking.status.in_(['confirmed', 'active']),
        Booking.start_date <= today,
        Booking.end_date >= today
    ).count()

    total_revenue = db.session.query(db.func.sum(Booking.total_price)).filter(
        Booking.status == 'completed'
    ).scalar() or 0

    return jsonify({
        'total_drones': total_drones,
        'available_drones': available_drones,
        'active_bookings': active_bookings,
        'total_revenue': total_revenue
    })


@api_bp.route('/bookings/calendar')
def booking_calendar():
    """Return all bookings for calendar display"""
    bookings = Booking.query.filter(
        Booking.status.in_(['pending', 'confirmed', 'active'])
    ).all()

    events = []
    for b in bookings:
        events.append({
            'id': b.id,
            'title': f'{b.drone.name} - {b.user.username}',
            'start': b.start_date.isoformat(),
            'end': b.end_date.isoformat(),
            'status': b.status,
            'color': {
                'pending': '#ffc107',
                'confirmed': '#0dcaf0',
                'active': '#0d6efd'
            }.get(b.status, '#6c757d')
        })

    return jsonify(events)


@api_bp.route('/check-date', methods=['POST'])
def check_date():
    data = request.get_json()
    drone_id = data.get('drone_id')
    start_str = data.get('start_date')
    end_str = data.get('end_date')

    if not all([drone_id, start_str, end_str]):
        return jsonify({'available': False, 'error': 'Missing parameters'}), 400

    drone = Drone.query.get(drone_id)
    if not drone:
        return jsonify({'available': False, 'error': 'Drone not found'}), 404

    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()
    except:
        return jsonify({'available': False, 'error': 'Invalid date format'}), 400

    conflicting = Booking.query.filter(
        Booking.drone_id == drone.id,
        Booking.status.in_(['pending', 'confirmed', 'active']),
        Booking.start_date <= end,
        Booking.end_date >= start
    ).count()

    available = conflicting < drone.stock
    total_days = (end - start).days + 1

    return jsonify({
        'available': available,
        'drone': drone.name,
        'stock_total': drone.stock,
        'stock_left': max(0, drone.stock - conflicting),
        'total_days': total_days,
        'daily_rate': drone.daily_rate,
        'total_price': drone.daily_rate * total_days if total_days > 0 else 0,
        'deposit': drone.deposit
    })
