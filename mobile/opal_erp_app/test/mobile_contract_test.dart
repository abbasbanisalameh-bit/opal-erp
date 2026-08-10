import 'package:flutter_test/flutter_test.dart';
import 'package:opal_erp_app/main.dart';

void main() {
  test('production API default is HTTPS and points to OPAL system mobile api v1', () {
    final uri = Uri.parse(apiBase);
    expect(uri.scheme, 'https');
    expect(uri.path.endsWith('/mobile/api/v1'), isTrue);
  });

  test('native system modules keep the core school operations visible', () {
    final codes = moduleSpecs.map((item) => item.code).toSet();
    expect(codes.contains('students'), isTrue);
    expect(codes.contains('guardians'), isTrue);
    expect(codes.contains('teachers'), isTrue);
    expect(codes.contains('timetable'), isTrue);
    expect(codes.contains('attendance'), isTrue);
    expect(codes.contains('finance'), isTrue);
    expect(codes.contains('exams'), isTrue);
    expect(codes.contains('documents'), isTrue);
    expect(codes.contains('announcements'), isTrue);
  });
}
