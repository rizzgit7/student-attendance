// go_router setup (§4): role-aware shell — student tabs vs teacher tabs.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/attendance/enter_code_screen.dart';
import '../features/auth/login_screen.dart';
import '../features/history/history_screen.dart';
import '../features/home/student_home_screen.dart';
import '../features/leave/leave_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/teacher/live_session_screen.dart';
import '../features/teacher/session_history_screen.dart';
import '../features/teacher/start_session_screen.dart';
import '../features/teacher/teacher_home_screen.dart';
import '../services/auth_service.dart';

final routerProvider = Provider<GoRouter>((ref) {
  // Do NOT watch authProvider here — recreating the whole GoRouter on every
  // auth change resets navigation and visibly "flashes" the login screen.
  // _AuthRefresh already notifies go_router to re-run the redirect below.
  final router = GoRouter(
    initialLocation: '/login',
    refreshListenable: _AuthRefresh(ref),
    redirect: (context, state) {
      final user = ref.read(authProvider).valueOrNull;
      final loggingIn = state.matchedLocation == '/login';
      if (user == null) return loggingIn ? null : '/login';
      if (loggingIn) return user.isStaff ? '/teacher' : '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      GoRoute(
        path: '/home',
        builder: (_, __) => const StudentHomeScreen(),
        routes: [
          GoRoute(
              path: 'code', builder: (_, __) => const EnterCodeScreen()),
          GoRoute(
              path: 'history',
              builder: (_, __) => const HistoryScreen()),
          GoRoute(
              path: 'leave', builder: (_, __) => const LeaveScreen()),
          GoRoute(
              path: 'profile',
              builder: (_, __) => const ProfileScreen()),
        ],
      ),
      GoRoute(
        path: '/teacher',
        builder: (_, __) => const TeacherHomeScreen(),
        routes: [
          GoRoute(
            path: 'start',
            builder: (_, state) => StartSessionScreen(
              sectionId: state.uri.queryParameters['section'] != null
                  ? int.parse(state.uri.queryParameters['section']!)
                  : null,
              subjectId: state.uri.queryParameters['subject'] != null
                  ? int.parse(state.uri.queryParameters['subject']!)
                  : null,
            ),
          ),
          GoRoute(
            path: 'session/:id',
            builder: (_, state) =>
                LiveSessionScreen(sessionId: int.parse(state.pathParameters['id']!)),
          ),
          GoRoute(
            path: 'history',
            builder: (_, __) => const SessionHistoryScreen(),
          ),
        ],
      ),
    ],
  );

  ref.onDispose(router.dispose);
  return router;
});

/// Bridges Riverpod state changes into go_router's refresh mechanism.
class _AuthRefresh extends ChangeNotifier {
  _AuthRefresh(this.ref) {
    ref.listen(authProvider, (_, __) => notifyListeners());
  }
  final Ref ref;
}
