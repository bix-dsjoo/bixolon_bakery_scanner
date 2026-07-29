final class InferenceLaunchConfig {
  InferenceLaunchConfig._({
    required this.pythonExecutable,
    required this.repoRoot,
  }) : workerScript = _join(
         repoRoot,
         r'scripts\run_camera_inference_worker.py',
       ),
       warmupImage = _join(
         repoRoot,
         r'samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg',
       );

  factory InferenceLaunchConfig.fromEnvironment(
    Map<String, String> environment,
  ) {
    final pythonExecutable = _requiredEnvironmentValue(
      environment,
      'BAKERY_INFERENCE_PYTHON',
    );
    final repoRoot = _requiredEnvironmentValue(environment, 'BAKERY_REPO_ROOT');
    return InferenceLaunchConfig._(
      pythonExecutable: pythonExecutable,
      repoRoot: repoRoot,
    );
  }

  final String pythonExecutable;
  final String repoRoot;
  final String workerScript;
  final String warmupImage;

  List<String> get arguments => List.unmodifiable([
    workerScript,
    '--repo-root',
    repoRoot,
    '--device',
    'auto',
    '--warmup-image',
    warmupImage,
  ]);

  static String _requiredEnvironmentValue(
    Map<String, String> environment,
    String name,
  ) {
    final value = environment[name];
    if (value == null || value.trim().isEmpty) {
      throw StateError('$name 환경 변수를 설정한 뒤 앱을 다시 시작하세요.');
    }
    return value;
  }

  static String _join(String root, String child) {
    final normalizedRoot = root.endsWith(r'\')
        ? root.substring(0, root.length - 1)
        : root;
    return '$normalizedRoot\\$child';
  }
}
