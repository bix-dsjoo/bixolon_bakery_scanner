import 'package:drift/native.dart';

import 'app_database.dart';

BakeryDatabase openProductionBakeryDatabase() => BakeryDatabase.production();

BakeryDatabase openInMemoryBakeryDatabase() =>
    BakeryDatabase(NativeDatabase.memory());
