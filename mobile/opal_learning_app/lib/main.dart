import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:webview_flutter/webview_flutter.dart';

const apiBase = String.fromEnvironment(
  'OPAL_API_BASE_URL',
  defaultValue: 'https://opalschool2016.pythonanywhere.com/learning/api/v1',
);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OpalLearningApp());
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code});
  final String message;
  final int? statusCode;
  final String? code;
  @override
  String toString() => message;
}

class MobileProfile {
  MobileProfile({required this.token, required this.account, this.profile = const {}});
  final String token;
  final Map<String, dynamic> account;
  final Map<String, dynamic> profile;

  String get label => profile['student_name']?.toString() ?? account['full_name']?.toString() ?? 'أوبال';
  String get subtitle {
    final kind = profile['kind']?.toString() ?? '';
    if (kind == 'manager') return 'إدارة منصة أوبال التعليمية';
    if (kind == 'teacher') return 'حساب المعلم';
    return profile['class_label']?.toString() ?? '';
  }

  factory MobileProfile.fromMap(Map<String, dynamic> raw) => MobileProfile(
        token: raw['token']?.toString() ?? '',
        account: Map<String, dynamic>.from(raw['account'] as Map? ?? const {}),
        profile: Map<String, dynamic>.from(raw['profile'] as Map? ?? const {}),
      );

  Map<String, dynamic> toMap() => {'token': token, 'account': account, 'profile': profile};
}

class ApiClient {
  ApiClient(this.storage);
  final FlutterSecureStorage storage;
  String? token;
  static const tokenKey = 'learning_api_token';
  static const profilesKey = 'learning_school_profiles';

  Future<void> loadToken() async => token = await storage.read(key: tokenKey);

