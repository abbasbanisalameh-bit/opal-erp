import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const apiBase = String.fromEnvironment(
  'OPAL_API_BASE_URL',
  defaultValue: 'https://example.invalid/learning/api/v1',
);

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OpalLearningApp());
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class ApiClient {
  ApiClient(this.storage);
  final FlutterSecureStorage storage;
  String? token;

  Future<void> loadToken() async {
    token = await storage.read(key: 'learning_api_token');
  }

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
      final message = payload is Map
          ? (payload['error']?['message']?.toString() ?? 'تعذر إكمال الطلب.')
          : 'تعذر إكمال الطلب.';
      throw ApiException(message, statusCode: response.statusCode);
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

  Future<Map<String, dynamic>> login(String email, String password) async {
    final data = await post('auth/login/', {
      'email': email,
      'password': password,
      'device_name': 'Flutter Mobile',
    }) as Map<String, dynamic>;
    token = data['token']?.toString();
    if (token == null || token!.isEmpty) throw ApiException('لم يصدر الخادم رمز دخول.');
    await storage.write(key: 'learning_api_token', value: token);
    return Map<String, dynamic>.from(data['account'] as Map);
  }

  Future<void> logout() async {
    try {
      if (token != null) await post('auth/logout/');
    } finally {
      token = null;
      await storage.delete(key: 'learning_api_token');
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

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await api.loadToken();
    if (api.token != null) {
      try {
        account = Map<String, dynamic>.from(await api.get('me/') as Map);
      } catch (_) {
        await api.logout();
      }
    }
    if (mounted) setState(() => loading = false);
  }

  void signedIn(Map<String, dynamic> value) => setState(() => account = value);
  Future<void> signedOut() async {
    await api.logout();
    if (mounted) setState(() => account = null);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'منصة أوبال التعليمية',
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
                : HomePage(api: api, account: account!, onSignedOut: signedOut),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.api, required this.onSignedIn});
  final ApiClient api;
  final ValueChanged<Map<String, dynamic>> onSignedIn;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final email = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;

  Future<void> submit() async {
    setState(() { busy = true; error = null; });
    try {
      final account = await widget.api.login(email.text.trim(), password.text);
      widget.onSignedIn(account);
    } on ApiException catch (exc) {
      setState(() => error = exc.message);
    } catch (_) {
      setState(() => error = 'تعذر الاتصال بالخادم.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
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
                    Text('منصة أوبال التعليمية', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 24),
                    TextField(controller: email, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], decoration: const InputDecoration(labelText: 'البريد الإلكتروني', border: OutlineInputBorder())),
                    const SizedBox(height: 12),
                    TextField(controller: password, obscureText: true, autofillHints: const [AutofillHints.password], decoration: const InputDecoration(labelText: 'كلمة المرور', border: OutlineInputBorder())),
                    if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
                    const SizedBox(height: 18),
                    FilledButton(onPressed: busy ? null : submit, child: busy ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('دخول')),
                    const SizedBox(height: 12),
                    const Text('أنشئ الحساب ووثّق البريد واقبل السياسات من موقع المنصة أولًا.', textAlign: TextAlign.center),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.api, required this.account, required this.onSignedOut});
  final ApiClient api;
  final Map<String, dynamic> account;
  final Future<void> Function() onSignedOut;
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int index = 0;
  @override
  Widget build(BuildContext context) {
    final pages = [
      CoursesPage(api: widget.api),
      NotificationsPage(api: widget.api),
      CertificatesPage(api: widget.api),
      PlansPage(api: widget.api),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.account['full_name']?.toString() ?? 'أوبال تعليم'),
        actions: [IconButton(onPressed: widget.onSignedOut, tooltip: 'تسجيل الخروج', icon: const Icon(Icons.logout))],
      ),
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.menu_book), label: 'الدورات'),
          NavigationDestination(icon: Icon(Icons.notifications), label: 'الإشعارات'),
          NavigationDestination(icon: Icon(Icons.workspace_premium), label: 'الشهادات'),
          NavigationDestination(icon: Icon(Icons.card_membership), label: 'الخطط'),
        ],
      ),
    );
  }
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
  late Future<List<dynamic>> future;

  @override
  void initState() {
    super.initState();
    future = widget.loader();
  }

  Future<void> reload() async => setState(() => future = widget.loader());
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<dynamic>>(
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
}

