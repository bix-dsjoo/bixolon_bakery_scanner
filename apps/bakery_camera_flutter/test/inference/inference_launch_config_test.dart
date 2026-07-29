import 'package:bakery_camera_prototype/src/inference/inference_launch_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('launch config resolves only explicit environment values', () {
    final config = InferenceLaunchConfig.fromEnvironment({
      'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
      'BAKERY_REPO_ROOT': r'C:\workspace\bixolon_bakery_scanner',
    });

    expect(config.pythonExecutable, r'C:\runtime\python.exe');
    expect(config.repoRoot, r'C:\workspace\bixolon_bakery_scanner');
    expect(
      config.workerScript,
      endsWith(r'scripts\run_camera_inference_worker.py'),
    );
    expect(
      config.warmupImage,
      endsWith(r'samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg'),
    );
  });

  test(
    'missing launch environment fails closed with actionable Korean copy',
    () {
      expect(
        () => InferenceLaunchConfig.fromEnvironment(const {}),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            allOf(
              contains('BAKERY_INFERENCE_PYTHON'),
              contains('환경 변수'),
              contains('설정'),
            ),
          ),
        ),
      );

      expect(
        () => InferenceLaunchConfig.fromEnvironment(const {
          'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
        }),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            allOf(
              contains('BAKERY_REPO_ROOT'),
              contains('환경 변수'),
              contains('설정'),
            ),
          ),
        ),
      );
    },
  );

  test('launch values preserve shell metacharacters as literal arguments', () {
    final config = InferenceLaunchConfig.fromEnvironment({
      'BAKERY_INFERENCE_PYTHON': r'C:\runtime & tools\python.exe',
      'BAKERY_REPO_ROOT': r'C:\bakery & echo unsafe',
    });

    expect(config.pythonExecutable, r'C:\runtime & tools\python.exe');
    expect(config.repoRoot, r'C:\bakery & echo unsafe');
    expect(config.arguments, <String>[
      r'C:\bakery & echo unsafe\scripts\run_camera_inference_worker.py',
      '--repo-root',
      r'C:\bakery & echo unsafe',
      '--device',
      'auto',
      '--warmup-image',
      r'C:\bakery & echo unsafe\samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg',
    ]);
  });
}