  Uri _uri(String path) {
    final base = apiBase.endsWith('/') ? apiBase : '$apiBase/';
    return Uri.parse(base).resolve(path);
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

  Future<dynamic> get(String path) async {
    final response = await http.get(_uri(path), headers: _headers()).timeout(const Duration(seconds: 25));
    return _decode(response);
  }

  Future<dynamic> post(String path, [Map<String, dynamic>? body]) async {
    final response = await http
        .post(_uri(path), headers: _headers(jsonBody: true), body: jsonEncode(body ?? <String, dynamic>{}))
        .timeout(const Duration(seconds: 25));
    return _decode(response);
  }

  Future<List<MobileProfile>> signIn(String identifier, String password) async {
    try {
      final schoolData = Map<String, dynamic>.from(await post('auth/school-login/', {
        'username': identifier,
        'password': password,
        'device_name': 'OPAL Flutter Mobile',
      }) as Map);
      final profiles = List<dynamic>.from(schoolData['profiles'] as List? ?? const [])
          .map((e) => MobileProfile.fromMap(Map<String, dynamic>.from(e as Map)))
          .where((e) => e.token.isNotEmpty)
          .toList();
      if (profiles.isEmpty) throw ApiException('لم يصدر الخادم ملف دخول صالحًا.');
      await storage.write(key: profilesKey, value: jsonEncode(profiles.map((e) => e.toMap()).toList()));
      return profiles;
    } on ApiException catch (exc) {
      if (!{'unsupported_school_account', 'invalid_credentials'}.contains(exc.code)) rethrow;
      if (!identifier.contains('@')) rethrow;
      final data = Map<String, dynamic>.from(await post('auth/login/', {
        'email': identifier,
        'password': password,
        'device_name': 'OPAL Flutter Mobile',
      }) as Map);
      final profile = MobileProfile(
        token: data['token']?.toString() ?? '',
        account: Map<String, dynamic>.from(data['account'] as Map),
      );
      if (profile.token.isEmpty) throw ApiException('لم يصدر الخادم رمز دخول.');
      return [profile];
    }
  }

  Future<void> useProfile(MobileProfile profile) async {
    token = profile.token;
    await storage.write(key: tokenKey, value: token);
  }

  Future<List<MobileProfile>> storedProfiles() async {
    final raw = await storage.read(key: profilesKey);
    if (raw == null || raw.isEmpty) return const [];
    try {
      return List<dynamic>.from(jsonDecode(raw) as List)
          .map((e) => MobileProfile.fromMap(Map<String, dynamic>.from(e as Map)))
          .where((e) => e.token.isNotEmpty)
          .toList();
    } catch (_) {
      return const [];
    }
  }

  Future<void> logout() async {
    try {
      if (token != null) await post('auth/logout/');
    } catch (_) {
      // Local logout must still succeed if the network is unavailable.
    } finally {
      token = null;
      await storage.delete(key: tokenKey);
      await storage.delete(key: profilesKey);
    }
  }
}

class OpalLearningApp extends StatefulWidget {
  const OpalLearningApp({super.key});
  @override
  State<OpalLearningApp> createState() => _OpalLearningAppState();
}

class _OpalLearningAppState extends State<OpalLearningApp> {
  final storage = const FlutterSecureStorage();
  late final ApiClient api = ApiClient(storage);
  bool loading = true;
  Map<String, dynamic>? account;
  List<MobileProfile> profiles = const [];

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await api.loadToken();
    profiles = await api.storedProfiles();
    if (api.token != null) {
      try {
        account = Map<String, dynamic>.from(await api.get('me/') as Map);
      } catch (_) {
        await api.logout();
        profiles = const [];
      }
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> signedIn(List<MobileProfile> values) async {
    profiles = values;
    await _chooseProfile(values.first);
  }

  Future<void> _chooseProfile(MobileProfile profile) async {
    await api.useProfile(profile);
    final current = Map<String, dynamic>.from(await api.get('me/') as Map);
    if (mounted) setState(() => account = current);
  }

  Future<void> signedOut() async {
    await api.logout();
    if (mounted) setState(() { account = null; profiles = const []; });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'أوبال',
      locale: const Locale('ar'),
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6F52D4)),
        useMaterial3: true,
        fontFamilyFallback: const ['Arial'],
      ),
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: loading
            ? const Scaffold(body: Center(child: CircularProgressIndicator()))
            : account == null
                ? LoginPage(api: api, onSignedIn: signedIn)
                : HomePage(
                    api: api,
                    account: account!,
                    profiles: profiles,
                    onChooseProfile: _chooseProfile,
                    onSignedOut: signedOut,
                  ),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.api, required this.onSignedIn});
  final ApiClient api;
  final Future<void> Function(List<MobileProfile>) onSignedIn;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final identifier = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;

  Future<void> submit() async {
    setState(() { busy = true; error = null; });
    try {
      final profiles = await widget.api.signIn(identifier.text.trim(), password.text);
      if (profiles.length == 1) {
        await widget.onSignedIn(profiles);
        return;
      }
      if (!mounted) return;
      final selected = await showModalBottomSheet<MobileProfile>(
        context: context,
        showDragHandle: true,
        builder: (context) => SafeArea(
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(12),
            children: [
              Text('اختر الابن', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              ...profiles.map((p) => ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.person)),
                    title: Text(p.label),
                    subtitle: p.subtitle.isEmpty ? null : Text(p.subtitle),
                    onTap: () => Navigator.pop(context, p),
                  )),
            ],
          ),
        ),
      );
      if (selected != null) {
        final ordered = [selected, ...profiles.where((p) => p.token != selected.token)];
        await widget.onSignedIn(ordered);
      }
    } on ApiException catch (exc) {
      setState(() => error = exc.message);
    } catch (_) {
      setState(() => error = 'تعذر الاتصال بالخادم.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      const Icon(Icons.school_rounded, size: 64),
                      const SizedBox(height: 12),
                      Text('أوبال', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall),
                      const SizedBox(height: 8),
                      const Text('ولي الأمر والمعلم والإدارة يستخدمون نفس حساب OPAL. حساب المنصة المستقل يمكنه استخدام البريد الإلكتروني.', textAlign: TextAlign.center),
                      const SizedBox(height: 24),
                      TextField(controller: identifier, autofillHints: const [AutofillHints.username], decoration: const InputDecoration(labelText: 'اسم المستخدم أو البريد الإلكتروني', border: OutlineInputBorder())),
                      const SizedBox(height: 12),
                      TextField(controller: password, obscureText: true, autofillHints: const [AutofillHints.password], decoration: const InputDecoration(labelText: 'كلمة المرور', border: OutlineInputBorder())),
                      if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                      const SizedBox(height: 18),
                      FilledButton(onPressed: busy ? null : submit, child: busy ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('دخول')),
                    ]),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
}

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.api, required this.account, required this.profiles, required this.onChooseProfile, required this.onSignedOut});
  final ApiClient api;
  final Map<String, dynamic> account;
  final List<MobileProfile> profiles;
  final Future<void> Function(MobileProfile) onChooseProfile;
  final Future<void> Function() onSignedOut;
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final role = widget.account['role']?.toString() ?? '';
    final isLearner = role == 'learner';
    final isManager = role == 'manager';
    final pages = isManager
        ? [
            ManagerDashboardPage(api: widget.api),
            ManagerAccountsPage(api: widget.api),
            ManagerCoursesPage(api: widget.api),
            ManagerCardsPage(api: widget.api),
            ManagerAccessPage(api: widget.api),
          ]
        : isLearner
            ? [CoursesPage(api: widget.api), NotificationsPage(api: widget.api), CertificatesPage(api: widget.api), SubscriptionPage(api: widget.api)]
            : [TeacherMobilePage(api: widget.api), NotificationsPage(api: widget.api)];
    final destinations = isManager
        ? const [
            NavigationDestination(icon: Icon(Icons.dashboard), label: 'الرئيسية'),
            NavigationDestination(icon: Icon(Icons.people), label: 'الحسابات'),
            NavigationDestination(icon: Icon(Icons.menu_book), label: 'الدورات'),
            NavigationDestination(icon: Icon(Icons.confirmation_number), label: 'البطاقات'),
            NavigationDestination(icon: Icon(Icons.tune), label: 'الإتاحة'),
          ]
        : isLearner
            ? const [
                NavigationDestination(icon: Icon(Icons.menu_book), label: 'الدورات'),
                NavigationDestination(icon: Icon(Icons.notifications), label: 'الإشعارات'),
                NavigationDestination(icon: Icon(Icons.workspace_premium), label: 'الشهادات'),
                NavigationDestination(icon: Icon(Icons.card_membership), label: 'الاشتراك'),
              ]
            : const [
                NavigationDestination(icon: Icon(Icons.cast_for_education), label: 'دوراتي'),
                NavigationDestination(icon: Icon(Icons.notifications), label: 'الإشعارات'),
              ];
    if (index >= pages.length) index = 0;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.account['full_name']?.toString() ?? 'أوبال تعليم'),
        actions: [
          if (!isManager && widget.profiles.length > 1)
            PopupMenuButton<MobileProfile>(
              tooltip: 'تبديل الابن',
              icon: const Icon(Icons.switch_account),
              onSelected: widget.onChooseProfile,
              itemBuilder: (_) => widget.profiles.map((p) => PopupMenuItem(value: p, child: Text(p.label))).toList(),
            ),
          IconButton(onPressed: widget.onSignedOut, tooltip: 'تسجيل الخروج', icon: const Icon(Icons.logout)),
        ],
      ),
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(selectedIndex: index, onDestinationSelected: (v) => setState(() => index = v), destinations: destinations),
    );
  }
}

