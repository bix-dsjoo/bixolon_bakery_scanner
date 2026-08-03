import 'package:flutter/material.dart';

class AuditFactTable extends StatelessWidget {
  const AuditFactTable({required this.facts, super.key});
  final Map<String, String> facts;
  @override
  Widget build(BuildContext context) => Table(
    columnWidths: const {0: IntrinsicColumnWidth()},
    children: [
      for (final entry in facts.entries)
        TableRow(
          children: [
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                entry.key,
                style: Theme.of(context).textTheme.labelMedium,
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(8),
              child: SelectableText(entry.value),
            ),
          ],
        ),
    ],
  );
}
