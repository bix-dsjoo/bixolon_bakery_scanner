import 'package:bakery_camera_prototype/src/admin/admin_models.dart';
import 'package:bakery_camera_prototype/src/ui/admin/dashboard_screen.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'refreshes dashboard availability from live diagnostics and watches changes',
    () async {
      final liveChanges = ValueNotifier(0);
      var reported = DashboardAvailability.ready;
      final readiness = DashboardReadinessController.watch(
        load: () async => reported,
        liveChanges: liveChanges,
      );
      addTearDown(liveChanges.dispose);
      addTearDown(readiness.dispose);

      await readiness.refresh();
      expect(readiness.value, DashboardAvailability.ready);

      reported = DashboardAvailability.unavailable;
      liveChanges.value++;
      await Future<void>.delayed(Duration.zero);

      expect(readiness.value, DashboardAvailability.unavailable);
    },
  );
}