class ManagerDashboardPage extends StatefulWidget {
  const ManagerDashboardPage({super.key, required this.api});
  final ApiClient api;
  @override
  State<ManagerDashboardPage> createState() => _ManagerDashboardPageState();
}

class _ManagerDashboardPageState extends State<ManagerDashboardPage> {
  late Future<Map<String, dynamic>> future = load();
  Future<Map<String, dynamic>> load() async => Map<String, dynamic>.from(await widget.api.get('manager/dashboard/') as Map);
  Future<void> reload() async => setState(() => future = load());

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: reload);
          final data = snapshot.data!;
          final stats = Map<String, dynamic>.from(data['stats'] as Map? ?? const {});
          final readiness = Map<String, dynamic>.from(data['readiness'] as Map? ?? const {});
          final cards = <MapEntry<String, String>>[
            MapEntry('المتعلمون', '${stats['learners'] ?? 0}'),
            MapEntry('المعلمون', '${stats['teachers'] ?? 0}'),
            MapEntry('الدورات المنشورة', '${stats['published_courses'] ?? 0}'),
            MapEntry('التسجيلات', '${stats['enrollments'] ?? 0}'),
            MapEntry('بطاقات متاحة', '${stats['available_subscriptions'] ?? 0}'),
            MapEntry('اشتراكات فعالة', '${stats['active_subscriptions'] ?? 0}'),
          ];
          final checks = List<dynamic>.from(readiness['checks'] as List? ?? const []);
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('إدارة منصة أوبال التعليمية', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text('حالة الجاهزية: ${readiness['overall'] ?? '—'} · الموانع: ${readiness['blocking_failures'] ?? 0}'),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: cards
                      .map(
                        (item) => SizedBox(
                          width: 165,
                          child: Card(
                            child: Padding(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                children: [
                                  Text(
                                    item.value,
                                    style: Theme.of(context).textTheme.headlineSmall,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(item.key, textAlign: TextAlign.center),
                                ],
                              ),
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 18),
                Text('فحص الجاهزية', style: Theme.of(context).textTheme.titleLarge),
                ...checks.map((raw) {
                  final item = Map<String, dynamic>.from(raw as Map);
                  final status = item['status']?.toString() ?? '';
                  final icon = status == 'pass' ? Icons.check_circle : status == 'fail' ? Icons.error : Icons.warning_amber_rounded;
                  return ListTile(leading: Icon(icon), title: Text(item['label']?.toString() ?? ''), subtitle: Text(item['detail']?.toString() ?? ''));
                }),
              ],
            ),
          );
        },
      );
}

class ManagerAccountsPage extends StatelessWidget {
  const ManagerAccountsPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(
        loader: () async => List<dynamic>.from(await api.get('manager/accounts/') as List),
        emptyText: 'لا توجد حسابات منصة.',
        builder: (context, raw) {
          final item = Map<String, dynamic>.from(raw as Map);
          return Card(child: ListTile(
            leading: CircleAvatar(child: Icon(item['role'] == 'teacher' ? Icons.school : Icons.person)),
            title: Text(item['full_name']?.toString() ?? ''),
            subtitle: Text('${item['email'] ?? ''}\n${item['role'] == 'teacher' ? 'معلم' : item['role'] == 'manager' ? 'مدير منصة' : 'متعلم'}${item['is_school_managed'] == true ? ' · مرتبط بالمدرسة' : ''}'),
            isThreeLine: true,
            trailing: Icon(item['is_active'] == true ? Icons.check_circle : Icons.block),
          ));
        },
      );
}

class ManagerCoursesPage extends StatefulWidget {
  const ManagerCoursesPage({super.key, required this.api});
  final ApiClient api;
  @override
  State<ManagerCoursesPage> createState() => _ManagerCoursesPageState();
}

