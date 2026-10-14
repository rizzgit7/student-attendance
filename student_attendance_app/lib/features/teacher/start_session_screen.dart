// Start an attendance session: select section + subject (§9).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../services/teacher_service.dart';
import 'teacher_home_screen.dart';

class StartSessionScreen extends ConsumerStatefulWidget {
  const StartSessionScreen({super.key, this.sectionId, this.subjectId});

  final int? sectionId;
  final int? subjectId;

  @override
  ConsumerState<StartSessionScreen> createState() =>
      _StartSessionScreenState();
}

class _StartSessionScreenState extends ConsumerState<StartSessionScreen> {
  int? _sectionId;
  int? _subjectId;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _sectionId = widget.sectionId;
    _subjectId = widget.subjectId;
  }

  Future<void> _start() async {
    if (_sectionId == null || _subjectId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Pick a section and a subject')));
      return;
    }
    setState(() => _busy = true);
    try {
      // Backend sets server time and generates the code (§10/§11).
      final session = await ref.read(teacherServiceProvider).startSession(
            sectionId: _sectionId!,
            subjectId: _subjectId!,
          );
      if (mounted) {
        context.go('/teacher/session/${session.id}');
      }
    } catch (e) {
      // AppException.toString() is the API's own message (e.g. the 403 that
      // says a teacher is not assigned to this subject/class).
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _hint(String text) {
    return Card(
      margin: const EdgeInsets.only(top: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(text, textAlign: TextAlign.center),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final options = ref.watch(staffOptionsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Start attendance')),
      body: options.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Padding(padding: const EdgeInsets.all(24), child: Text('$e')),
        ),
        data: (opts) {
          // Only combinations the API will accept may be offered: a session
          // for an unassigned subject/section comes back as 403.
          final sections = opts.teachableSections;
          final sectionId =
              sections.any((s) => s.id == _sectionId) ? _sectionId : null;
          final subjects = opts.subjectsFor(sectionId);
          final subjectId =
              subjects.any((s) => s.id == _subjectId) ? _subjectId : null;
          final canStart = sectionId != null && subjectId != null;

          return Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (sections.isEmpty)
                  _hint('No class or subject is assigned to you yet. Ask your '
                      'administrator to assign you in the web dashboard '
                      '(Assign teacher → subject/section).')
                else ...[
                  DropdownButtonFormField<int>(
                    key: ValueKey(
                        'sections-${sections.map((s) => s.id).join('-')}'),
                    initialValue: sectionId,
                    decoration: const InputDecoration(
                        labelText: 'Class / Section',
                        border: OutlineInputBorder()),
                    items: sections
                        .map((s) => DropdownMenuItem(
                            value: s.id, child: Text(s.name)))
                        .toList(),
                    onChanged: (v) => setState(() {
                      // The subject list depends on the class: drop a choice
                      // that is no longer valid rather than sending a 403.
                      _sectionId = v;
                      _subjectId = null;
                    }),
                  ),
                  const SizedBox(height: 16),
                  if (subjects.isEmpty)
                    _hint('No subject is assigned to you for this class. Ask '
                        'your administrator to create the assignment.')
                  else
                    DropdownButtonFormField<int>(
                      key: ValueKey('subject-$sectionId'),
                      initialValue: subjectId,
                      decoration: const InputDecoration(
                          labelText: 'Subject',
                          border: OutlineInputBorder()),
                      items: subjects
                          .map((s) => DropdownMenuItem(
                              value: s.id, child: Text(s.name)))
                          .toList(),
                      onChanged: (v) => setState(() => _subjectId = v),
                    ),
                ],
                const SizedBox(height: 24),
                FilledButton.icon(
                  icon: const Icon(Icons.play_arrow),
                  label: _busy
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Start session'),
                  onPressed: (_busy || !canStart) ? null : _start,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
