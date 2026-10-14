// Teacher home: pick class/section/subject and start attendance (§9).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/models.dart';
import '../../services/auth_service.dart';
import '../../services/teacher_service.dart';

/// Sections/subjects/assignments the signed-in staff may use. Teachers only
/// get the pairs they are assigned to, so the pick-lists can never offer a
/// combination the API answers with 403.
final staffOptionsProvider = FutureProvider<StaffOptions>((ref) =>
    ref.watch(teacherServiceProvider).options());

class TeacherHomeScreen extends ConsumerWidget {
  const TeacherHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider).valueOrNull;
    return Scaffold(
      appBar: AppBar(
        title: Text(user?.fullName ?? 'Teacher'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FilledButton.icon(
              icon: const Icon(Icons.play_circle),
              label: const Text('Start attendance session'),
              onPressed: () => context.go('/teacher/start'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.history),
              label: const Text('Session history'),
              onPressed: () => context.go('/teacher/history'),
            ),
            const Spacer(),
            const Text(
              'Students check in with the 6-digit code shown on the live '
              'session screen. Codes rotate every 30–60 seconds.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}