class _ManagerCoursesPageState extends State<ManagerCoursesPage> {
  late Future<List<dynamic>> future = load();
  Future<List<dynamic>> load() async => List<dynamic>.from(await widget.api.get('manager/courses/') as List);
  Future<void> reload() async => setState(() => future = load());
  Future<void> changeStatus(Map<String, dynamic> course, String action) async {
    try {
      await widget.api.post('manager/courses/${course['id']}/status/', {'action': action});
      await reload();
    } on ApiException catch (exc) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(exc.message)));
    }
  }
  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: reload);
          final items = snapshot.data ?? const [];
          return RefreshIndicator(
            onRefresh: reload,
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final item = Map<String, dynamic>.from(items[index] as Map);
                return Card(child: ListTile(
                  leading: const CircleAvatar(child: Icon(Icons.menu_book)),
                  title: Text(item['title']?.toString() ?? ''),
                  subtitle: Text('${item['subject']?['name'] ?? ''} · ${item['teacher']?['name'] ?? ''}\nالدروس ${item['lesson_count'] ?? 0} · التقييمات ${item['assessment_count'] ?? 0} · ${item['status'] ?? ''}'),
                  isThreeLine: true,
                  trailing: PopupMenuButton<String>(
                    onSelected: (value) => changeStatus(item, value),
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'publish', child: Text('نشر')),
                      PopupMenuItem(value: 'draft', child: Text('إعادة لمسودة')),
                      PopupMenuItem(value: 'archive', child: Text('أرشفة')),
                    ],
                  ),
                ));
              },
            ),
          );
        },
      );
}

class ManagerCardsPage extends StatefulWidget {
  const ManagerCardsPage({super.key, required this.api});
  final ApiClient api;
  @override
  State<ManagerCardsPage> createState() => _ManagerCardsPageState();
}

class _ManagerCardsPageState extends State<ManagerCardsPage> {
  late Future<List<dynamic>> future = load();
  Future<List<dynamic>> load() async => List<dynamic>.from(await widget.api.get('manager/subscription-cards/') as List);
  Future<void> reload() async => setState(() => future = load());
  Future<void> cancelCard(int id) async {
    try {
      await widget.api.post('manager/subscription-cards/$id/cancel/');
      await reload();
    } on ApiException catch (exc) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(exc.message)));
    }
  }
  Future<void> generateCards() async {
    final subjects = List<dynamic>.from(await widget.api.get('manager/subjects/') as List);
    if (!mounted) return;
    final quantity = TextEditingController(text: '1');
    final prefix = TextEditingController(text: 'OPAL');
    String duration = 'monthly';
    bool allSubjects = true;
    final selected = <int>{};
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocalState) => AlertDialog(
          title: const Text('إنشاء بطاقات اشتراك'),
          content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: quantity, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'عدد البطاقات')),
            TextField(controller: prefix, textCapitalization: TextCapitalization.characters, decoration: const InputDecoration(labelText: 'بادئة الرمز')),
            const SizedBox(height: 10),
            DropdownMenu<String>(
              initialSelection: duration,
              label: const Text('المدة'),
              dropdownMenuEntries: const [
                DropdownMenuEntry(value: 'monthly', label: 'شهري'),
                DropdownMenuEntry(value: 'termly', label: 'فصلي'),
                DropdownMenuEntry(value: 'yearly', label: 'سنوي'),
              ],
              onSelected: (value) { if (value != null) duration = value; },
            ),
            CheckboxListTile(value: allSubjects, title: const Text('جميع المواد'), onChanged: (value) => setLocalState(() => allSubjects = value ?? false)),
            if (!allSubjects) ...subjects.map((raw) {
              final item = Map<String, dynamic>.from(raw as Map);
              final id = item['id'] as int;
              return CheckboxListTile(
                value: selected.contains(id),
                title: Text(item['name']?.toString() ?? ''),
                onChanged: (value) => setLocalState(() { if (value == true) { selected.add(id); } else { selected.remove(id); } }),
              );
            }),
          ])),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('إلغاء')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('إنشاء')),
          ],
        ),
      ),
    );
    if (accepted != true) return;
    try {
      await widget.api.post('manager/subscription-cards/generate/', {
        'quantity': int.tryParse(quantity.text.trim()) ?? 1,
        'prefix': prefix.text.trim(),
        'duration': duration,
        'grants_all_subjects': allSubjects,
        'subject_ids': selected.toList(),
      });
      await reload();
    } on ApiException catch (exc) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(exc.message)));
    }
  }
  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(padding: const EdgeInsets.all(12), child: SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: generateCards, icon: const Icon(Icons.add_card), label: const Text('إنشاء بطاقات عشوائية')))),
        Expanded(child: FutureBuilder<List<dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: reload);
            final items = snapshot.data ?? const [];
            return RefreshIndicator(onRefresh: reload, child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final item = Map<String, dynamic>.from(items[index] as Map);
                return Card(child: ListTile(
                  leading: const Icon(Icons.confirmation_number),
                  title: SelectableText(item['code']?.toString() ?? ''),
                  subtitle: Text('${item['duration_label'] ?? ''} · ${item['status_label'] ?? ''}'),
                  trailing: item['status'] == 'available' ? IconButton(onPressed: () => cancelCard(item['id'] as int), tooltip: 'إلغاء البطاقة', icon: const Icon(Icons.cancel)) : null,
                ));
              },
            ));
          },
        )),
      ]);
}

class ManagerAccessPage extends StatefulWidget {
  const ManagerAccessPage({super.key, required this.api});
  final ApiClient api;
  @override
  State<ManagerAccessPage> createState() => _ManagerAccessPageState();
}

