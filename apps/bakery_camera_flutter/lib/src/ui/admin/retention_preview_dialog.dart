import 'package:flutter/material.dart';

import '../../admin/retention_service.dart';

/// Shows the destructive retention boundary before it is eligible to run.
/// The preview itself is read-only; a separate explicit confirmation performs
/// the execution against the revalidated preview ID.
final class RetentionPreviewDialog extends StatefulWidget {
  const RetentionPreviewDialog({
    required this.retention,
    required this.cutoff,
    super.key,
  });

  final RetentionRepository retention;
  final DateTime cutoff;

  @override
  State<RetentionPreviewDialog> createState() => _RetentionPreviewDialogState();
}

class _RetentionPreviewDialogState extends State<RetentionPreviewDialog> {
  Future<RetentionPreview>? _future;
  bool _confirmed = false;
  bool _executing = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _future = widget.retention.preview(widget.cutoff);
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text(
      '\uC0AD\uC81C\uD560 \uAE30\uB85D \uBBF8\uB9AC \uBCF4\uAE30',
    ),
    content: SizedBox(
      width: 520,
      child: FutureBuilder<RetentionPreview>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const SizedBox(
              height: 96,
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.hasError) {
            return _PreviewError(
              onRetry: () => setState(() {
                _error = null;
                _future = widget.retention.preview(widget.cutoff);
              }),
            );
          }
          final preview = snapshot.requireData;
          return Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('\uAE30\uC900 \uC2DC\uAC01: ${_formatDate(preview.cutoff)}'),
              const SizedBox(height: 8),
              Text(
                '\uC601\uD5A5\uC744 \uBC1B\uB294 \uAC70\uB798: ${preview.affectedSessionIds.length}\uAC74',
              ),
              Text(
                '\uC0AD\uC81C\uD560 \uC774\uBBF8\uC9C0: ${preview.files.length}\uAC1C',
              ),
              Text(
                '\uC0AD\uC81C\uD560 \uC6A9\uB7C9: ${_bytes(preview.totalByteSize)}',
              ),
              const SizedBox(height: 12),
              const Text(
                '\uAC70\uB798, \uCD94\uB860 \uC601\uC218\uC99D, \uACE0\uAC1D \uC120\uD0DD, \uC8FC\uBB38, \uACB0\uC81C, \uAC80\uD1A0 \uAE30\uB85D, \uC6D0\uBCF8 SHA-256\uB294 \uBCF4\uC874\uB429\uB2C8\uB2E4.',
              ),
              const SizedBox(height: 12),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: _confirmed,
                onChanged: _executing
                    ? null
                    : (value) => setState(() => _confirmed = value ?? false),
                title: const Text(
                  '\uC774\uBBF8\uC9C0 \uC0AD\uC81C\uB294 \uB418\uB3CC\uB9B4 \uC218 \uC5C6\uC74C\uC744 \uD655\uC778\uD588\uC2B5\uB2C8\uB2E4.',
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                const Text(
                  '\uC0AD\uC81C\uB97C \uC644\uB8CC\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4. \uC138\uBD80 \uAE30\uB85D\uC744 \uD655\uC778\uD558\uC138\uC694.',
                ),
              ],
            ],
          );
        },
      ),
    ),
    actions: [
      TextButton(
        onPressed: _executing ? null : () => Navigator.of(context).pop(),
        child: const Text('\uB2EB\uAE30'),
      ),
      FutureBuilder<RetentionPreview>(
        future: _future,
        builder: (context, snapshot) => FilledButton(
          onPressed: !snapshot.hasData || !_confirmed || _executing
              ? null
              : _execute,
          child: Text(
            _executing
                ? '\uC0AD\uC81C \uC911'
                : '\uC774\uBBF8\uC9C0 \uC0AD\uC81C \uC2E4\uD589',
          ),
        ),
      ),
    ],
  );

  Future<void> _execute() async {
    final preview = (await _future)!;
    setState(() {
      _executing = true;
      _error = null;
    });
    try {
      final result = await widget.retention.execute(preview.previewId);
      if (!mounted) return;
      Navigator.of(context).pop(result);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _executing = false;
      });
    }
  }
}

class _PreviewError extends StatelessWidget {
  const _PreviewError({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      const Text(
        '\uBCF4\uC874 \uC0AD\uC81C \uB300\uC0C1\uC744 \uC548\uC804\uD558\uAC8C \uC870\uD68C\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.',
      ),
      const SizedBox(height: 12),
      OutlinedButton(
        onPressed: onRetry,
        child: const Text('\uB2E4\uC2DC \uC2DC\uB3C4'),
      ),
    ],
  );
}

String _formatDate(DateTime value) =>
    '${value.year}.${value.month.toString().padLeft(2, '0')}.${value.day.toString().padLeft(2, '0')} ${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')} UTC';

String _bytes(int value) => '${value.toString()} B';
