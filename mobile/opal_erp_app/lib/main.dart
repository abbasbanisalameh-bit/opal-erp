import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const apiBase = String.fromEnvironment(
  'OPAL_ERP_API_BASE_URL',
  defaultValue: 'https://opalschool2016.pythonanywhere.com/mobile/api/v1',
);

class OpalSystemColors {
  static const blue = Color(0xFF0D63B8);
  static const blueDark = Color(0xFF063B70);
  static const cyan = Color(0xFF198FC8);
  static const ink = Color(0xFF10243E);
  static const surface = Color(0xFFF4F8FC);
  static const gold = Color(0xFFE0AC2D);
  static const success = Color(0xFF18875A);
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OpalErpApp());
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code});
  final String message;
  final int? statusCode;
  final String? code;
  @override
  String toString() => message;
}

class ErpApiClient {
  ErpApiClient(this.storage);
  final FlutterSecureStorage storage;
  static const tokenKey = 'opal_erp_mobile_token';
  String? token;

  Future<void> loadToken() async => token = await storage.read(key: tokenKey);

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = apiBase.endsWith('/') ? apiBase : '$apiBase/';
    final uri = Uri.parse(base).resolve(path);
    return query == null ? uri : uri.replace(queryParameters: query);
  }

  Map<String, String> _headers({bool jsonBody = false}) => {
        'Accept': 'application/json',
        if (jsonBody) 'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  dynamic _decode(http.Response response) {
    dynamic payload;
    try {
      payload = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException('استجابة الخادم غير صالحة.', statusCode: response.statusCode);
    }
    if (response.statusCode < 200 || response.statusCode >= 300 || payload['ok'] != true) {
      final error = payload is Map ? payload['error'] as Map? : null;
      throw ApiException(
        error?['message']?.toString() ?? 'تعذر إكمال الطلب.',
        statusCode: response.statusCode,
        code: error?['code']?.toString(),
      );
    }
    return payload['data'];
  }

  Future<dynamic> get(String path, {Map<String, String>? query}) async {
    final response = await http.get(_uri(path, query), headers: _headers()).timeout(const Duration(seconds: 25));
    return _decode(response);
  }

  Future<dynamic> post(String path, [Map<String, dynamic>? body]) async {
    final response = await http
        .post(_uri(path), headers: _headers(jsonBody: true), body: jsonEncode(body ?? <String, dynamic>{}))
        .timeout(const Duration(seconds: 25));
    return _decode(response);
  }

  Future<Map<String, dynamic>> login(String username, String password) async {
    final data = Map<String, dynamic>.from(await post('auth/login/', {
      'username': username,
      'password': password,
      'device_name': 'OPAL ERP Android',
    }) as Map);
    final value = data['token']?.toString() ?? '';
    if (value.isEmpty) throw ApiException('لم يصدر الخادم جلسة دخول صالحة.');
    token = value;
    await storage.write(key: tokenKey, value: value);
    return Map<String, dynamic>.from(data['account'] as Map? ?? const {});
  }

  Future<Map<String, dynamic>> me() async => Map<String, dynamic>.from(await get('me/') as Map);

  Future<void> logout() async {
    try {
      if (token != null) await post('auth/logout/');
    } catch (_) {
      // Local sign-out remains available if the server is unreachable.
    } finally {
      token = null;
      await storage.delete(key: tokenKey);
    }
  }
}

class OpalSchoolLogo extends StatelessWidget {
  const OpalSchoolLogo({super.key, this.size = 110});
  final double size;
  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(color: OpalSystemColors.blueDark.withValues(alpha: .18), blurRadius: 24, offset: const Offset(0, 9))],
        ),
        child: ClipOval(child: Image.asset('assets/opal-school-logo.png', fit: BoxFit.cover)),
      );
}

class OpalErpApp extends StatefulWidget {
  const OpalErpApp({super.key});
  @override
  State<OpalErpApp> createState() => _OpalErpAppState();
}