class _ManagerAccessPageState extends State<ManagerAccessPage> {
  late Future<Map<String, dynamic>> future = load();
  final search = TextEditingController();
  Future<Map<String, dynamic>> load([String query = '']) async {
    final suffix = query.trim().isEmpty ? '' : '?q=${Uri.encodeQueryComponent(query.trim())}';
    return Map<String, dynamic>.from(await widget.api.get('manager/school-access/$suffix') as Map);
  }
  Future<void> reload([String query = '']) async => setState(() => future = load(query));
  Future<void> apply(Map<String, dynamic> body) async {
    try {
      await widget.api.post('manager/school-access/', body);
      await reload(search.text);
    } on ApiException catch (exc) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(exc.message)));
    }
  }
  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () => reload(search.text));
          final data = snapshot.data!;
          final grades = List<dynamic>.from(data['grades'] as List? ?? const []);
          final students = List<dynamic>.from(data['students'] as List? ?? const []);
          return ListView(padding: const EdgeInsets.all(16), children: [
            Text('إتاحة المنصة', style: Theme.of(context).textTheme.titleLarge),
            SwitchListTile(
              value: data['parent_default_enabled'] == true,
              title: const Text('الإتاحة الافتراضية لأولياء الأمور'),
              onChanged: (value) => apply({'action': 'global', 'parent_default_enabled': value, 'teacher_sso_enabled': data['teacher_sso_enabled'] == true}),
            ),
            SwitchListTile(
              value: data['teacher_sso_enabled'] == true,
              title: const Text('إتاحة المنصة للمعلمين'),
              onChanged: (value) => apply({'action': 'global', 'parent_default_enabled': data['parent_default_enabled'] == true, 'teacher_sso_enabled': value}),
            ),
            Row(children: [
              Expanded(child: FilledButton.tonal(onPressed: () => apply({'action': 'all_on'}), child: const Text('إتاحة للجميع'))),
              const SizedBox(width: 8),
              Expanded(child: FilledButton.tonal(onPressed: () => apply({'action': 'all_off'}), child: const Text('إيقاف عن الجميع'))),
            ]),
            const Divider(height: 30),
            Text('حسب الصف', style: Theme.of(context).textTheme.titleMedium),
            ...grades.map((raw) {
              final item = Map<String, dynamic>.from(raw as Map);
              return ListTile(
                title: Text(item['name']?.toString() ?? ''),
                trailing: DropdownMenu<String>(
                  width: 150,
                  initialSelection: item['mode']?.toString() ?? 'inherit',
                  dropdownMenuEntries: const [
                    DropdownMenuEntry(value: 'inherit', label: 'يتبع العام'),
                    DropdownMenuEntry(value: 'enabled', label: 'متاح'),
                    DropdownMenuEntry(value: 'disabled', label: 'موقوف'),
                  ],
                  onSelected: (value) { if (value != null) apply({'action': 'grade', 'grade_id': item['id'], 'mode': value}); },
                ),
              );
            }),
            const Divider(height: 30),
            Text('طالب معين', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            TextField(
              controller: search,
              textInputAction: TextInputAction.search,
              onSubmitted: reload,
              decoration: InputDecoration(labelText: 'اسم الطالب أو رقمه', border: const OutlineInputBorder(), suffixIcon: IconButton(onPressed: () => reload(search.text), icon: const Icon(Icons.search))),
            ),
            const SizedBox(height: 8),
            ...students.map((raw) {
              final item = Map<String, dynamic>.from(raw as Map);
              return ListTile(
                title: Text(item['full_name']?.toString() ?? ''),
                subtitle: Text(item['student_number']?.toString() ?? ''),
                trailing: DropdownMenu<String>(
                  width: 150,
                  initialSelection: item['mode']?.toString() ?? 'inherit',
                  dropdownMenuEntries: const [
                    DropdownMenuEntry(value: 'inherit', label: 'يتبع الصف'),
                    DropdownMenuEntry(value: 'enabled', label: 'متاح'),
                    DropdownMenuEntry(value: 'disabled', label: 'موقوف'),
                  ],
                  onSelected: (value) { if (value != null) apply({'action': 'student', 'student_id': item['id'], 'mode': value}); },
                ),
              );
            }),
          ]);
        },
      );
}

class AsyncListPage extends StatefulWidget {
  const AsyncListPage({super.key, required this.loader, required this.builder, required this.emptyText});
  final Future<List<dynamic>> Function() loader;
  final Widget Function(BuildContext, dynamic) builder;
  final String emptyText;
  @override
  State<AsyncListPage> createState() => _AsyncListPageState();
}

class _AsyncListPageState extends State<AsyncListPage> {
  late Future<List<dynamic>> future = widget.loader();
  Future<void> reload() async => setState(() => future = widget.loader());
  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: reload);
          final items = snapshot.data ?? const [];
          return RefreshIndicator(
            onRefresh: reload,
            child: items.isEmpty
                ? ListView(children: [Padding(padding: const EdgeInsets.all(32), child: Text(widget.emptyText, textAlign: TextAlign.center))])
                : ListView.separated(padding: const EdgeInsets.all(16), itemCount: items.length, separatorBuilder: (_, __) => const SizedBox(height: 8), itemBuilder: (context, i) => widget.builder(context, items[i])),
          );
        },
      );
}

class CoursesPage extends StatelessWidget {
  const CoursesPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(
        loader: () async => List<dynamic>.from(await api.get('courses/') as List),
        emptyText: 'لا توجد دورات منشورة.',
        builder: (context, item) {
          final course = Map<String, dynamic>.from(item as Map);
          final enrollment = course['enrollment'] as Map?;
          return Card(child: ListTile(
            leading: const CircleAvatar(child: Icon(Icons.play_lesson)),
            title: Text(course['title']?.toString() ?? ''),
            subtitle: Text('${course['subject']?['name'] ?? ''}${enrollment == null ? '' : ' · التقدم ${enrollment['progress_percent']}%'}'),
            trailing: const Icon(Icons.chevron_left),
            onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CoursePage(api: api, slug: course['slug'].toString()))),
          ));
        },
      );
}

