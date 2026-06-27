from datetime import date

def generate_receipt_number(count):
    year = date.today().year
    return f"RC-{year}-{count:06d}"
