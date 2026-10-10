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
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sections = ref.watch(sectionsProvider);
    final subjects = ref.watch(subjectsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Start attendance')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            sections.when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
              data: (items) => DropdownButtonFormField<int>(
                initialValue: _sectionId,
                decoration: const InputDecoration(
                    labelText: 'Class / Section',
                    border: OutlineInputBorder()),
                items: items
                    .map((s) => DropdownMenuItem(
                        value: s.id, child: Text(s.name)))
                    .toList(),
                onChanged: (v) => setState(() => _sectionId = v),
              ),
            ),
            const SizedBox(height: 16),
            subjects.when(
              loading: () => const LinearProgressIndicator(),
              error: (e, _) => Text('$e'),
              data: (items) => DropdownButtonFormField<int>(
                initialValue: _subjectId,
                decoration: const InputDecoration(
                    labelText: 'Subject', border: OutlineInputBorder()),
                items: items
                    .map((s) => DropdownMenuItem(
                        value: s.id, child: Text(s.name)))
                    .toList(),
                onChanged: (v) => setState(() => _subjectId = v),
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              icon: const Icon(Icons.play_arrow),
              label: _busy
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Start session'),
              onPressed: _busy ? null : _start,
            ),
          ],
        ),
      ),
    );
  }
}
