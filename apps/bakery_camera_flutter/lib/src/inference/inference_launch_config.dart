import 'package:path/path.dart' as path;

final _windowsPath = path.Context(style: path.Style.windows);

final class InferenceLaunchConfig {
  InferenceLaunchConfig._({
    required this.pythonExecutable,
    required this.repoRoot,
    required this.runtimeProfile,
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
  ) => InferenceLaunchConfig.resolve(
    environment: environment,
    executablePath: r'C:\bakery_camera_prototype.exe',
  );

  factory InferenceLaunchConfig.resolve({
    required Map<String, String> environment,
    required String executablePath,
  }) {
    final python = environment['BAKERY_INFERENCE_PYTHON']?.trim();
    final root = environment['BAKERY_REPO_ROOT']?.trim();
    final requestedProfile =
        environment['BAKERY_INFERENCE_RUNTIME_PROFILE']?.trim();
    final runtimeProfile = requestedProfile == null || requestedProfile.isEmpty
        ? candidateRuntimeProfile
        : requestedProfile;
    if (runtimeProfile != candidateRuntimeProfile &&
        runtimeProfile != legacyRuntimeProfile) {
      throw StateError('지원하지 않는 추론 런타임 프로필입니다.');
    }
    final hasPython = python != null && python.isNotEmpty;
    final hasRoot = root != null && root.isNotEmpty;

    if (hasPython != hasRoot) {
      throw StateError('개발 실행 경로 두 개를 모두 설정한 뒤 앱을 다시 시작하세요.');
    }
    if (hasPython) {
      return InferenceLaunchConfig._(
        pythonExecutable: python,
        repoRoot: root!,
        runtimeProfile: runtimeProfile,
      );
    }

    final appRoot = _windowsPath.dirname(executablePath);
    return InferenceLaunchConfig._(
      pythonExecutable: _windowsPath.join(
        appRoot,
        'runtime',
        'python',
        'python.exe',
      ),
      repoRoot: _windowsPath.join(appRoot, 'pipeline'),
      runtimeProfile: runtimeProfile,
    );
  }

  static const candidateRuntimeProfile =
      'rtx5080_15plus5_single_frame_v1';
  static const legacyRuntimeProfile = 'legacy';

  final String pythonExecutable;
  final String repoRoot;
  final String workerScript;
  final String warmupImage;
  final String runtimeProfile;

  List<String> get arguments => List.unmodifiable([
    workerScript,
    '--repo-root',
    repoRoot,
    '--device',
    'auto',
    '--runtime-profile',
    runtimeProfile,
    '--warmup-image',
    warmupImage,
  ]);

  static String _join(String root, String child) {
    final normalizedRoot = root.endsWith(r'\')
        ? root.substring(0, root.length - 1)
        : root;
    return '$normalizedRoot\\$child';
  }
}
