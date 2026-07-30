import 'dart:collection';

import '../inference/inference_models.dart';

final class CameraPresentationState {
  CameraPresentationState._({
    required this.state,
    required this.finalCountUsable,
    required this.retakeScope,
    required List<String> retakeObjectIds,
    required this.instruction,
    required List<String> candidateObjectIds,
    required this.policyId,
    required this.policySha256,
  }) : retakeObjectIds = UnmodifiableListView(retakeObjectIds),
       candidateObjectIds = UnmodifiableListView(candidateObjectIds);

  factory CameraPresentationState.fromInference(
    InferencePresentation presentation,
  ) {
    return CameraPresentationState._(
      state: presentation.state,
      finalCountUsable: presentation.finalCountUsable,
      retakeScope: presentation.retakeScope,
      retakeObjectIds: presentation.retakeObjectIds,
      instruction: presentation.instruction,
      candidateObjectIds: presentation.candidateObjectIds,
      policyId: presentation.policyId,
      policySha256: presentation.policySha256,
    );
  }

  final InferencePresentationState state;
  final bool finalCountUsable;
  final RetakeScope? retakeScope;
  final List<String> retakeObjectIds;
  final RetakeInstruction? instruction;
  final List<String> candidateObjectIds;
  final String policyId;
  final String policySha256;

  String? get primaryInstruction {
    final value = instruction;
    return value == null ? null : instructionFor(value);
  }
}

String instructionFor(RetakeInstruction instruction) => switch (instruction) {
  RetakeInstruction.noBreadDetected => '빵을 찾지 못했어요. 빵이 모두 보이도록 다시 촬영해 주세요',
  RetakeInstruction.separateBreads => '빵 사이 간격을 두고 다시 촬영해 주세요',
  RetakeInstruction.candidateEvidenceWeak => '빵이 잘 보이도록 다시 촬영해 주세요',
};
