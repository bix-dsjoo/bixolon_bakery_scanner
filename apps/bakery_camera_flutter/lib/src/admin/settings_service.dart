import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:uuid/uuid.dart';

import '../persistence/app_database.dart';
import 'settings_models.dart';

/// Writes only the explicit 1.1.0 kiosk settings as immutable revisions.
///
/// Checkout sessions retain the revision ID captured at their own start, so a
/// save can only affect the next customer session.
final class SettingsService {
  factory SettingsService({
    required BakeryDatabase database,
    String Function()? createId,
    DateTime Function()? now,
  }) => SettingsService._(
    database,
    createId ?? const Uuid().v4,
    now ?? DateTime.now,
  );

  SettingsService._(this._database, this._createId, this._now);

  static const minRetryLimit = 1;
  static const maxRetryLimit = 5;
  static const minCompleteDurationSeconds = 2;
  static const maxCompleteDurationSeconds = 10;
  static const minEvidenceRetentionDays = 7;
  static const maxEvidenceRetentionDays = 3650;
  static const koreanLocale = 'ko-KR';

  final BakeryDatabase _database;
  final String Function() _createId;
  final DateTime Function() _now;

  Future<KioskSettings> current() async {
    final app = await (_database.select(
      _database.appSettings,
    )..where((row) => row.settingsId.equals('operational'))).getSingle();
    return revision(app.activeSettingsRevisionId);
  }

  Future<KioskSettings> revision(String revisionId) async {
    final row = await (_database.select(
      _database.settingsRevisions,
    )..where((item) => item.revisionId.equals(revisionId))).getSingle();
    return _settings(row);
  }

  Future<KioskSettings> save(KioskSettingsDraft draft) async {
    _validate(draft);
    return _database.transaction(() async {
      final before = await current();
      final revisionId = _createId().trim();
      if (revisionId.isEmpty || revisionId == before.revisionId) {
        throw StateError('settings revision ID must be new and non-empty');
      }
      final updatedAt = _now().toUtc();
      final normalized = KioskSettingsDraft(
        kioskDisplayName: draft.kioskDisplayName.trim(),
        retryLimit: draft.retryLimit,
        paymentCompleteDurationSeconds: draft.paymentCompleteDurationSeconds,
        customerAutoReset: draft.customerAutoReset,
        evidenceRetentionDays: draft.evidenceRetentionDays,
        locale: draft.locale,
        adminAuthorLabel: draft.adminAuthorLabel.trim(),
      );
      await _database
          .into(_database.settingsRevisions)
          .insert(
            SettingsRevisionsCompanion.insert(
              revisionId: revisionId,
              createdAtUs: updatedAt.microsecondsSinceEpoch,
              retryLimit: normalized.retryLimit,
              paymentCompleteDurationSeconds:
                  normalized.paymentCompleteDurationSeconds,
              customerAutoReset: normalized.customerAutoReset,
              evidenceRetentionDays: normalized.evidenceRetentionDays,
              locale: normalized.locale,
              kioskDisplayName: normalized.kioskDisplayName,
              adminAuthorLabel: normalized.adminAuthorLabel,
            ),
          );
      await _database.batch((batch) {
        batch.insertAll(
          _database.settingsRevisionEntries,
          _entries(revisionId, normalized, updatedAt),
        );
      });
      await (_database.update(
        _database.appSettings,
      )..where((row) => row.settingsId.equals('operational'))).write(
        AppSettingsCompanion(activeSettingsRevisionId: Value(revisionId)),
      );
      await _database
          .into(_database.auditEvents)
          .insert(
            AuditEventsCompanion.insert(
              eventId: '$revisionId/settings-revision-activated',
              eventType: 'settings_revision_activated',
              occurredAtUs: updatedAt.microsecondsSinceEpoch,
              detail: Value(
                jsonEncode({
                  'after_revision_id': revisionId,
                  'author_label': normalized.adminAuthorLabel,
                  'before_revision_id': before.revisionId,
                  'effective_from': 'next_customer_session',
                }),
              ),
            ),
          );
      return KioskSettings(
        revisionId: revisionId,
        updatedAt: updatedAt,
        kioskDisplayName: normalized.kioskDisplayName,
        retryLimit: normalized.retryLimit,
        paymentCompleteDurationSeconds:
            normalized.paymentCompleteDurationSeconds,
        customerAutoReset: normalized.customerAutoReset,
        evidenceRetentionDays: normalized.evidenceRetentionDays,
        locale: normalized.locale,
        adminAuthorLabel: normalized.adminAuthorLabel,
      );
    });
  }

