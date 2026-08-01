"""
Script: sync_fullname_to_username.py
Fungsi: Samakan full_name dengan username untuk semua user di database
Usage : python sync_fullname_to_username.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    if not users:
        print("Tidak ada user di database.")
        sys.exit(0)

    print(f"{'ID':<5} {'Username':<20} {'Full Name Lama':<30} {'Full Name Baru':<20}")
    print("-" * 80)

    updated = 0
    for u in users:
        old = u.full_name
        if u.full_name != u.username:
            u.full_name = u.username
            updated += 1
            marker = " ← UPDATE"
        else:
            marker = ""
        print(f"{u.id:<5} {u.username:<20} {str(old):<30} {u.full_name:<20}{marker}")

    if updated:
        db.session.commit()
        print(f"\n✅ {updated} user diupdate.")
    else:
        print("\n✅ Semua full_name sudah sama dengan username, tidak ada yang diubah.")
