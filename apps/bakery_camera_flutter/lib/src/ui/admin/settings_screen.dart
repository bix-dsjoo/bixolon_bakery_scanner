import 'package:flutter/material.dart';

import '../../admin/retention_service.dart';
import '../../admin/settings_models.dart';
import '../../admin/settings_service.dart';
import 'retention_preview_dialog.dart';

/// Local kiosk settings only. Every save explicitly describes the next-session
/// boundary so a customer checkout cannot change beneath the customer.
final class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    required this.settings,
    required this.retention,
    super.key,
  });

  final KioskSettingsRepository settings;
  final RetentionRepository retention;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _retryLimit = TextEditingController();
  final _completeDuration = TextEditingController();
  final _retentionDays = TextEditingController();
  final _author = TextEditingController();
  KioskSettings? _settings;
  bool _autoReset = true;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _name.dispose();
    _retryLimit.dispose();
    _completeDuration.dispose();
    _retentionDays.dispose();
    _author.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final settings = await widget.settings.current();
      if (!mounted) return;
      _apply(settings);
      setState(() => _loading = false);
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
      _message(
        '\uC124\uC815\uC744 \uBD88\uB7EC\uC624\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.',
      );
    }
  }

  void _apply(KioskSettings value) {
    _settings = value;
    _name.text = value.kioskDisplayName;
    _retryLimit.text = value.retryLimit.toString();
    _completeDuration.text = value.paymentCompleteDurationSeconds.toString();
    _retentionDays.text = value.evidenceRetentionDays.toString();
    _author.text = value.adminAuthorLabel;
    _autoReset = value.customerAutoReset;
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _settings == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final settings = _settings;
    if (settings == null) {
      return Center(
        child: FilledButton(
          onPressed: _load,
          child: const Text('\uB2E4\uC2DC \uC2DC\uB3C4'),
        ),
      );
    }
    return Form(
      key: _formKey,
      child: ListView(
        key: const ValueKey('settings-sections'),
        children: [
          const Text(
            '\uC124\uC815\uC740 \uB2E4\uC74C \uACE0\uAC1D \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9\uB429\uB2C8\uB2E4.',
          ),
          const SizedBox(height: 16),
          _SettingsGroup(
            title: '\uACE0\uAC1D \uD654\uBA74',
            children: [
              _field(
                fieldKey: const Key('settings-kiosk-display-name'),
                controller: _name,
                label: '\uD0A4\uC624\uC2A4\uD06C \uD45C\uC2DC \uC774\uB984',
                keyboardType: TextInputType.text,
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text(
                  '\uACB0\uC81C \uD6C4 \uACE0\uAC1D \uD654\uBA74\uC73C\uB85C \uB3CC\uC544\uAC00\uAE30',
                ),
                value: _autoReset,
                onChanged: _saving
                    ? null
                    : (value) => setState(() => _autoReset = value),
              ),
              const ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('\uC5B8\uC5B4'),
                subtitle: Text(
                  '\uD55C\uAD6D\uC5B4 (ko-KR)\uB85C \uACE0\uC815\uB429\uB2C8\uB2E4.',
                ),
              ),
            ],
          ),
          _SettingsGroup(
            title: '\uACC4\uC0B0 \uC644\uB8CC',
            children: [
              _field(
                fieldKey: const Key('settings-retry-limit'),
                controller: _retryLimit,
                label: '\uC7AC\uCD2C\uC601 \uD69F\uC218 (1~5)',
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              _field(
                fieldKey: const Key('settings-complete-duration'),
                controller: _completeDuration,
                label:
                    '\uACB0\uC81C \uC644\uB8CC \uD654\uBA74 \uC2DC\uAC04 (2~10\uCD08)',
                keyboardType: TextInputType.number,
              ),
            ],
          ),
          _SettingsGroup(
            title: '\uAE30\uB85D \uBCF4\uC874',
            children: [
              _field(
                fieldKey: const Key('settings-retention-days'),
                controller: _retentionDays,
                label:
                    '\uC774\uBBF8\uC9C0 \uBCF4\uC874 \uAE30\uAC04 (7~3650\uC77C)',
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                key: const Key('retention-preview'),
                onPressed: _saving ? null : () => _previewRetention(settings),
                child: const Text(
                  '\uC0AD\uC81C\uD560 \uAE30\uB85D \uBBF8\uB9AC \uBCF4\uAE30',
                ),
              ),
            ],
          ),
          _SettingsGroup(
            title: '\uAD00\uB9AC\uC790 \uD45C\uC2DC',
            children: [
              _field(
                fieldKey: const Key('settings-admin-author'),
                controller: _author,
                label: '\uAC10\uC0AC \uAE30\uB85D \uC791\uC131\uC790',
                keyboardType: TextInputType.text,
              ),
            ],
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: Text(
              _saving ? '\uC800\uC7A5 \uC911' : '\uC124\uC815 \uC800\uC7A5',
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _field({
    required Key fieldKey,
    required TextEditingController controller,
    required String label,
    required TextInputType keyboardType,
  }) => TextFormField(
    key: fieldKey,
    controller: controller,
    enabled: !_saving,
    keyboardType: keyboardType,
    decoration: InputDecoration(labelText: label),
    validator: (value) => value == null || value.trim().isEmpty
        ? '\uC785\uB825\uD574 \uC8FC\uC138\uC694.'
        : null,
  );

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final retryLimit = int.tryParse(_retryLimit.text);
    final duration = int.tryParse(_completeDuration.text);
    final retentionDays = int.tryParse(_retentionDays.text);
    if (retryLimit == null || duration == null || retentionDays == null) {
      _message(
        '\uC22B\uC790 \uC124\uC815\uC740 \uC815\uC218\uB85C \uC785\uB825\uD574 \uC8FC\uC138\uC694.',
      );
      return;
    }
    setState(() => _saving = true);
    try {
      final saved = await widget.settings.save(
        KioskSettingsDraft(
          kioskDisplayName: _name.text,
          retryLimit: retryLimit,
          paymentCompleteDurationSeconds: duration,
          customerAutoReset: _autoReset,
          evidenceRetentionDays: retentionDays,
          locale: SettingsService.koreanLocale,
          adminAuthorLabel: _author.text,
        ),
      );
      if (!mounted) return;
      _apply(saved);
      _message(
        '\uC124\uC815\uC744 \uC800\uC7A5\uD588\uC2B5\uB2C8\uB2E4. \uB2E4\uC74C \uACE0\uAC1D \uACC4\uC0B0\uBD80\uD130 \uC801\uC6A9\uB429\uB2C8\uB2E4.',
      );
    } on ArgumentError catch (error) {
      _message(
        '\uC124\uC815 \uBC94\uC704\uB97C \uD655\uC778\uD574 \uC8FC\uC138\uC694: ${error.message}',
      );
    } catch (_) {
      _message(
        '\uC124\uC815\uC744 \uC548\uC804\uD558\uAC8C \uC800\uC7A5\uD558\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.',
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _previewRetention(KioskSettings settings) async {
    final days =
        int.tryParse(_retentionDays.text) ?? settings.evidenceRetentionDays;
    if (days < SettingsService.minEvidenceRetentionDays ||
        days > SettingsService.maxEvidenceRetentionDays) {
      _message(
        '\uC774\uBBF8\uC9C0 \uBCF4\uC874 \uAE30\uAC04\uC740 7~3650\uC77C\uC785\uB2C8\uB2E4.',
      );
      return;
    }
    await showDialog<RetentionExecutionResult>(
      context: context,
      builder: (_) => RetentionPreviewDialog(
        retention: widget.retention,
        cutoff: DateTime.now().toUtc().subtract(Duration(days: days)),
      ),
    );
  }

  void _message(String value) {
    final messenger = ScaffoldMessenger.maybeOf(context);
    messenger?.showSnackBar(SnackBar(content: Text(value)));
  }
}

class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      border: Border(top: BorderSide(color: Theme.of(context).dividerColor)),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
}