class _OpalErpAppState extends State<OpalErpApp> {
  final storage = const FlutterSecureStorage();
  late final ErpApiClient api = ErpApiClient(storage);
  bool loading = true;
  Map<String, dynamic>? account;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await api.loadToken();
    if (api.token != null) {
      try {
        account = await api.me();
      } catch (_) {
        await api.logout();
      }
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> signedIn(Map<String, dynamic> value) async {
    if (mounted) setState(() => account = value);
  }

  Future<void> signedOut() async {
    await api.logout();
    if (mounted) setState(() => account = null);
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'نظام أوبال',
        locale: const Locale('ar'),
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: OpalSystemColors.surface,
          colorScheme: ColorScheme.fromSeed(seedColor: OpalSystemColors.blue, surface: Colors.white),
          fontFamilyFallback: const ['Arial'],
          appBarTheme: const AppBarTheme(
            backgroundColor: Colors.white,
            foregroundColor: OpalSystemColors.ink,
            surfaceTintColor: Colors.transparent,
            elevation: 0,
          ),
          cardTheme: const CardThemeData(
            color: Colors.white,
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.all(Radius.circular(18)),
              side: BorderSide(color: Color(0xFFE0EAF4)),
            ),
          ),
          inputDecorationTheme: const InputDecorationTheme(
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(15))),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.all(Radius.circular(15)),
              borderSide: BorderSide(color: Color(0xFFD9E5F0)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.all(Radius.circular(15)),
              borderSide: BorderSide(color: OpalSystemColors.blue, width: 1.5),
            ),
          ),
          filledButtonTheme: FilledButtonThemeData(
            style: FilledButton.styleFrom(
              backgroundColor: OpalSystemColors.blue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
        home: Directionality(
          textDirection: TextDirection.rtl,
          child: loading
              ? const SystemSplash()
              : account == null
                  ? SystemLoginPage(api: api, onSignedIn: signedIn)
                  : SystemHomePage(api: api, account: account!, onSignedOut: signedOut),
        ),
      );
}

class SystemSplash extends StatelessWidget {
  const SystemSplash({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
        body: Container(
          width: double.infinity,
          decoration: const BoxDecoration(
            gradient: LinearGradient(colors: [Color(0xFFE7F2FC), Colors.white, Color(0xFFF0F7FD)], begin: Alignment.topRight, end: Alignment.bottomLeft),
          ),
          child: const SafeArea(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OpalSchoolLogo(size: 150),
                SizedBox(height: 20),
                Text('نظام أوبال المدرسي', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: OpalSystemColors.ink)),
                SizedBox(height: 8),
                Text('كل أعمال المدرسة في مكان واحد', style: TextStyle(color: OpalSystemColors.blue, fontWeight: FontWeight.w700)),
                SizedBox(height: 28),
                SizedBox(width: 34, height: 34, child: CircularProgressIndicator(strokeWidth: 3)),
              ],
            ),
          ),
        ),
      );
}

class SystemLoginPage extends StatefulWidget {
  const SystemLoginPage({super.key, required this.api, required this.onSignedIn});
  final ErpApiClient api;
  final Future<void> Function(Map<String, dynamic>) onSignedIn;
  @override
  State<SystemLoginPage> createState() => _SystemLoginPageState();
}

class _SystemLoginPageState extends State<SystemLoginPage> {
  final username = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;

