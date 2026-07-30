import 'package:bakery_camera_prototype/src/checkout/checkout_recovery.dart';
import 'package:bakery_camera_prototype/src/checkout/checkout_ports.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'startup recovery interrupts stale work and flags retained evidence without resuming checkout',
    () async {
      final port = _RecoveryPort();
      final recovery = CheckoutRecovery(
        port: port,
        clock: () => DateTime.utc(2026, 7, 30, 12),
      );

      final result = await recovery.recover();

      expect(port.detectedAt, DateTime.utc(2026, 7, 30, 12));
      expect(result.interruptedSessionIds, ['scan-session', 'paying-session']);
      expect(result.repairedPaymentSessionIds, ['stale-payment-session']);
      expect(result.evidenceIssuePaths, [
        'sessions/2026/07/30/scan-session/attempt-001.jpg',
      ]);
      expect(result.resumesAnyPriorSession, isFalse);
    },
  );
}

final class _RecoveryPort implements CheckoutRecoveryPort {
  DateTime? detectedAt;

  @override
  Future<CheckoutRecoveryReport> recoverInterruptedCheckout(
    DateTime value,
  ) async {
    detectedAt = value;
    return const CheckoutRecoveryReport(
      interruptedSessionIds: ['scan-session', 'paying-session'],
      repairedPaymentSessionIds: ['stale-payment-session'],
      evidenceIssuePaths: ['sessions/2026/07/30/scan-session/attempt-001.jpg'],
    );
  }
}
