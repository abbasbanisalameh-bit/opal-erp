from datetime import datetime

def generate_receipt_number():
    return datetime.now().strftime("RC%Y%m%d%H%M%S")