class TeacherMobilePage extends StatelessWidget {
  const TeacherMobilePage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(
        loader: () async => List<dynamic>.from(await api.get('courses/') as List),
        emptyText: 'لا توجد دورات منشورة ضمن حساب المعلم.',
        builder: (context, raw) {
          final item = Map<String, dynamic>.from(raw as Map);
          return Card(child: ListTile(
            leading: const Icon(Icons.cast_for_education),
            title: Text(item['title']?.toString() ?? ''),
            subtitle: Text(item['subject']?['name']?.toString() ?? ''),
          ));
        },
      );
}

class CoursePage extends StatefulWidget {
  const CoursePage({super.key, required this.api, required this.slug});
  final ApiClient api;
  final String slug;
  @override
  State<CoursePage> createState() => _CoursePageState();
}

class _CoursePageState extends State<CoursePage> {
  late Future<Map<String, dynamic>> future = load();
  Future<Map<String, dynamic>> load() async => Map<String, dynamic>.from(await widget.api.get('courses/${Uri.encodeComponent(widget.slug)}/') as Map);
  Future<void> enroll() async {
    try {
      await widget.api.post('courses/${Uri.encodeComponent(widget.slug)}/enroll/');
      setState(() => future = load());
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }
  @override
  Widget build(BuildContext context) => Directionality(textDirection: TextDirection.rtl, child: Scaffold(
        appBar: AppBar(title: const Text('الدورة')),
        body: FutureBuilder<Map<String, dynamic>>(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () async => setState(() => future = load()));
            final course = snapshot.data!;
            final enrollment = course['enrollment'] as Map?;
            final hasAccess = course['has_access'] == true;
            final lessons = List<dynamic>.from(course['lessons'] as List? ?? const []);
            final assessments = List<dynamic>.from(course['assessments'] as List? ?? const []);
            return ListView(padding: const EdgeInsets.all(16), children: [
              Text(course['title'].toString(), style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8), Text(course['summary']?.toString() ?? ''),
              const SizedBox(height: 16),
              if (!hasAccess) const Card(child: Padding(padding: EdgeInsets.all(16), child: Text('تحتاج إلى اشتراك فعال يشمل مادة الدورة.'))),
              if (hasAccess && enrollment == null) FilledButton(onPressed: enroll, child: const Text('التسجيل والبدء')),
              if (enrollment != null) LinearProgressIndicator(value: ((enrollment['progress_percent'] as num?)?.toDouble() ?? 0) / 100),
              if (enrollment != null) Padding(padding: const EdgeInsets.only(top: 12), child: OutlinedButton.icon(onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AssistantPage(api: widget.api, courseSlug: widget.slug))), icon: const Icon(Icons.auto_awesome), label: const Text('مساعد محتوى الدورة'))),
              const SizedBox(height: 22), Text('الدروس', style: Theme.of(context).textTheme.titleLarge),
              ...lessons.map((raw) { final lesson = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(title: Text(lesson['title'].toString()), subtitle: Text('${lesson['duration_minutes']} دقيقة'), onTap: enrollment == null ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LessonPage(api: widget.api, courseSlug: widget.slug, lessonSlug: lesson['slug'].toString()))))); }),
              const SizedBox(height: 16), Text('التقييمات', style: Theme.of(context).textTheme.titleLarge),
              ...assessments.map((raw) { final assessment = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(title: Text(assessment['title'].toString()), subtitle: Text(assessment['type'] == 'quiz' ? 'اختبار إلكتروني' : 'واجب'), onTap: enrollment == null ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AssessmentPage(api: widget.api, courseSlug: widget.slug, assessmentSlug: assessment['slug'].toString()))))); }),
            ]);
          },
        ),
      ));
}

class LessonVideo extends StatefulWidget {
  const LessonVideo({super.key, required this.url});
  final String url;
  @override
  State<LessonVideo> createState() => _LessonVideoState();
}

class _LessonVideoState extends State<LessonVideo> {
  late final WebViewController controller;

  String _youtubeId(Uri uri) {
    if (uri.host.contains('youtu.be')) return uri.pathSegments.isNotEmpty ? uri.pathSegments.first : '';
    if (uri.pathSegments.contains('shorts')) {
      final i = uri.pathSegments.indexOf('shorts');
      return i + 1 < uri.pathSegments.length ? uri.pathSegments[i + 1] : '';
    }
    if (uri.pathSegments.contains('embed')) {
      final i = uri.pathSegments.indexOf('embed');
      return i + 1 < uri.pathSegments.length ? uri.pathSegments[i + 1] : '';
    }
    return uri.queryParameters['v'] ?? '';
  }

