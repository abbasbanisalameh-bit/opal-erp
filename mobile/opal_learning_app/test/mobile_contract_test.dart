import 'package:flutter_test/flutter_test.dart';
import 'package:opal_learning_app/main.dart';

void main() {
  test('production API default is HTTPS and points to learning api v1', () {
    final uri = Uri.parse(apiBase);
    expect(uri.scheme, 'https');
    expect(uri.path.endsWith('/learning/api/v1'), isTrue);
  });

  test('school mobile profile keeps child identity separate from token', () {
    final profile = MobileProfile.fromMap({
      'token': 'token-child-1',
      'account': {'full_name': 'حساب تعلم الطالب'},
      'profile': {
        'kind': 'student',
        'student_id': 10,
        'student_name': 'آدم أحمد بني سلامة',
        'class_label': 'الصف الأول - أ',
      },
    });
    expect(profile.token, 'token-child-1');
    expect(profile.label, 'آدم أحمد بني سلامة');
    expect(profile.subtitle, 'الصف الأول - أ');
  });

  test('manager profile uses the same OPAL mobile identity contract', () {
    final profile = MobileProfile.fromMap({
      'token': 'olm-manager-token',
      'account': {'full_name': 'مدير المدرسة', 'role': 'manager'},
      'profile': {'kind': 'manager', 'manager_username': 'admin'},
    });
    expect(profile.label, 'مدير المدرسة');
    expect(profile.subtitle, 'إدارة منصة أوبال التعليمية');
  });
}
