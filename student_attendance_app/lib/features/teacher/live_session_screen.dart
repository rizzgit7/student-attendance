// Live session: 6-digit code, countdown, live counts, close (§9).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/models.dart';
import '../../services/teacher_service.dart';

class LiveSessionScreen extends ConsumerStatefulWidget {
  const LiveSessionScreen({super.key, required this.sessionId});

  final int sessionId;

  @override
  ConsumerState<LiveSessionScreen> createState() =>
      _LiveSessionScreenState();
}

class _LiveSessionScreenState extends ConsumerState<LiveSessionScreen> {
  TeacherSession? _session;
  Timer? _poll;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
    // live present/late count (§9)
    _poll = Timer.periodic(
        const Duration(seconds: 3), (_) => _load(silent: true));
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load({bool silent = false}) async {
    try {
      final session =
          await ref.read(teacherServiceProvider).session(widget.sessionId);
      setState(() {
        _session = session;
        _error = null;
      });
    } catch (e) {
      if (!silent) setState(() => _error = '$e');
    }
  }

  Future<void> _rotate() async {
    try {
      final session = await ref
          .read(teacherServiceProvider)
          .rotateCode(widget.sessionId);
      setState(() => _session = session);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _close() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Close session?'),
        content: const Text('Students will no longer be able to check in.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Close')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(teacherServiceProvider).close(widget.sessionId);
      if (mounted) context.go('/teacher');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = _session;
    return Scaffold(
      appBar: AppBar(
        title: Text(session == null
            ? 'Session'
            : '${session.subject} · ${session.klass}-${session.section}'),
      ),
      body: session == null
          ? Center(
              child: _error == null
                  ? const CircularProgressIndicator()
                  : Text(_error!),
            )
          : Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Card(
                    color: Colors.indigo.shade50,
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        children: [
                          Text(
                            session.codeValid && session.code != null
                                ? session.code!
                                : '– – – – – –',
                            style: const TextStyle(
                              fontSize: 48,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 12,
                              fontFeatures: [],
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            session.status == 'CLOSED'
                                ? 'Session closed'
                                : session.codeValid
                                    ? 'Expires in ${session.codeSecondsLeft}s'
                                    : 'Code expired — rotate for a new one',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          if (session.status == 'OPEN')
                            TextButton.icon(
                              icon: const Icon(Icons.refresh),
                              label: const Text('Rotate code'),
                              onPressed: _rotate,
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _Stat(
                          label: 'Present',
                          value: session.presentCount,
                          color: Colors.green),
                      _Stat(
                          label: 'Late',
                          value: session.lateCount,
                          color: Colors.orange),
                      _Stat(
                          label: 'Total',
                          value: session.presentCount + session.lateCount,
                          color: Colors.indigo),
                    ],
                  ),
                  const Spacer(),
                  if (session.status == 'OPEN')
                    FilledButton.icon(
                      style:
                          FilledButton.styleFrom(backgroundColor: Colors.red),
                      icon: const Icon(Icons.stop_circle),
                      label: const Text('Close session'),
                      onPressed: _close,
                    ),
                ],
              ),
            ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value, required this.color});

  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Text('$value',
          style: TextStyle(
              fontSize: 36, fontWeight: FontWeight.bold, color: color)),
      Text(label),
    ]);
  }
}