class CoursesPage extends StatelessWidget {
  const CoursesPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) {
    return AsyncListPage(
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
  Widget build(BuildContext context) {
    return Directionality(textDirection: TextDirection.rtl, child: Scaffold(
      appBar: AppBar(title: const Text('الدورة')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () => setState(() => future = load()));
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
            if (enrollment != null) Padding(
              padding: const EdgeInsets.only(top: 12),
              child: OutlinedButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AssistantPage(api: widget.api, courseSlug: widget.slug))),
                icon: const Icon(Icons.auto_awesome),
                label: const Text('مساعد محتوى الدورة'),
              ),
            ),
            const SizedBox(height: 22), Text('الدروس', style: Theme.of(context).textTheme.titleLarge),
            ...lessons.map((raw) { final lesson = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(title: Text(lesson['title'].toString()), subtitle: Text('${lesson['duration_minutes']} دقيقة'), onTap: enrollment == null ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LessonPage(api: widget.api, courseSlug: widget.slug, lessonSlug: lesson['slug'].toString()))))); }),
            const SizedBox(height: 16), Text('التقييمات', style: Theme.of(context).textTheme.titleLarge),
            ...assessments.map((raw) { final assessment = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(title: Text(assessment['title'].toString()), subtitle: Text(assessment['type'] == 'quiz' ? 'اختبار إلكتروني' : 'واجب'), onTap: enrollment == null ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => AssessmentPage(api: widget.api, courseSlug: widget.slug, assessmentSlug: assessment['slug'].toString()))))); }),
          ]);
        },
      ),
    ));
  }
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
    if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () => setState(() => future = load()));
    final lesson = snapshot.data!;
    return ListView(padding: const EdgeInsets.all(20), children: [Text(lesson['title'].toString(), style: Theme.of(context).textTheme.headlineSmall), const SizedBox(height: 16), SelectableText(lesson['content']?.toString() ?? ''), const SizedBox(height: 24), FilledButton.icon(onPressed: completing ? null : complete, icon: const Icon(Icons.check_circle), label: const Text('إكمال الدرس'))]);
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
    if (snapshot.hasError) return ErrorPane(message: snapshot.error.toString(), onRetry: () => setState(() => future = load()));
    final data = snapshot.data!;
    final quiz = data['type'] == 'quiz';
    final questions = List<dynamic>.from(data['questions'] as List? ?? const []);
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text(data['title'].toString(), style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: 8), Text(data['instructions']?.toString() ?? ''),
      if (quiz) ...questions.map((raw) { final q = Map<String, dynamic>.from(raw as Map); final choices = Map<String, dynamic>.from(q['choices'] as Map); return Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Text(q['text'].toString(), style: Theme.of(context).textTheme.titleMedium), ...choices.entries.map((e) => RadioListTile<String>(value: e.key, groupValue: answers[q['id'].toString()], title: Text(e.value.toString()), onChanged: (value) => setState(() => answers[q['id'].toString()] = value!)))]))); }),
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
      setState(() {
        answer = data['answer']?.toString() ?? '';
        sources = List<dynamic>.from(data['sources'] as List? ?? const []);
      });
    } on ApiException catch (exc) {
      setState(() => error = exc.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Directionality(
    textDirection: TextDirection.rtl,
    child: Scaffold(
      appBar: AppBar(title: const Text('مساعد المحتوى')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('اسأل ضمن محتوى الدروس المنشورة في هذه الدورة. الإجابة لا تستبدل المدرّس أو التقييم الرسمي.'),
          const SizedBox(height: 16),
          TextField(controller: question, minLines: 3, maxLines: 8, decoration: const InputDecoration(labelText: 'سؤالك', border: OutlineInputBorder())),
          const SizedBox(height: 12),
          FilledButton.icon(onPressed: busy ? null : ask, icon: const Icon(Icons.auto_awesome), label: const Text('إرسال السؤال')),
          if (error != null) Padding(padding: const EdgeInsets.only(top: 16), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
          if (answer != null) Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Text(answer!), if (sources.isNotEmpty) ...[const Divider(), const Text('المراجع:'), ...sources.map((item) => Text('• $item'))]]))),
        ],
      ),
    ),
  );
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

class PlansPage extends StatelessWidget {
  const PlansPage({super.key, required this.api});
  final ApiClient api;
  @override
  Widget build(BuildContext context) => AsyncListPage(loader: () async => List<dynamic>.from(await api.get('subscription-plans/') as List), emptyText: 'لا توجد خطط متاحة.', builder: (context, raw) { final item = Map<String, dynamic>.from(raw as Map); return Card(child: ListTile(leading: const Icon(Icons.card_membership), title: Text(item['name'].toString()), subtitle: Text('${item['price']} ${item['currency']} · ${item['duration']}'))); });
}

class ErrorPane extends StatelessWidget {
  const ErrorPane({super.key, required this.message, required this.onRetry});
  final String message;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [Text(message, textAlign: TextAlign.center), const SizedBox(height: 12), OutlinedButton(onPressed: onRetry, child: const Text('إعادة المحاولة'))])));
}
