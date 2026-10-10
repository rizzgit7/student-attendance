// Profile/settings + logout (§8).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config.dart';
import '../../services/auth_service.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider).valueOrNull;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (user != null) ...[
            Card(
              child: Column(children: [
                const ListTile(
                  leading: Icon(Icons.badge, size: 40),
                  title: Text('Account'),
                ),
                ListTile(
                    dense: true,
                    title: const Text('Name'),
                    trailing: Text(user.fullName)),
                ListTile(
                    dense: true,
                    title: const Text('Email'),
                    trailing: Text(user.email)),
                ListTile(
                    dense: true,
                    title: const Text('Role'),
                    trailing: Text(user.role)),
                ListTile(
                    dense: true,
                    title: const Text('Institution'),
                    trailing: Text('#${user.institutionId}')),
              ]),
            ),
          ],
          Card(
            child: ListTile(
              dense: true,
              title: const Text('API server'),
              trailing: Text(AppConfig.baseUrl,
                  style: Theme.of(context).textTheme.bodySmall),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            icon: const Icon(Icons.logout),
            label: const Text('Logout'),
            onPressed: () async {
              await ref.read(authProvider.notifier).logout();
              // router redirect sends the user to /login
            },
          ),
        ],
      ),
    );
  }
}
