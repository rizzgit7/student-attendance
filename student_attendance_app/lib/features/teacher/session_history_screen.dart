// Teacher session history (§9).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/models.dart';
import '../../services/teacher_service.dart';

final sessionHistoryProvider = FutureProvider<List<TeacherSession>>(
    (ref) => ref.watch(teacherServiceProvider).history());

class SessionHistoryScreen extends ConsumerWidget {
  const SessionHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(sessionHistoryProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Session history')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(sessionHistoryProvider),
        child: history.when(
          loading: () =>
              const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(padding: const EdgeInsets.all(24), child: Text('$e')),
          ]),
          data: (sessions) => sessions.isEmpty
              ? const Center(child: Text('No sessions yet.'))
              : ListView.builder(
                  itemCount: sessions.length,
                  itemBuilder: (context, i) {
                    final s = sessions[i];
                    return Card(
                      child: ListTile(
                        leading: Icon(
                          s.status == 'OPEN'
                              ? Icons.radio_button_checked
                              : Icons.check_circle,
                          color: s.status == 'OPEN'
                              ? Colors.green
                              : Colors.grey,
                        ),
                        title: Text('${s.subject} · ${s.klass}-${s.section}'),
                        subtitle: Text(
                            'Present ${s.presentCount} · Late ${s.lateCount}'),
                        onTap: s.status == 'OPEN'
                            ? () =>
                                context.go('/teacher/session/${s.id}')
                            : null,
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}
