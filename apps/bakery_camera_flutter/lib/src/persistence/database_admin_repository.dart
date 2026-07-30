import '../admin/admin_models.dart';
import '../admin/admin_repository.dart';
import 'app_database.dart';

/// Read projections over immutable checkout evidence. It never writes audit data.
final class DatabaseAdminRepository implements AdminRepository {
  DatabaseAdminRepository(this._database);

  final BakeryDatabase _database;

  @override
  Future<AdminDashboardSummary> dashboard(DateRange range) async {
    final sessions = await _database.select(_database.checkoutSessions).get();
    final attempts = await _database.select(_database.scanAttempts).get();
    final objects = await _database.select(_database.inferenceObjects).get();
    final resolutions = await _database
        .select(_database.objectResolutions)
        .get();
    final orders = await _database.select(_database.finalOrders).get();
    final payments = await _database.select(_database.simulatedPayments).get();

    final sessionById = {
      for (final session in sessions) session.sessionId: session,
    };
    final inRangeSessions = sessions
        .where((row) => range.includes(_utc(row.startedAtUs)))
        .toList(growable: false);
    final sessionIds = inRangeSessions.map((row) => row.sessionId).toSet();
    final inRangeAttempts = attempts
        .where((row) => sessionIds.contains(row.sessionId))
        .toList(growable: false);
    final attemptIds = inRangeAttempts.map((row) => row.attemptId).toSet();
    final inRangeObjects = objects
        .where((row) => attemptIds.contains(row.attemptId))
        .toList(growable: false);
    final objectById = {
      for (final object in inRangeObjects) object.inferenceObjectId: object,
    };

    final committedPayments = payments
        .where((payment) {
          final session = sessionById[payment.sessionId];
          return session?.state == 'completed' &&
              range.includes(_utc(payment.paidAtUs));
        })
        .toList(growable: false);
    final committedOrderIds = committedPayments
        .map((row) => row.orderId)
        .toSet();
    final committedOrders = orders
        .where((order) => committedOrderIds.contains(order.orderId))
        .toList(growable: false);

    final currentResolutions = resolutions
        .where((row) => row.isCurrent && sessionIds.contains(row.sessionId))
        .toList(growable: false);
    final resolvedUnknownIds = currentResolutions
        .where(
          (row) =>
              row.inferenceObjectId != null &&
              objectById[row.inferenceObjectId]?.skuId == null,
        )
        .map((row) => row.inferenceObjectId!)
        .toSet();
    final unknownObjectIds = inRangeObjects
        .where((row) => row.skuId == null)
        .map((row) => row.inferenceObjectId)
        .toSet();
    final attemptsBySession = <String, int>{};
    for (final attempt in inRangeAttempts) {
      attemptsBySession.update(
        attempt.sessionId,
        (count) => count + 1,
        ifAbsent: () => 1,
      );
    }

    return AdminDashboardSummary(
      completedOrders: committedOrders.length,
      grossKrw: committedPayments.fold(0, (sum, row) => sum + row.amountKrw),
      scanAttempts: inRangeAttempts.length,
      retakeSessions: attemptsBySession.values
          .where((count) => count > 1)
          .length,
      unknownObjects: unknownObjectIds.length,
      customerResolvedUnknownObjects: resolvedUnknownIds.length,
      customerOverrides: currentResolutions
          .where((row) => row.source == 'customer_overrode_auto')
          .length,
      manualCartLines: currentResolutions
          .where((row) => row.source == 'customer_manual_cart')
          .length,
      failedSessions: inRangeSessions
          .where((row) => row.state == 'failed')
          .length,
      unresolvedAttentionCount:
          unknownObjectIds.difference(resolvedUnknownIds).length +
          inRangeSessions.where((row) => row.state == 'failed').length,
    );
  }

  @override
  Stream<AdminDashboardSummary> watchDashboard(DateRange range) => _database
      .customSelect(
        'SELECT 1',
        readsFrom: {
          _database.checkoutSessions,
          _database.scanAttempts,
          _database.inferenceObjects,
          _database.objectResolutions,
          _database.finalOrders,
          _database.simulatedPayments,
        },
      )
      .watch()
      .asyncMap((_) => dashboard(range));

  @override
  Future<List<AttentionItem>> recentAttentionItems({required int limit}) async {
    if (limit <= 0) return const [];
    final sessions = await _database.select(_database.checkoutSessions).get();
    final attempts = await _database.select(_database.scanAttempts).get();
    final objects = await _database.select(_database.inferenceObjects).get();
    final resolutions = await _database
        .select(_database.objectResolutions)
        .get();
    final resolvedObjectIds = resolutions
        .where((row) => row.isCurrent && row.inferenceObjectId != null)
        .map((row) => row.inferenceObjectId!)
        .toSet();
    final attemptById = {
      for (final attempt in attempts) attempt.attemptId: attempt,
    };
    final items = <AttentionItem>[
      for (final session in sessions.where((row) => row.state == 'failed'))
        AttentionItem(
          sessionId: session.sessionId,
          kind: AttentionKind.failedSession,
          occurredAt: _utc(session.terminalAtUs ?? session.startedAtUs),
          label: '계속할 수 없는 오류',
        ),
      for (final object in objects.where(
        (row) =>
            row.skuId == null &&
            !resolvedObjectIds.contains(row.inferenceObjectId),
      ))
        if (attemptById[object.attemptId] case final attempt?)
          AttentionItem(
            sessionId: attempt.sessionId,
            kind: AttentionKind.unresolvedUnknown,
            occurredAt: _utc(attempt.capturedAtUs),
            label: '고객 선택이 필요한 빵',
          ),
    ]..sort((a, b) => b.occurredAt.compareTo(a.occurredAt));
    return items.take(limit).toList(growable: false);
  }

  DateTime _utc(int microseconds) =>
      DateTime.fromMicrosecondsSinceEpoch(microseconds, isUtc: true);
}
