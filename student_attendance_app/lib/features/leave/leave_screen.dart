// Leave requests: submit + history (§8).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/models.dart';
import '../../services/attendance_service.dart';

final leavesProvider = FutureProvider<List<LeaveRequest>>((ref) =>
    ref.watch(attendanceServiceProvider).myLeaves());

class LeaveScreen extends ConsumerStatefulWidget {
  const LeaveScreen({super.key});

  @override
  ConsumerState<LeaveScreen> createState() => _LeaveScreenState();
}

class _LeaveScreenState extends ConsumerState<LeaveScreen> {
  final _reason = TextEditingController();
  DateTime? _from;
  DateTime? _to;
  bool _busy = false;

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  String _fmt(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate(bool isFrom) async {
    final picked = await showDatePicker(
      context: context,
      firstDate: DateTime.now().subtract(const Duration(days: 30)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() => isFrom ? _from = picked : _to = picked);
    }
  }

  Future<void> _submit() async {
    if (_from == null || _to == null || _reason.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Pick dates and enter a reason')));
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(attendanceServiceProvider).requestLeave(
            fromDate: _fmt(_from!),
            toDate: _fmt(_to!),
            reason: _reason.text.trim(),
          );
      _reason.clear();
      ref.invalidate(leavesProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Leave request submitted')));
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
    final leaves = ref.watch(leavesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Leave requests')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => _pickDate(true),
                        child: Text(_from == null
                            ? 'From date'
                            : 'From: ${_fmt(_from!)}'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => _pickDate(false),
                        child: Text(
                            _to == null ? 'To date' : 'To: ${_fmt(_to!)}'),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _reason,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Reason',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 8),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: const Text('Submit request'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('My requests', style: Theme.of(context).textTheme.titleMedium),
          leaves.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (e, _) => Text('$e'),
            data: (items) => items.isEmpty
                ? const Text('No leave requests yet.')
                : Column(children: [
                    ...items.map((l) => Card(
                          child: ListTile(
                            title: Text('${l.fromDate} → ${l.toDate}'),
                            subtitle: Text(l.reason),
                            trailing: Chip(
                              label: Text(l.status),
                              backgroundColor: l.status == 'APPROVED'
                                  ? Colors.green.shade100
                                  : l.status == 'REJECTED'
                                      ? Colors.red.shade100
                                      : Colors.grey.shade200,
                            ),
                          ),
                        )),
                  ]),
          ),
        ],
      ),
    );
  }
}
