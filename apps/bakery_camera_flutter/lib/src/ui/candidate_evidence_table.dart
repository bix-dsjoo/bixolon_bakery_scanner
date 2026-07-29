import 'package:flutter/material.dart';

import '../inference/inference_models.dart';
import 'app_theme.dart';
import 'bixolon_brand.dart';
import 'evaluation_view_data.dart';

final class CandidateEvidenceTable extends StatelessWidget {
  const CandidateEvidenceTable({super.key, required this.object});

  final InferenceObject object;

  @override
  Widget build(BuildContext context) {
    assert(object.isUnknown);
    return Padding(
      padding: const EdgeInsets.fromLTRB(34, 4, 8, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'AI가 이 빵의 품목을 알 수 없다고 판단했어요. '
            '가능성이 높은 품목 3개를 참고용으로 보여드려요.',
            style: Theme.of(
              context,
            ).textTheme.bodySmall?.copyWith(color: bixolonMutedInk, height: 1.45),
          ),
          const SizedBox(height: 10),
          const _CandidateHeader(),
          for (final candidate in object.candidates)
            _CandidateRow(candidate: candidate),
        ],
      ),
    );
  }
}

final class _CandidateHeader extends StatelessWidget {
  const _CandidateHeader();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.only(bottom: 4),
    child: Row(
      children: [
        SizedBox(width: 34, child: Text('순위')),
        Expanded(child: Text('예상 품목')),
        SizedBox(width: 64, child: Text('판정 점수', textAlign: TextAlign.right)),
      ],
    ),
  );
}

final class _CandidateRow extends StatelessWidget {
  const _CandidateRow({required this.candidate});

  final InferenceCandidate candidate;

  @override
  Widget build(BuildContext context) => Semantics(
    label:
        '${candidate.rank}위 ${candidate.skuName}, '
        '판정 점수 ${evaluationPercent(candidate.score)}',
    child: Container(
      key: const Key('candidate-row'),
      constraints: const BoxConstraints(minHeight: 34),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: bixolonDivider)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 34,
            child: Text(
              '${candidate.rank}',
              style: const TextStyle(
                color: unknownAmber,
                fontWeight: FontWeight.w700,
                fontFeatures: tabularFigures,
              ),
            ),
          ),
          Expanded(
            child: Text(
              candidate.skuName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          SizedBox(
            width: 64,
            child: Text(
              evaluationPercent(candidate.score),
              textAlign: TextAlign.right,
              style: const TextStyle(fontFeatures: tabularFigures),
            ),
          ),
        ],
      ),
    ),
  );
}