  Future<void> submit() async {
    if (username.text.trim().isEmpty || password.text.isEmpty) return;
    setState(() { busy = true; error = null; });
    try {
      final account = await widget.api.login(username.text.trim(), password.text);
      await widget.onSignedIn(account);
    } on ApiException catch (exc) {
      if (mounted) setState(() => error = exc.message);
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر الاتصال بخادم نظام أوبال.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Container(
          width: double.infinity,
          decoration: const BoxDecoration(
            gradient: LinearGradient(colors: [Color(0xFFE6F1FB), Color(0xFFF9FCFF), Color(0xFFEAF4FC)], begin: Alignment.topRight, end: Alignment.bottomLeft),
          ),
          child: SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 470),
                  child: Column(
                    children: [
                      const OpalSchoolLogo(size: 142),
                      const SizedBox(height: 16),
                      Text('نظام أوبال المدرسي', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900, color: OpalSystemColors.ink)),
                      const SizedBox(height: 6),
                      const Text('إدارة المدرسة بوضوح وسرعة من هاتفك', style: TextStyle(color: OpalSystemColors.blue, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 22),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(22),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('تسجيل الدخول', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                              const SizedBox(height: 5),
                              const Text('استخدم نفس اسم المستخدم وكلمة المرور في OPAL ERP.', style: TextStyle(color: Color(0xFF65798D))),
                              const SizedBox(height: 20),
                              TextField(
                                controller: username,
                                autofillHints: const [AutofillHints.username],
                                decoration: const InputDecoration(labelText: 'اسم المستخدم', prefixIcon: Icon(Icons.person_outline_rounded)),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                controller: password,
                                obscureText: true,
                                autofillHints: const [AutofillHints.password],
                                decoration: const InputDecoration(labelText: 'كلمة المرور', prefixIcon: Icon(Icons.lock_outline_rounded)),
                              ),
                              if (error != null)
                                Container(
                                  margin: const EdgeInsets.only(top: 12),
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(color: Theme.of(context).colorScheme.errorContainer, borderRadius: BorderRadius.circular(14)),
                                  child: Text(error!),
                                ),
                              const SizedBox(height: 18),
                              FilledButton.icon(
                                onPressed: busy ? null : submit,
                                icon: busy
                                    ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                    : const Icon(Icons.login_rounded),
                                label: const Text('دخول إلى النظام'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
}

class ModuleSpec {
  const ModuleSpec(this.code, this.label, this.endpoint, this.icon, this.color);
  final String code;
  final String label;
  final String endpoint;
  final IconData icon;
  final Color color;
}

const moduleSpecs = <ModuleSpec>[
  ModuleSpec('students', 'الطلاب', 'students/', Icons.groups_rounded, Color(0xFF0D63B8)),
  ModuleSpec('guardians', 'أولياء الأمور', 'guardians/', Icons.family_restroom_rounded, Color(0xFF0C8B8E)),
  ModuleSpec('teachers', 'المعلمون', 'teachers/', Icons.co_present_rounded, Color(0xFF5F57B7)),
  ModuleSpec('timetable', 'الجدول الدراسي', 'timetable/', Icons.calendar_month_rounded, Color(0xFF2C78B8)),
  ModuleSpec('attendance', 'الحضور والغياب', 'attendance/', Icons.fact_check_rounded, Color(0xFF13815B)),
  ModuleSpec('finance', 'الرسوم والدفعات', 'finance/', Icons.payments_rounded, Color(0xFFB47A12)),
  ModuleSpec('exams', 'الامتحانات', 'exams/', Icons.assignment_rounded, Color(0xFF7A56B6)),
  ModuleSpec('documents', 'الوثائق', 'documents/', Icons.description_rounded, Color(0xFF426C97)),
  ModuleSpec('announcements', 'الإعلانات', 'announcements/', Icons.campaign_rounded, Color(0xFFD16B31)),
];

class SystemHomePage extends StatefulWidget {
  const SystemHomePage({super.key, required this.api, required this.account, required this.onSignedOut});
  final ErpApiClient api;
  final Map<String, dynamic> account;
  final Future<void> Function() onSignedOut;
  @override
  State<SystemHomePage> createState() => _SystemHomePageState();
}

class _SystemHomePageState extends State<SystemHomePage> {
  late Future<Map<String, dynamic>> future = load();
  Future<Map<String, dynamic>> load() async => Map<String, dynamic>.from(await widget.api.get('dashboard/') as Map);
  Future<void> reload() async => setState(() => future = load());

  String motivation() {
    const messages = [
      'إدارة واضحة اليوم تعني وقتًا أكثر للطلاب غدًا.',
      'ابدأ بالأهم، ودع أوبال يجمع التفاصيل في مكان واحد.',
      'كل معلومة دقيقة تساعدك على قرار أفضل.',
      'يوم منظم يبدأ من لوحة واضحة.',
      'تابع المؤشرات، وأنجز أعمال المدرسة بثقة.',
    ];
    return messages[DateTime.now().day % messages.length];
  }

  @override
  Widget build(BuildContext context) {
    final allowed = List<dynamic>.from(widget.account['modules'] as List? ?? const []).map((e) => e.toString()).toSet();
    final modules = moduleSpecs.where((m) => allowed.contains(m.code)).toList();
    final name = widget.account['full_name']?.toString() ?? 'مستخدم أوبال';
    final role = widget.account['role_label']?.toString() ?? '';
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            ClipOval(child: Image.asset('assets/opal-school-logo.png', width: 36, height: 36, fit: BoxFit.cover)),
            const SizedBox(width: 9),
            const Text('نظام أوبال', style: TextStyle(fontWeight: FontWeight.w900)),
          ],
        ),
        actions: [IconButton(onPressed: widget.onSignedOut, tooltip: 'تسجيل الخروج', icon: const Icon(Icons.logout_rounded))],
      ),
      body: RefreshIndicator(
        onRefresh: reload,
        child: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            final data = snapshot.data;
            final stats = Map<String, dynamic>.from(data?['stats'] as Map? ?? const {});
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 26),
              children: [
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [OpalSystemColors.blueDark, OpalSystemColors.blue, OpalSystemColors.cyan], begin: Alignment.topRight, end: Alignment.bottomLeft),
                    borderRadius: BorderRadius.circular(22),
                    boxShadow: [BoxShadow(color: OpalSystemColors.blueDark.withValues(alpha: .18), blurRadius: 22, offset: const Offset(0, 9))],
                  ),
                  child: Row(
                    children: [
                      Container(width: 52, height: 52, decoration: BoxDecoration(color: Colors.white.withValues(alpha: .15), shape: BoxShape.circle), child: const Icon(Icons.dashboard_customize_rounded, color: Colors.white, size: 29)),
                      const SizedBox(width: 13),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('مرحبًا، $name', style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w900)),
                          const SizedBox(height: 3),
                          Text('$role · ${motivation()}', style: TextStyle(color: Colors.white.withValues(alpha: .90), fontSize: 12, height: 1.4)),
                        ]),
                      ),
                      const Icon(Icons.auto_awesome_rounded, color: OpalSystemColors.gold),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('لوحة اليوم', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                    if (data != null) Text(data['academic_year']?.toString() ?? '', style: const TextStyle(color: Color(0xFF65798D))),
                  ],
                ),
                const SizedBox(height: 10),
                if (snapshot.connectionState != ConnectionState.done)
                  const SizedBox(height: 100, child: Center(child: CircularProgressIndicator()))
                else if (snapshot.hasError)
                  ErrorCard(message: snapshot.error.toString(), onRetry: reload)
                else
                  Wrap(
                    spacing: 9,
                    runSpacing: 9,
                    children: [
                      if (stats['students'] != null) DashboardStat(icon: Icons.groups_rounded, value: '${stats['students']}', label: 'طالب'),
                      if (stats['guardians'] != null) DashboardStat(icon: Icons.family_restroom_rounded, value: '${stats['guardians']}', label: 'ولي أمر'),
                      if (stats['teachers'] != null) DashboardStat(icon: Icons.co_present_rounded, value: '${stats['teachers']}', label: 'معلم'),
                      if (stats['today_attendance_events'] != null) DashboardStat(icon: Icons.fact_check_rounded, value: '${stats['today_attendance_events']}', label: 'حركة حضور'),
                      if (stats['open_invoices'] != null) DashboardStat(icon: Icons.payments_rounded, value: '${stats['open_invoices']}', label: 'رسوم مفتوحة'),
                    ],
                  ),
                const SizedBox(height: 22),
                Text('أقسام النظام', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 10),
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 10, crossAxisSpacing: 10, childAspectRatio: 1.35),
                  itemCount: modules.length,
                  itemBuilder: (context, index) {
                    final module = modules[index];
                    return InkWell(
                      borderRadius: BorderRadius.circular(18),
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => SystemModulePage(api: widget.api, spec: module))),
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(15),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Container(width: 43, height: 43, decoration: BoxDecoration(color: module.color.withValues(alpha: .11), borderRadius: BorderRadius.circular(14)), child: Icon(module.icon, color: module.color)),
                              Row(children: [Expanded(child: Text(module.label, style: const TextStyle(fontWeight: FontWeight.w900))), const Icon(Icons.chevron_left_rounded, size: 20)]),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class DashboardStat extends StatelessWidget {
  const DashboardStat({super.key, required this.icon, required this.value, required this.label});
  final IconData icon;
  final String value;
  final String label;
  @override
  Widget build(BuildContext context) => SizedBox(
        width: 158,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(width: 39, height: 39, decoration: BoxDecoration(color: OpalSystemColors.blue.withValues(alpha: .09), borderRadius: BorderRadius.circular(12)), child: Icon(icon, color: OpalSystemColors.blue, size: 21)),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(value, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900)), Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF6B7E91)))])),
              ],
            ),
          ),
        ),
      );
}

