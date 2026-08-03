// ignore_for_file: prefer_initializing_formals

import 'checkout_ports.dart';

typedef RecoveryClock = DateTime Function();

final class CheckoutRecoveryResult {
  const CheckoutRecoveryResult({
    required this.interruptedSessionIds,
    required this.repairedPaymentSessionIds,
    required this.evidenceIssuePaths,
  });

  final List<String> interruptedSessionIds;
  final List<String> repairedPaymentSessionIds;
  final List<String> evidenceIssuePaths;
  bool get resumesAnyPriorSession => false;
}

/// Small bootstrap boundary: it can only terminalize old sessions or add audit
/// flags. It intentionally has no API for reopening a checkout.
final class CheckoutRecovery {
  const CheckoutRecovery({
    required CheckoutRecoveryPort port,
    required RecoveryClock clock,
  }) : _port = port,
       _clock = clock;

  final CheckoutRecoveryPort _port;
  final RecoveryClock _clock;

  Future<CheckoutRecoveryResult> recover() async {
    final report = await _port.recoverInterruptedCheckout(_clock().toUtc());
    return CheckoutRecoveryResult(
      interruptedSessionIds: List.unmodifiable(report.interruptedSessionIds),
      repairedPaymentSessionIds: List.unmodifiable(
        report.repairedPaymentSessionIds,
      ),
      evidenceIssuePaths: List.unmodifiable(report.evidenceIssuePaths),
    );
  }
}