  @override
  void initState() {
    super.initState();
    controller = WebViewController()..setJavaScriptMode(JavaScriptMode.unrestricted);
    final uri = Uri.tryParse(widget.url);
    if (uri == null) return;
    final host = uri.host.toLowerCase();
    if (host.contains('youtube.com') || host.contains('youtu.be')) {
      final id = _youtubeId(uri);
      controller.loadRequest(Uri.parse('https://www.youtube-nocookie.com/embed/$id?playsinline=1&rel=0'));
    } else if (host.contains('vimeo.com') && uri.pathSegments.isNotEmpty) {
      controller.loadRequest(Uri.parse('https://player.vimeo.com/video/${uri.pathSegments.last}'));
    } else if (RegExp(r'\.(mp4|webm|ogg|m4v)(\?.*)?$', caseSensitive: false).hasMatch(widget.url)) {
      final escaped = const HtmlEscape().convert(widget.url);
      controller.loadHtmlString('<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#000"><video controls playsinline style="width:100%;height:100%" src="$escaped"></video></body></html>');
    } else {
      controller.loadRequest(uri);
    }
  }

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: AspectRatio(aspectRatio: 16 / 9, child: WebViewWidget(controller: controller)),
      );
}

class LessonPage extends StatefulWidget {
  const LessonPage({super.key, required this.api, required this.courseSlug, required this.lessonSlug});
  final ApiClient api;
  final String courseSlug;
  final String lessonSlug;
  @override
  State<LessonPage> createState() => _LessonPageState();
}

class _LessonPageState extends State<LessonPage> {
  late Future<Map<String, dynamic>> future = load();
  bool completing = false;
  Future<Map<String, dynamic>> load() async => Map<String, dynamic>.from(await widget.api.get('courses/${Uri.encodeComponent(widget.courseSlug)}/lessons/${Uri.encodeComponent(widget.lessonSlug)}/') as Map);
  Future<void> complete() async {
    setState(() => completing = true);
    try {
      final result = await widget.api.post('courses/${Uri.encodeComponent(widget.courseSlug)}/lessons/${Uri.encodeComponent(widget.lessonSlug)}/complete/') as Map;
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('تم الحفظ — التقدم ${result['progress_percent']}%')));
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally { if (mounted) setState(() => completing = false); }
  }
  @override
  Widget build(BuildContext context) => Directionality(textDirection: TextDirection.rtl, child: Scaffold(appBar: AppBar(title: const Text('الدرس')), body: FutureBuilder<Map<String, dynamic>>(future: future, builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () async => setState(() => future = load()));
        final lesson = snapshot.data!;
        final videoUrl = lesson['video_url']?.toString() ?? '';
        return ListView(padding: const EdgeInsets.all(20), children: [
          Text(lesson['title'].toString(), style: Theme.of(context).textTheme.headlineSmall),
          if (videoUrl.isNotEmpty) ...[const SizedBox(height: 16), LessonVideo(url: videoUrl)],
          const SizedBox(height: 16), SelectableText(lesson['content']?.toString() ?? ''),
          const SizedBox(height: 24), FilledButton.icon(onPressed: completing ? null : complete, icon: const Icon(Icons.check_circle), label: const Text('إكمال الدرس')),
        ]);
      })));
}

class AssessmentPage extends StatefulWidget {
  const AssessmentPage({super.key, required this.api, required this.courseSlug, required this.assessmentSlug});
  final ApiClient api;
  final String courseSlug;
  final String assessmentSlug;
  @override
  State<AssessmentPage> createState() => _AssessmentPageState();
}

class _AssessmentPageState extends State<AssessmentPage> {
  late Future<Map<String, dynamic>> future = load();
  final answers = <String, String>{};
  final assignment = TextEditingController();
  bool busy = false;
  Future<Map<String, dynamic>> load() async => Map<String, dynamic>.from(await widget.api.get('courses/${Uri.encodeComponent(widget.courseSlug)}/assessments/${Uri.encodeComponent(widget.assessmentSlug)}/') as Map);
  Future<void> submit(Map<String, dynamic> data) async {
    setState(() => busy = true);
    try {
      final body = data['type'] == 'quiz' ? {'answers': answers} : {'answer_text': assignment.text};
      final result = await widget.api.post('courses/${Uri.encodeComponent(widget.courseSlug)}/assessments/${Uri.encodeComponent(widget.assessmentSlug)}/submit/', body) as Map;
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result['score'] == null ? 'تم إرسال الواجب للتصحيح.' : 'العلامة: ${result['score']}')));
      setState(() => future = load());
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Directionality(textDirection: TextDirection.rtl, child: Scaffold(appBar: AppBar(title: const Text('التقييم')), body: FutureBuilder<Map<String, dynamic>>(future: future, builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () async => setState(() => future = load()));
        final data = snapshot.data!;
        final quiz = data['type'] == 'quiz';
        final questions = List<dynamic>.from(data['questions'] as List? ?? const []);
        return ListView(padding: const EdgeInsets.all(16), children: [
          Text(data['title'].toString(), style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8), Text(data['instructions']?.toString() ?? ''),
          if (quiz) ...questions.map((raw) {
            final q = Map<String, dynamic>.from(raw as Map);
            final choices = Map<String, dynamic>.from(q['choices'] as Map);
            final questionId = q['id'].toString();
            return Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(q['text'].toString(), style: Theme.of(context).textTheme.titleMedium),
                    RadioGroup<String>(
                      groupValue: answers[questionId],
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => answers[questionId] = value);
                        }
                      },
                      child: Column(
                        children: choices.entries
                            .map((e) => RadioListTile<String>(
                                  value: e.key,
                                  title: Text(e.value.toString()),
                                ))
                            .toList(),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
          if (!quiz) TextField(controller: assignment, minLines: 7, maxLines: 20, decoration: const InputDecoration(labelText: 'إجابة الواجب', border: OutlineInputBorder())),
          const SizedBox(height: 18), FilledButton(onPressed: busy ? null : () => submit(data), child: const Text('إرسال التقييم')),
        ]);
      })));
}

