from enterprise_ops.services import notify


def guardian_users_for_student(student):
    return [
        link.family.user
        for link in student.family_links.filter(is_active=True, family__is_active=True, family__user__isnull=False)
        .select_related("family__user")
    ]


def notify_guardian_for_student(student, title, message, *, event_key, link="/parent/"):
    items = []
    for user in guardian_users_for_student(student):
        items.append(notify(user, title, message, "info", link, event_key=f"{event_key}:user:{user.pk}"))
    return items


def notify_guardians_for_fee_payment(fee_payment):
    students = {
        allocation.student_id: allocation.student
        for allocation in fee_payment.allocations.select_related("student")
        if allocation.amount > 0
    }
    names = "، ".join(student.full_name for student in students.values())
    for student in students.values():
        notify_guardian_for_student(
            student,
            "تم تسجيل دفعة رسوم",
            f"تم تسجيل دفعة بقيمة {fee_payment.total_amount} د.أ وتوزيعها على: {names}. رقم الإيصال {fee_payment.receipt_number}.",
            event_key=f"fee-payment:{fee_payment.pk}",
            link="/parent/fees/",
        )


def notify_guardian_for_registration(registration):
    if registration.student_id and registration.first_payment > 0:
        notify_guardian_for_student(
            registration.student,
            "تم تسجيل الدفعة الأولى",
            f"تم تسجيل {registration.first_payment} د.أ للطالب {registration.student.full_name}. رقم الإيصال {registration.receipt.receipt_number if registration.receipt else '-'}.",
            event_key=f"registration-payment:{registration.pk}",
            link="/parent/fees/",
        )