class SystemModulePage extends StatefulWidget {
  const SystemModulePage({super.key, required this.api, required this.spec});
  final ErpApiClient api;
  final ModuleSpec spec;
  @override
  State<SystemModulePage> createState() => _SystemModulePageState();
}

class _SystemModulePageState extends State<SystemModulePage> {
  final search = TextEditingController();
  late Future<Map<String, dynamic>> future = load();

  Future<Map<String, dynamic>> load([String q = '']) async {
    final query = q.trim().isEmpty ? null : {'q': q.trim()};
    return Map<String, dynamic>.from(await widget.api.get(widget.spec.endpoint, query: query) as Map);
  }

  Future<void> reload([String q = '']) async => setState(() => future = load(q));

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.spec.label, style: const TextStyle(fontWeight: FontWeight.w900))),
        body: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return ErrorCard(message: snapshot.error.toString(), onRetry: () => reload(search.text));
            final data = snapshot.data ?? const <String, dynamic>{};
            final items = List<dynamic>.from(data['items'] as List? ?? const []);
            return RefreshIndicator(
              onRefresh: () => reload(search.text),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: widget.spec.color.withValues(alpha: .08), borderRadius: BorderRadius.circular(18)),
                    child: Row(children: [Container(width: 45, height: 45, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)), child: Icon(widget.spec.icon, color: widget.spec.color)), const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(widget.spec.label, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17)), Text('${items.length} سجل ظاهر', style: const TextStyle(color: Color(0xFF66798B), fontSize: 12))]))]),
                  ),
                  if ({'students', 'guardians', 'teachers', 'finance'}.contains(widget.spec.code)) ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: search,
                      textInputAction: TextInputAction.search,
                      onSubmitted: reload,
                      decoration: InputDecoration(labelText: 'بحث', prefixIcon: const Icon(Icons.search_rounded), suffixIcon: IconButton(onPressed: () => reload(search.text), icon: const Icon(Icons.arrow_forward_rounded))),
                    ),
                  ],
                  const SizedBox(height: 12),
                  if (items.isEmpty)
                    const Card(child: Padding(padding: EdgeInsets.all(28), child: Column(children: [Icon(Icons.inbox_outlined, size: 42, color: Color(0xFF8AA0B5)), SizedBox(height: 10), Text('لا توجد بيانات لعرضها حاليًا.', textAlign: TextAlign.center)])))
                  else
                    ...items.map((raw) {
                      final item = Map<String, dynamic>.from(raw as Map);
                      final status = item['status']?.toString() ?? '';
                      final remaining = item['remaining']?.toString();
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 9),
                        child: Card(
                          child: ListTile(
                            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                            leading: Container(width: 42, height: 42, decoration: BoxDecoration(color: widget.spec.color.withValues(alpha: .10), borderRadius: BorderRadius.circular(13)), child: Icon(widget.spec.icon, color: widget.spec.color, size: 22)),
                            title: Text(item['title']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
                            subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              if ((item['subtitle']?.toString() ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 3), child: Text(item['subtitle'].toString(), maxLines: widget.spec.code == 'announcements' ? 4 : 2, overflow: TextOverflow.ellipsis)),
                              if (remaining != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text('المتبقي: $remaining د.أ', style: const TextStyle(color: OpalSystemColors.blue, fontWeight: FontWeight.w800))),
                            ]),
                            trailing: status.isEmpty ? null : Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5), decoration: BoxDecoration(color: widget.spec.color.withValues(alpha: .08), borderRadius: BorderRadius.circular(999)), child: Text(status, style: TextStyle(color: widget.spec.color, fontSize: 10, fontWeight: FontWeight.w800))),
                          ),
                        ),
                      );
                    }),
                ],
              ),
            );
          },
        ),
      );
}

class ErrorCard extends StatelessWidget {
  const ErrorCard({super.key, required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.error_outline_rounded, size: 38, color: Theme.of(context).colorScheme.error),
                const SizedBox(height: 10),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 12),
                OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh_rounded), label: const Text('إعادة المحاولة')),
              ]),
            ),
          ),
        ),
      );
}
