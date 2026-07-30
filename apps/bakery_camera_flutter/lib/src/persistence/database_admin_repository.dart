import '../admin/admin_models.dart';
import '../admin/admin_repository.dart';
import 'app_database.dart';

typedef AuditEvidenceIntegrityChecker =
    Future<AuditEvidenceIntegrity> Function(
      String relativePath,
      String sha256,
      int byteSize,
    );

/// Read projections over immutable checkout evidence. It never writes audit data.
final class DatabaseAdminRepository
    implements AdminRepository, TransactionAuditRepository {
  DatabaseAdminRepository(this._database, {this.verifyEvidence});

  final BakeryDatabase _database;
  final AuditEvidenceIntegrityChecker? verifyEvidence;

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
    final inRangeAttempts = attempts
        .where((row) => range.includes(_utc(row.capturedAtUs)))
        .toList(growable: false);
    final attemptIds = inRangeAttempts.map((row) => row.attemptId).toSet();
    final inRangeObjects = objects
        .where((row) => attemptIds.contains(row.attemptId))
        .toList(growable: false);
    final objectById = {
      for (final object in objects) object.inferenceObjectId: object,
    };

    final committedPayments = payments
        .where((payment) {
          return sessionById[payment.sessionId]?.state == 'completed' &&
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
        .where((row) => row.isCurrent && range.includes(_utc(row.resolvedAtUs)))
        .toList(growable: false);
    final resolvedUnknownIds = currentResolutions
        .where((row) {
          final objectId = row.inferenceObjectId;
          if (objectId == null) return false;
          final object = objectById[objectId];
          return object != null && object.skuId == null;
        })
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
      failedSessions: sessions
          .where(
            (row) =>
                row.state == 'failed' &&
                row.terminalAtUs != null &&
                range.includes(_utc(row.terminalAtUs!)),
          )
          .length,
      unresolvedAttentionCount:
          unknownObjectIds.difference(resolvedUnknownIds).length +
          sessions
              .where(
                (row) =>
                    row.state == 'failed' &&
                    row.terminalAtUs != null &&
                    range.includes(_utc(row.terminalAtUs!)),
              )
              .length,
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

  @override
  Future<TransactionPage> transactions(
    TransactionFilter filter,
    PageCursor? after, {
    int limit = 50,
  }) async {
    if (limit <= 0) {
      throw ArgumentError.value(limit, 'limit', 'must be positive');
    }
    final sessions = await _database.select(_database.checkoutSessions).get();
    final attempts = await _database.select(_database.scanAttempts).get();
    final objects = await _database.select(_database.inferenceObjects).get();
    final resolutions = await _database
        .select(_database.objectResolutions)
        .get();
    final orders = await _database.select(_database.finalOrders).get();
    final payments = await _database.select(_database.simulatedPayments).get();
    final orderLines = await _database.select(_database.finalOrderLines).get();

    final attemptsBySession = _groupBy(attempts, (row) => row.sessionId);
    final attemptIdsBySession = {
      for (final entry in attemptsBySession.entries)
        entry.key: entry.value.map((row) => row.attemptId).toSet(),
    };
    final objectsBySession = {
      for (final entry in attemptIdsBySession.entries)
        entry.key: objects
            .where((row) => entry.value.contains(row.attemptId))
            .toList(growable: false),
    };
    final resolutionsBySession = _groupBy(resolutions, (row) => row.sessionId);
    final orderBySession = {for (final row in orders) row.sessionId: row};
    final paymentBySession = {for (final row in payments) row.sessionId: row};
    final linesByOrder = _groupBy(orderLines, (row) => row.orderId);
    final sessionQuery = filter.sessionQuery?.trim().toLowerCase();
    final productQuery = filter.productQuery?.trim().toLowerCase();
    final modelPolicyQuery = filter.modelPolicyQuery?.trim().toLowerCase();
    final filtered =
        sessions.where((session) {
          final sessionAttempts =
              attemptsBySession[session.sessionId] ?? const [];
          final sessionObjects =
              objectsBySession[session.sessionId] ?? const [];
          final sessionResolutions =
              resolutionsBySession[session.sessionId] ?? const [];
          final order = orderBySession[session.sessionId];
          final payment = paymentBySession[session.sessionId];
          final hasUnknown = sessionObjects.any((row) => row.skuId == null);
          final hasRetake =
              sessionAttempts.length > 1 ||
              sessionAttempts.any((row) => row.retakeReason != null);
          final hasFailure = session.state == 'failed';
          final productMatches =
              [
                ...sessionResolutions.map((row) => row.productName),
                ...((order == null
                        ? const <FinalOrderLineRow>[]
                        : linesByOrder[order.orderId] ??
                              const <FinalOrderLineRow>[])
                    .map((row) => row.productName)),
              ].any(
                (name) =>
                    productQuery != null &&
                    name.toLowerCase().contains(productQuery),
              );
          final modelPolicyMatches =
              [
                session.detectorId,
                session.repvitArtifactId,
                session.dinov3ArtifactId,
                session.calibrationId,
                session.fusionPolicyId,
                session.detectorSha256,
                session.repvitSha256,
                session.dinov3Sha256,
                session.calibrationSha256,
                session.fusionPolicySha256,
              ].any(
                (value) =>
                    modelPolicyQuery != null &&
                    value.toLowerCase().contains(modelPolicyQuery),
              );
          return (filter.dateRange == null ||
                  filter.dateRange!.includes(_utc(session.startedAtUs))) &&
              (sessionQuery == null ||
                  sessionQuery.isEmpty ||
                  session.sessionId.toLowerCase().contains(sessionQuery)) &&
              (productQuery == null ||
                  productQuery.isEmpty ||
                  productMatches) &&
              (modelPolicyQuery == null ||
                  modelPolicyQuery.isEmpty ||
                  modelPolicyMatches) &&
              (filter.paymentStatus == TransactionPaymentStatus.any ||
                  (filter.paymentStatus == TransactionPaymentStatus.completed &&
                      payment != null &&
                      session.state == 'completed') ||
                  (filter.paymentStatus == TransactionPaymentStatus.unpaid &&
                      payment == null)) &&
              (filter.resolutionSource == null ||
                  sessionResolutions.any(
                    (row) => row.source == filter.resolutionSource,
                  )) &&
              (filter.requiresUnknown == null ||
                  filter.requiresUnknown == hasUnknown) &&
              (filter.requiresRetake == null ||
                  filter.requiresRetake == hasRetake) &&
              (filter.requiresFailure == null ||
                  filter.requiresFailure == hasFailure);
        }).toList()..sort((left, right) {
          final time = right.startedAtUs.compareTo(left.startedAtUs);
          return time != 0 ? time : right.sessionId.compareTo(left.sessionId);
        });
    final pageable = after == null
        ? filtered
        : filtered.where((row) => _isAfterCursor(row, after)).toList();
    final pageRows = pageable.take(limit).toList(growable: false);
    final items = pageRows
        .map((session) {
          final sessionAttempts =
              attemptsBySession[session.sessionId] ?? const <ScanAttemptRow>[];
          final sessionObjects =
              objectsBySession[session.sessionId] ??
              const <InferenceObjectRow>[];
          final sources =
              (resolutionsBySession[session.sessionId] ??
                      const <ObjectResolutionRow>[])
                  .map((row) => row.source)
                  .toSet()
                  .toList()
                ..sort();
          final order = orderBySession[session.sessionId];
          return TransactionListItem(
            sessionId: session.sessionId,
            startedAt: _utc(session.startedAtUs),
            terminalState: session.state,
            breadCount: order?.totalQuantity ?? 0,
            finalAmountKrw: paymentBySession[session.sessionId]?.amountKrw,
            scanAttemptCount: sessionAttempts.length,
            resolutionSources: List.unmodifiable(sources),
            hasUnknown: sessionObjects.any((row) => row.skuId == null),
            hasRetake:
                sessionAttempts.length > 1 ||
                sessionAttempts.any((row) => row.retakeReason != null),
            hasFailure: session.state == 'failed',
          );
        })
        .toList(growable: false);
    final hasMore = items.length < pageable.length;
    final last = items.isEmpty ? null : items.last;
    return TransactionPage(
      items: items,
      nextCursor: hasMore && last != null
          ? PageCursor(startedAt: last.startedAt, sessionId: last.sessionId)
          : null,
    );
  }

  @override
  Future<AdminTransactionDetail> transactionDetail(String sessionId) async {
    final session = await (_database.select(
      _database.checkoutSessions,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    if (session == null) {
      throw StateError('unknown checkout session: $sessionId');
    }
    final attempts =
        await (_database.select(
            _database.scanAttempts,
          )..where((row) => row.sessionId.equals(sessionId))).get()
          ..sort((a, b) => a.attemptNumber.compareTo(b.attemptNumber));
    final attemptIds = attempts.map((row) => row.attemptId).toSet();
    final allObjects = await _database.select(_database.inferenceObjects).get();
    final objects = allObjects
        .where((row) => attemptIds.contains(row.attemptId))
        .toList(growable: false);
    final objectIds = objects.map((row) => row.inferenceObjectId).toSet();
    final allCandidates = await _database
        .select(_database.inferenceCandidates)
        .get();
    final retentionEvents = await _database
        .select(_database.retentionEvents)
        .get();
    final retentionPathsByAttempt = <String, Set<String>>{};
    for (final event in retentionEvents) {
      retentionPathsByAttempt
          .putIfAbsent(event.attemptId, () => <String>{})
          .add(event.relativePath);
    }
    final candidates = allCandidates
        .where((row) => objectIds.contains(row.inferenceObjectId))
        .toList(growable: false);
    final resolutions =
        await (_database.select(
            _database.objectResolutions,
          )..where((row) => row.sessionId.equals(sessionId))).get()
          ..sort((a, b) => a.resolvedAtUs.compareTo(b.resolvedAtUs));
    final order = await (_database.select(
      _database.finalOrders,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    final payment = await (_database.select(
      _database.simulatedPayments,
    )..where((row) => row.sessionId.equals(sessionId))).getSingleOrNull();
    final lines = order == null
        ? const <FinalOrderLineRow>[]
        : await (_database.select(
            _database.finalOrderLines,
          )..where((row) => row.orderId.equals(order.orderId))).get();
    final candidatesByObject = _groupBy(
      candidates,
      (row) => row.inferenceObjectId,
    );
    final objectsByAttempt = _groupBy(objects, (row) => row.attemptId);
    final attemptModels = <AdminScanAttempt>[];
    for (final attempt in attempts) {
      final image = await _evidence(
        attempt.imageRelativePath,
        attempt.imageSha256,
        attempt.imageByteSize,
        retentionExpired:
            retentionPathsByAttempt[attempt.attemptId]?.contains(
              attempt.imageRelativePath,
            ) ??
            false,
      );
      final receipt = attempt.receiptRelativePath == null
          ? null
          : await _evidence(
              attempt.receiptRelativePath!,
              attempt.receiptSha256!,
              attempt.receiptByteSize!,
              retentionExpired:
                  retentionPathsByAttempt[attempt.attemptId]?.contains(
                    attempt.receiptRelativePath!,
                  ) ??
                  false,
            );
      final attemptObjects =
          (objectsByAttempt[attempt.attemptId] ?? const <InferenceObjectRow>[])
              .map((object) {
                final objectCandidates =
                    (candidatesByObject[object.inferenceObjectId] ??
                            const <InferenceCandidateRow>[])
                        .map(
                          (candidate) => AdminInferenceCandidate(
                            rank: candidate.rank,
                            skuId: candidate.skuId,
                            skuName: candidate.skuName,
                            score: candidate.score,
                          ),
                        )
                        .toList()
                      ..sort((a, b) => a.rank.compareTo(b.rank));
                return AdminInferenceObject(
                  objectId: object.objectId,
                  skuId: object.skuId,
                  skuName: object.skuName,
                  boxJson: object.bboxJson,
                  confidence: object.confidence,
                  decisionPath: object.decisionPath,
                  detectorSource: object.detectorSource,
                  detectorScore: object.detectorScore,
                  candidates: objectCandidates,
                  unknownReason: object.unknownReason,
                );
              })
              .toList(growable: false);
      attemptModels.add(
        AdminScanAttempt(
          attemptNumber: attempt.attemptNumber,
          capturedAt: _utc(attempt.capturedAtUs),
          status: attempt.status,
          image: image,
          receipt: receipt,
          presentationState: attempt.presentationState,
          retakeReason: attempt.retakeReason,
          timingsMs: Map.unmodifiable({
            'decode/preprocess': attempt.decodePreprocessMs,
            'detector': attempt.detectorMs,
            'repvit': attempt.repvitMs,
            'dinov3': attempt.dinov3Ms,
            'postprocess': attempt.postprocessMs,
            'total': attempt.totalMs,
          }),
          objects: attemptObjects,
        ),
      );
    }
    final resolutionModels = resolutions
        .map(
          (row) => AdminObjectResolution(
            resolutionId: row.resolutionId,
            inferenceObjectId: row.inferenceObjectId,
            productId: row.productId,
            productName: row.productName,
            recognitionSkuId: row.recognitionSkuId,
            unitPriceKrw: row.unitPriceKrw,
            source: row.source,
            resolvedAt: _utc(row.resolvedAtUs),
            candidateRank: row.candidateRank,
            canonicalBoxJson: row.canonicalBboxJson,
            isCurrent: row.isCurrent,
          ),
        )
        .toList(growable: false);
    final orderModel = order == null
        ? null
        : AdminFinalOrder(
            orderId: order.orderId,
            createdAt: _utc(order.createdAtUs),
            totalQuantity: order.totalQuantity,
            totalAmountKrw: order.totalAmountKrw,
            receipt: await _evidence(
              order.receiptRelativePath,
              order.receiptSha256,
              order.receiptByteSize,
            ),
            lines: lines
                .map(
                  (row) => AdminOrderLine(
                    productName: row.productName,
                    productId: row.productId,
                    recognitionSkuId: row.recognitionSkuId,
                    unitPriceKrw: row.unitPriceKrw,
                    quantity: row.quantity,
                    lineAmountKrw: row.lineAmountKrw,
                    resolutionSource: row.resolutionSource,
                  ),
                )
                .toList(growable: false),
          );
    final warning = [
      ...attemptModels.map((row) => row.image),
      ...attemptModels
          .map((row) => row.receipt)
          .whereType<AdminEvidenceReference>(),
      if (orderModel != null) orderModel.receipt,
    ].any((evidence) => evidence.integrity != AuditEvidenceIntegrity.retained);
    return AdminTransactionDetail(
      sessionId: session.sessionId,
      startedAt: _utc(session.startedAtUs),
      terminalAt: session.terminalAtUs == null
          ? null
          : _utc(session.terminalAtUs!),
      terminalState: session.state,
      terminalReason: session.terminalReason,
      catalogRevisionId: session.catalogRevisionId,
      settingsRevisionId: session.settingsRevisionId,
      artifacts: AdminArtifactSnapshot(
        detectorId: session.detectorId,
        detectorSha256: session.detectorSha256,
        repvitArtifactId: session.repvitArtifactId,
        repvitSha256: session.repvitSha256,
        repvitManifestSha256: session.repvitManifestSha256,
        repvitPrototypeSha256: session.repvitPrototypeSha256,
        dinov3ArtifactId: session.dinov3ArtifactId,
        dinov3Sha256: session.dinov3Sha256,
        dinov3SupportSha256: session.dinov3SupportSha256,
        calibrationId: session.calibrationId,
        calibrationSha256: session.calibrationSha256,
        preprocessSha256: session.preprocessSha256,
        fusionPolicyId: session.fusionPolicyId,
        fusionPolicySha256: session.fusionPolicySha256,
      ),
      attempts: attemptModels,
      resolutions: resolutionModels,
      order: orderModel,
      payment: payment == null
          ? null
          : AdminPaymentSnapshot(
              paymentId: payment.paymentId,
              amountKrw: payment.amountKrw,
              provider: payment.provider,
              status: payment.status,
              finalOrderSha256: payment.finalOrderSha256,
              paidAt: _utc(payment.paidAtUs),
            ),
      hasIntegrityWarning: warning,
    );
  }

  Future<AdminEvidenceReference> _evidence(
    String path,
    String sha256,
    int size, {
    bool retentionExpired = false,
  }) async {
    AuditEvidenceIntegrity integrity;
    if (retentionExpired) {
      integrity = AuditEvidenceIntegrity.retentionExpired;
    } else if (verifyEvidence == null) {
      integrity = AuditEvidenceIntegrity.unverified;
    } else {
      try {
        final checker = verifyEvidence;
        integrity = await checker!(path, sha256, size);
      } on Object {
        integrity = AuditEvidenceIntegrity.unavailable;
      }
    }
    return AdminEvidenceReference(
      relativePath: path,
      sha256: sha256,
      byteSize: size,
      integrity: integrity,
    );
  }

  bool _isAfterCursor(CheckoutSessionRow row, PageCursor cursor) {
    final timestamp = row.startedAtUs.compareTo(
      cursor.startedAt.microsecondsSinceEpoch,
    );
    return timestamp < 0 ||
        (timestamp == 0 && row.sessionId.compareTo(cursor.sessionId) < 0);
  }

  Map<K, List<T>> _groupBy<T, K>(Iterable<T> rows, K Function(T row) key) {
    final grouped = <K, List<T>>{};
    for (final row in rows) {
      grouped.putIfAbsent(key(row), () => []).add(row);
    }
    return grouped;
  }
}
