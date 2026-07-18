PAYMENT_METHOD_CHOICES = [
    ("cash", "نقدي"),
    ("card", "بطاقة بنكية"),
    ("bank_transfer", "تحويل بنكي"),
    ("online", "دفع إلكتروني"),
    ("cheque", "شيك"),
    ("unspecified", "غير محدد (سجل سابق)"),
]


ACTIVE_PAYMENT_METHOD_CHOICES = PAYMENT_METHOD_CHOICES[:-1]
