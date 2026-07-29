import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'candidate_evidence_table.dart';
import 'evaluation_view_data.dart';

final class EvaluationObjectList extends StatelessWidget {
  const EvaluationObjectList({
    super.key,
    required this.rows,
    required this.selectedObjectId,
    required this.onSelectObject,
  });

  final List<EvaluationObjectRow> rows;
  final String? selectedObjectId;
  final ValueChanged<String> onSelectObject;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      for (final row in rows)
        _EvaluationObjectRow(
          row: row,
          selected: row.object.objectId == selectedObjectId,
          onTap: () => onSelectObject(row.object.objectId),
        ),
    ],
  );
}

final class _EvaluationObjectRow extends StatefulWidget {
  const _EvaluationObjectRow({
    required this.row,
    required this.selected,
    required this.onTap,
  });

  final EvaluationObjectRow row;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_EvaluationObjectRow> createState() => _EvaluationObjectRowState();
}

final class _EvaluationObjectRowState extends State<_EvaluationObjectRow> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final row = widget.row;
    final object = row.object;
    final semanticColor = object.isUnknown ? unknownAmber : confirmedTeal;
    final border = _focused
        ? Border.all(color: actionBlue, width: 2)
        : Border(
            left: BorderSide(
              color: widget.selected ? bixolonOrange : semanticColor,
              width: widget.selected ? 3 : 2,
            ),
            bottom: const BorderSide(color: bixolonDivider),
          );
    return Column(
      key: const Key('evaluation-object-row'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          selected: widget.selected,
          button: true,
          label:
              '${row.displayNumber}번 '
              '${object.isUnknown ? '알 수 없음' : object.skuName}, '
              '${row.decisionLabel}, 판정 점수 '
              '${evaluationPercent(row.decisionScore)}',
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              key: Key('evaluation-object-row-${object.objectId}'),
              onTap: widget.onTap,
              onFocusChange: (focused) => setState(() => _focused = focused),
              focusColor: Colors.transparent,
              child: Container(
                key: Key('object-row-surface-${object.objectId}'),
                constraints: const BoxConstraints(minHeight: 52),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                decoration: BoxDecoration(border: border),
                child: Row(
                  children: [
                    SizedBox(
                      width: 34,
                      child: Text(
                        row.displayNumber.toString().padLeft(2, '0'),
                        style: const TextStyle(
                          color: bixolonMutedInk,
                          fontWeight: FontWeight.w700,
                          fontFeatures: tabularFigures,
                        ),
                      ),
                    ),
                    Container(
                      key: Key('object-semantic-dot-${object.objectId}'),
                      width: 6,
                      height: 6,
                      margin: const EdgeInsets.only(right: 8),
                      decoration: BoxDecoration(
                        color: semanticColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            object.isUnknown ? '알 수 없음' : object.skuName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            row.decisionLabel,
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(color: bixolonMutedInk),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      evaluationPercent(row.decisionScore),
                      textAlign: TextAlign.right,
                      style: const TextStyle(fontFeatures: tabularFigures),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        if (widget.selected && object.isUnknown)
          CandidateEvidenceTable(object: object),
      ],
    );
  }
}
