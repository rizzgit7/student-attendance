// Student home: today's classes + attendance snapshot (§8).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/errors.dart';
import '../../models/models.dart';
import '../../services/attendance_service.dart';
import '../../services/auth_service.dart';

final dashboardProvider = FutureProvider<Dashboard>((ref) =>
    ref.watch(attendanceServiceProvider).dashboard());

class StudentHomeScreen extends ConsumerWidget {
  const StudentHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboard = ref.watch(dashboardProvider);
    final user = ref.watch(authProvider).valueOrNull;

    return Scaffold(
      appBar: AppBar(
        title: Text('Hello, ${user?.fullName.split(' ').first ?? ''}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person),
            onPressed: () => context.go('/home/profile'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(dashboardProvider.future),
        child: dashboard.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(e is AppException ? e.message : 'Something went wrong'),
            ),
          ]),
          data: (data) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: ListTile(
                  leading: const Icon(Icons.pie_chart, color: Colors.indigo),
                  title: Text(
                      'Attendance: ${data.percentage.toStringAsFixed(1)}%'),
                  subtitle: const Text('Across all subjects so far'),
                ),
              ),
              const SizedBox(height: 8),
              Text("Today's classes",
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              if (data.classes.isEmpty)
                const Card(
                    child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No classes scheduled today.'),
                )),
              ...data.classes.map((c) => Card(
                    child: ListTile(
                      leading: Icon(
                        c.marked ? Icons.check_circle : Icons.radio_button_unchecked,
                        color: c.marked ? Colors.green : Colors.grey,
                      ),
                      title: Text(c.subject),
                      subtitle: Text(DateFormat('HH:mm')
                          .format(c.scheduledStart.toLocal())),
                      trailing: Text(c.myStatus ?? (c.marked ? '' : 'Not marked')),
                    ),
                  )),
              const SizedBox(height: 8),
              FilledButton.icon(
                icon: const Icon(Icons.password),
                label: const Text('Enter attendance code'),
                onPressed: () => context.go('/home/code'),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                icon: const Icon(Icons.history),
                label: const Text('Attendance history'),
                onPressed: () => context.go('/home/history'),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                icon: const Icon(Icons.event_busy),
                label: Text('Leave requests${data.pendingLeaves > 0 ? ' (${data.pendingLeaves} pending)' : ''}'),
                onPressed: () => context.go('/home/leave'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
