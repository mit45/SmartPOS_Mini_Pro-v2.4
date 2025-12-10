from repositories import personnel_repository as repo

def start_shift(conn, cursor, user_id, note=""):
    repo.start_shift(cursor, user_id, note)
    conn.commit()

def end_shift(conn, cursor, shift_id):
    repo.end_shift(cursor, shift_id)
    conn.commit()

def get_active_shift(cursor, user_id):
    return repo.get_active_shift(cursor, user_id)

def list_shifts(cursor, user_id=None):
    return repo.list_shifts(cursor, user_id)

def add_payment(conn, cursor, user_id, amount, ptype, date, desc):
    repo.add_payment(cursor, user_id, amount, ptype, date, desc)
    conn.commit()

def list_payments(cursor, user_id=None):
    return repo.list_payments(cursor, user_id)
