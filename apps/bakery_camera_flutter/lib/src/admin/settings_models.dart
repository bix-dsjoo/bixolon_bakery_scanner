/// The deliberately small, typed operational setting surface for 1.1.0.
///
/// Model, calibration, detector, and fusion policy values are intentionally
/// absent: those are immutable pipeline evidence rather than kiosk settings.
enum KioskSettingKey {
  kioskDisplayName('kiosk_display_name', 'string'),
  retryLimit('retry_limit', 'integer'),
  paymentCompleteDurationSeconds(
    'payment_complete_duration_seconds',
    'integer',
  ),
  customerAutoReset('customer_auto_reset', 'boolean'),
  evidenceRetentionDays('evidence_retention_days', 'integer'),
  locale('locale', 'string'),
  adminAuthorLabel('admin_author_label', 'string');

  const KioskSettingKey(this.storageKey, this.valueType);

  final String storageKey;
  final String valueType;

  static KioskSettingKey fromStorageKey(String value) {
    for (final key in values) {
      if (key.storageKey == value) return key;
    }
    throw ArgumentError.value(
      value,
      'storageKey',
      'is not a supported setting',
    );
  }
}

final class KioskSettingsDraft {
  const KioskSettingsDraft({
    required this.kioskDisplayName,
    required this.retryLimit,
    required this.paymentCompleteDurationSeconds,
    required this.customerAutoReset,
    required this.evidenceRetentionDays,
    required this.locale,
    required this.adminAuthorLabel,
  });

  final String kioskDisplayName;
  final int retryLimit;
  final int paymentCompleteDurationSeconds;
  final bool customerAutoReset;
  final int evidenceRetentionDays;
  final String locale;
  final String adminAuthorLabel;
}

final class KioskSettings {
  const KioskSettings({
    required this.revisionId,
    required this.updatedAt,
    required this.kioskDisplayName,
    required this.retryLimit,
    required this.paymentCompleteDurationSeconds,
    required this.customerAutoReset,
    required this.evidenceRetentionDays,
    required this.locale,
    required this.adminAuthorLabel,
  });

  final String revisionId;
  final DateTime updatedAt;
  final String kioskDisplayName;
  final int retryLimit;
  final int paymentCompleteDurationSeconds;
  final bool customerAutoReset;
  final int evidenceRetentionDays;
  final String locale;
  final String adminAuthorLabel;

  KioskSettingsDraft toDraft({
    String? kioskDisplayName,
    int? retryLimit,
    int? paymentCompleteDurationSeconds,
    bool? customerAutoReset,
    int? evidenceRetentionDays,
    String? locale,
    String? adminAuthorLabel,
  }) => KioskSettingsDraft(
    kioskDisplayName: kioskDisplayName ?? this.kioskDisplayName,
    retryLimit: retryLimit ?? this.retryLimit,
    paymentCompleteDurationSeconds:
        paymentCompleteDurationSeconds ?? this.paymentCompleteDurationSeconds,
    customerAutoReset: customerAutoReset ?? this.customerAutoReset,
    evidenceRetentionDays: evidenceRetentionDays ?? this.evidenceRetentionDays,
    locale: locale ?? this.locale,
    adminAuthorLabel: adminAuthorLabel ?? this.adminAuthorLabel,
  );
}
