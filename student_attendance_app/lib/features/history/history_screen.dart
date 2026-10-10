// Attendance history + subject-wise summary (§8).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../models/models.dart';
import '../../services/attendance_service.dart';

final historyProvider = FutureProvider<List<AttendanceRecord>>((ref) =>
    ref.watch(attendanceServiceProvider).history());

final summaryProvider = FutureProvider<List<SubjectSummary>>((ref) =>
    ref.watch(attendanceServiceProvider).summary());

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(historyProvider);
    final summary = ref.watch(summaryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Attendance history')),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(historyProvider);
          ref.invalidate(summaryProvider);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Subject-wise', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            summary.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Text('$e'),
              data: (subjects) => Column(children: [
                ...subjects.map((s) => Card(
                      child: ListTile(
                        title: Text(s.subject),
                        subtitle: LinearProgressIndicator(
                            value: s.percentage / 100),
                        trailing: Text('${s.percentage.toStringAsFixed(1)}%',
                            style: Theme.of(context).textTheme.titleMedium),
                      ),
                    )),
              ]),
            ),
            const SizedBox(height: 16),
            Text('All records', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            history.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Text('$e'),
              data: (records) => records.isEmpty
                  ? const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No attendance records yet.'),
                      ),
                    )
                  : Column(children: [
                      ...records.map((r) => Card(
                            child: ListTile(
                              leading: Icon(
                                r.status == 'PRESENT'
                                    ? Icons.check_circle
                                    : Icons.timer,
                                color: r.status == 'PRESENT'
                                    ? Colors.green
                                    : Colors.orange,
                              ),
                              title: Text(r.subject),
                              subtitle: Text(DateFormat('dd MMM yyyy, HH:mm')
                                  .format(r.recordedAt.toLocal())),
                              trailing: r.isCorrected
                                  ? const Icon(Icons.edit, size: 18)
                                  : null,
                            ),
                          )),
                    ]),
            ),
          ],
        ),
      ),
    );
  }
}
