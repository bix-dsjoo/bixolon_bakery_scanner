import 'package:bakery_camera_prototype/src/inference/inference_launch_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses installed package layout when overrides are absent', () {
    final config = InferenceLaunchConfig.resolve(
      environment: const {},
      executablePath: r'C:\Program Files\App\bakery_camera_prototype.exe',
    );

    expect(
      config.pythonExecutable,
      r'C:\Program Files\App\runtime\python\python.exe',
    );
    expect(config.repoRoot, r'C:\Program Files\App\pipeline');
    expect(
      config.workerScript,
      r'C:\Program Files\App\pipeline\scripts\run_camera_inference_worker.py',
    );
  });

  test('both development overrides preserve repository launching', () {
    final config = InferenceLaunchConfig.resolve(
      environment: const {
        'BAKERY_INFERENCE_PYTHON': r'C:\runtime\python.exe',
        'BAKERY_REPO_ROOT': r'C:\workspace\bixolon_bakery_scanner',
      },
      executablePath: r'C:\installed\bakery_camera_prototype.exe',
    );

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
    'partial development override fails closed with actionable Korean copy',
    () {
      expect(
        () => InferenceLaunchConfig.resolve(
          environment: const {'BAKERY_REPO_ROOT': r'C:\repo'},
          executablePath: r'C:\App\app.exe',
        ),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            allOf(contains('개발 실행 경로'), contains('두 개'), contains('모두 설정')),
          ),
        ),
      );
    },
  );

  test('launch values preserve shell metacharacters as literal arguments', () {
    final config = InferenceLaunchConfig.resolve(
      environment: const {
        'BAKERY_INFERENCE_PYTHON': r'C:\runtime & tools\python.exe',
        'BAKERY_REPO_ROOT': r'C:\bakery & echo unsafe',
      },
      executablePath: r'C:\installed\bakery_camera_prototype.exe',
    );

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