  void _validate(KioskSettingsDraft draft) {
    if (draft.kioskDisplayName.trim().isEmpty ||
        draft.kioskDisplayName.trim().length > 80) {
      throw ArgumentError.value(
        draft.kioskDisplayName,
        'kioskDisplayName',
        'must be 1 to 80 characters',
      );
    }
    if (draft.adminAuthorLabel.trim().isEmpty ||
        draft.adminAuthorLabel.trim().length > 80) {
      throw ArgumentError.value(
        draft.adminAuthorLabel,
        'adminAuthorLabel',
        'must be 1 to 80 characters',
      );
    }
    _range(draft.retryLimit, minRetryLimit, maxRetryLimit, 'retryLimit');
    _range(
      draft.paymentCompleteDurationSeconds,
      minCompleteDurationSeconds,
      maxCompleteDurationSeconds,
      'paymentCompleteDurationSeconds',
    );
    _range(
      draft.evidenceRetentionDays,
      minEvidenceRetentionDays,
      maxEvidenceRetentionDays,
      'evidenceRetentionDays',
    );
    if (draft.locale != koreanLocale) {
      throw ArgumentError.value(
        draft.locale,
        'locale',
        '1.1.0 is fixed to Korean',
      );
    }
  }

  static void _range(int value, int minimum, int maximum, String name) {
    if (value < minimum || value > maximum) {
      throw ArgumentError.value(value, name, 'must be $minimum to $maximum');
    }
  }

  List<SettingsRevisionEntriesCompanion> _entries(
    String revisionId,
    KioskSettingsDraft value,
    DateTime updatedAt,
  ) {
    final timestamp = updatedAt.microsecondsSinceEpoch;
    SettingsRevisionEntriesCompanion entry(
      KioskSettingKey key,
      Object settingValue,
    ) => SettingsRevisionEntriesCompanion.insert(
      revisionId: revisionId,
      settingKey: key.storageKey,
      valueType: key.valueType,
      valueJson: jsonEncode(settingValue),
      updatedAtUs: timestamp,
      authorLabel: value.adminAuthorLabel,
    );
    return [
      entry(KioskSettingKey.kioskDisplayName, value.kioskDisplayName),
      entry(KioskSettingKey.retryLimit, value.retryLimit),
      entry(
        KioskSettingKey.paymentCompleteDurationSeconds,
        value.paymentCompleteDurationSeconds,
      ),
      entry(KioskSettingKey.customerAutoReset, value.customerAutoReset),
      entry(KioskSettingKey.evidenceRetentionDays, value.evidenceRetentionDays),
      entry(KioskSettingKey.locale, value.locale),
      entry(KioskSettingKey.adminAuthorLabel, value.adminAuthorLabel),
    ];
  }

  static KioskSettings _settings(SettingsRevisionRow row) => KioskSettings(
    revisionId: row.revisionId,
    updatedAt: DateTime.fromMicrosecondsSinceEpoch(
      row.createdAtUs,
      isUtc: true,
    ),
    kioskDisplayName: row.kioskDisplayName,
    retryLimit: row.retryLimit,
    paymentCompleteDurationSeconds: row.paymentCompleteDurationSeconds,
    customerAutoReset: row.customerAutoReset,
    evidenceRetentionDays: row.evidenceRetentionDays,
    locale: row.locale,
    adminAuthorLabel: row.adminAuthorLabel,
  );
}
