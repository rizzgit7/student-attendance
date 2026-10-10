// Enter the 6-digit code and see the result (§8: code entry + result).
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/errors.dart';
import '../../models/models.dart';
import '../../services/attendance_service.dart';

class EnterCodeScreen extends ConsumerStatefulWidget {
  const EnterCodeScreen({super.key});

  @override
  ConsumerState<EnterCodeScreen> createState() => _EnterCodeScreenState();
}

class _EnterCodeScreenState extends ConsumerState<EnterCodeScreen> {
  final _code = TextEditingController();
  bool _busy = false;
  String? _error;
  AttendanceRecord? _result;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final code = _code.text.trim();
    if (code.length != 6) {
      setState(() => _error = 'Enter the full 6-digit code');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _result = null;
    });
    try {
      final record =
          await ref.read(attendanceServiceProvider).checkIn(code);
      setState(() => _result = record);
    } catch (e) {
      setState(
          () => _error = e is AppException ? e.message : 'Check-in failed');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Enter attendance code')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_result != null) ...[
              const SizedBox(height: 24),
              Icon(
                _result!.status == 'PRESENT' ? Icons.check_circle : Icons.timer,
                size: 96,
                color: _result!.status == 'PRESENT'
                    ? Colors.green
                    : Colors.orange,
              ),
              const SizedBox(height: 16),
              Text(
                _result!.status == 'PRESENT' ? 'PRESENT' : 'LATE',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              Text('${_result!.subject} — marked at server time',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: () {
                  setState(() {
                    _result = null;
                    _code.clear();
                  });
                },
                child: const Text('Enter another code'),
              ),
            ] else ...[
              TextField(
                controller: _code,
                keyboardType: TextInputType.number,
                maxLength: 6,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 32, letterSpacing: 12, fontWeight: FontWeight.bold),
                decoration: const InputDecoration(
                  counterText: '',
                  labelText: '6-digit code from your teacher',
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _submit(),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!,
                    style: const TextStyle(color: Colors.red),
                    textAlign: TextAlign.center),
              ],
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Check in'),
              ),
              const SizedBox(height: 12),
              const Text(
                'The code rotates every 30–60 seconds. Ask your teacher for the current one.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