class AssistantPage extends StatefulWidget {
  const AssistantPage({super.key, required this.api, required this.courseSlug});
  final ApiClient api;
  final String courseSlug;
  @override
  State<AssistantPage> createState() => _AssistantPageState();
}

class _AssistantPageState extends State<AssistantPage> {
  final question = TextEditingController();
  bool busy = false;
  String? answer;
  List<dynamic> sources = const [];
  String? error;
  Future<void> ask() async {
    final text = question.text.trim();
    if (text.isEmpty) return;
    setState(() { busy = true; answer = null; error = null; sources = const []; });
    try {
      final data = Map<String, dynamic>.from(await widget.api.post('assistant/', {'course_slug': widget.courseSlug, 'question': text}) as Map);
      setState(() { answer = data['answer']?.toString() ?? ''; sources = List<dynamic>.from(data['sources'] as List? ?? const []); });
    } on ApiException catch (exc) { setState(() => error = exc.message); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => Directionality(textDirection: TextDirection.rtl, child: Scaffold(appBar: AppBar(title: const Text('مساعد المحتوى')), body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('اسأل ضمن محتوى الدروس المنشورة في هذه الدورة. الإجابة لا تستبدل المدرّس أو التقييم الرسمي.'),
        const SizedBox(height: 16), TextField(controller: question, minLines: 3, maxLines: 8, decoration: const InputDecoration(labelText: 'سؤالك', border: OutlineInputBorder())),
        const SizedBox(height: 12), FilledButton.icon(onPressed: busy ? null : ask, icon: const Icon(Icons.auto_awesome), label: const Text('إرسال السؤال')),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        if (answer != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Text(answer!), if (sources.isNotEmpty) ...[const Divider(), const Text('المراجع:'), ...sources.map((item) => Text('• $item'))]]))),
      ])));
}

class NotificationsPage extends StatelessWidget {
  const NotificationsPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(loader: () async => List<dynamic>.from(await api.get('notifications/') as List), emptyText: 'لا توجد إشعارات.', builder: (context, raw) { final item = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(leading: Icon(item['read_at'] == null ? Icons.notifications_active : Icons.notifications_none), title: Text(item['title'].toString()), subtitle: Text(item['body'].toString()), onTap: () async { await api.post('notifications/${item['id']}/read/'); })); });
}

class CertificatesPage extends StatelessWidget {
  const CertificatesPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(loader: () async => List<dynamic>.from(await api.get('certificates/') as List), emptyText: 'لا توجد شهادات صادرة.', builder: (context, raw) { final item = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(leading: const Icon(Icons.workspace_premium), title: Text(item['course']?['title']?.toString() ?? ''), subtitle: Text('الرقم: ${item['serial']}'))); });
}

class SubscriptionPage extends StatefulWidget {
  const SubscriptionPage({super.key, required this.api});
  final ApiClient api;
  @override
  State<SubscriptionPage> createState() => _SubscriptionPageState();
}

class _SubscriptionPageState extends State<SubscriptionPage> {
  final code = TextEditingController();
  bool busy = false;
  String? message;
  String? error;
  Future<void> redeem() async {
    final value = code.text.trim();
    if (value.isEmpty) return;
    setState(() { busy = true; message = null; error = null; });
    try {
      final result = Map<String, dynamic>.from(await widget.api.post('subscription-cards/redeem/', {'code': value}) as Map);
      setState(() => message = 'تم تفعيل البطاقة حتى ${result['expires_at'] ?? ''}.');
      code.clear();
    } on ApiException catch (exc) { setState(() => error = exc.message); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => ListView(padding: const EdgeInsets.all(16), children: [
        Text('تفعيل بطاقة الاشتراك', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        TextField(controller: code, textCapitalization: TextCapitalization.characters, decoration: const InputDecoration(labelText: 'رمز البطاقة', hintText: 'OPAL-XXXX-XXXX-XXXX-XXXX-XXXX', border: OutlineInputBorder())),
        const SizedBox(height: 10), FilledButton.icon(onPressed: busy ? null : redeem, icon: const Icon(Icons.verified), label: const Text('تفعيل البطاقة')),
        if (message != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(message!, style: const TextStyle(fontWeight: FontWeight.bold))),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 24), Text('الخطط المتاحة', style: Theme.of(context).textTheme.titleLarge),
        SizedBox(height: 420, child: AsyncListPage(loader: () async => List<dynamic>.from(await widget.api.get('subscription-plans/') as List), emptyText: 'لا توجد خطط متاحة.', builder: (context, raw) { final item = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(leading: const Icon(Icons.card_membership), title: Text(item['name'].toString()), subtitle: Text('${item['price']} ${item['currency']} · ${item['duration']}'))); })),
      ]);
}

class ErrorPane extends StatelessWidget {
  const ErrorPane({super.key, required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [Text(message, textAlign: TextAlign.center), const SizedBox(height: 12), OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة'))])));
}
