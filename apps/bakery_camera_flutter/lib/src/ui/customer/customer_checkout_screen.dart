import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../catalog/product.dart';
import '../../checkout/checkout_controller.dart';
import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
import '../bixolon_theme_extension.dart';
import '../components/checkout_scaffold.dart';
import '../components/price_text.dart';
import 'analyzing_view.dart';
import 'catalog_picker.dart';
import 'customer_review_view.dart';
import 'order_review_view.dart';
import 'payment_view.dart';
import 'ready_view.dart';
import 'retake_required_view.dart';

class CustomerCheckoutScreen extends StatefulWidget {
  const CustomerCheckoutScreen({
    required this.controller,
    this.requiresAdminEntryConfirmation = false,
    this.onEnterAdmin,
    this.onPaymentCompleted,
    super.key,
  });

  final CheckoutController controller;
  final bool requiresAdminEntryConfirmation;
  final Future<bool> Function({required bool abandonConfirmed})? onEnterAdmin;
  final VoidCallback? onPaymentCompleted;

  @override
  State<CustomerCheckoutScreen> createState() => _CustomerCheckoutScreenState();
}

class _CustomerCheckoutScreenState extends State<CustomerCheckoutScreen> {
  _CatalogRequest? _catalogRequest;
  String? _selectedObjectId;
  CheckoutState? _previousState;

  @override
  void initState() {
    super.initState();
    _synchronizeSelection(widget.controller.state, previousState: null);
    _previousState = widget.controller.state;
    widget.controller.addListener(_changed);
  }

  @override
  void didUpdateWidget(CustomerCheckoutScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_changed);
      widget.controller.addListener(_changed);
      _selectedObjectId = null;
      _synchronizeSelection(widget.controller.state, previousState: null);
      _previousState = widget.controller.state;
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (!mounted) return;
    final state = widget.controller.state;
    _synchronizeSelection(state, previousState: _previousState);
    _previousState = state;
    setState(() {});
  }

  void _synchronizeSelection(
    CheckoutState state, {
    required CheckoutState? previousState,
  }) {
    final isReview =
        state.phase == CheckoutPhase.customerReview ||
        state.phase == CheckoutPhase.orderReview;
    if (!isReview) {
      _selectedObjectId = null;
      return;
    }

    final selectedObjectId = _selectedObjectId;
    final currentDraft = selectedObjectId == null
        ? null
        : _draftFor(state, selectedObjectId);
    if (currentDraft == null) {
      _selectedObjectId = _initialSelection(state);
      return;
    }

    if (state.phase == CheckoutPhase.customerReview &&
        previousState?.phase == CheckoutPhase.customerReview) {
      final previousDraft = _draftFor(previousState!, selectedObjectId!);
      if (previousDraft?.isResolved == false && currentDraft.isResolved) {
        _selectedObjectId = _initialSelection(state);
      }
    }
  }

  ObjectDraft? _draftFor(CheckoutState state, String objectId) => state
      .objectDrafts
      .where((draft) => draft.inferenceObject.objectId == objectId)
      .firstOrNull;

  String? _initialSelection(CheckoutState state) =>
      state.activeObject?.inferenceObject.objectId ??
      state.objectDrafts
          .where((draft) => !draft.isResolved)
          .firstOrNull
          ?.inferenceObject
          .objectId ??
      state.objectDrafts.firstOrNull?.inferenceObject.objectId;

  void _selectObject(String objectId) {
    if (_selectedObjectId == objectId) return;
    setState(() => _selectedObjectId = objectId);
  }

  void _showCatalogForObject(String objectId) => _showCatalog(objectId);

  void _showAddCatalog() => _showCatalog(null);

  void _showCatalog(String? objectId) => setState(() {
    _catalogRequest = _CatalogRequest(
      objectId: objectId,
      invokingFocus: FocusManager.instance.primaryFocus,
    );
  });

  void _closeCatalog() {
    final invokingFocus = _catalogRequest?.invokingFocus;
    setState(() => _catalogRequest = null);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (invokingFocus?.context != null && invokingFocus!.canRequestFocus) {
        invokingFocus.requestFocus();
      }
    });
  }

  Future<void> _selectCatalog(String productId) async {
    final request = _catalogRequest;
    if (request == null || request.saving) return;
    setState(() => _catalogRequest = request.savingSelection());
    try {
      final objectId = request.objectId;
      if (objectId != null) {
        if (widget.controller.state.phase == CheckoutPhase.orderReview) {
          await widget.controller.overrideResolvedProduct(objectId, productId);
        } else {
          await widget.controller.chooseCatalog(objectId, productId);
        }
      } else {
        await widget.controller.addManualProduct(productId);
      }
      if (mounted) _closeCatalog();
    } catch (_) {
      if (mounted) {
        setState(() => _catalogRequest = request.withError('상품을 변경하지 못했어요.'));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final Widget content;
    final state = widget.controller.state;
    content = switch (state.phase) {
      CheckoutPhase.ready => ReadyView(
        onScan: () => widget.controller.scan(),
        previewController: widget.controller.previewController,
      ),
      CheckoutPhase.analyzing => const AnalyzingView(),
      CheckoutPhase.retakeRequired => RetakeRequiredView(
        state: state,
        manualCartEligible: widget.controller.manualCartEligible,
        onRetake: () => widget.controller.retake(),
        onManualEntry: () => widget.controller.enterManualCart(),
      ),
      CheckoutPhase.customerReview => CustomerReviewView(
        state: state,
        selectedObjectId: _selectedObjectId,
        onSelectObject: _selectObject,
        productForCandidate: widget.controller.productForCandidate,
        onChooseTop3: (objectId, skuId) =>
            widget.controller.chooseTop3(objectId, skuId),
        onOpenCatalog: _showCatalogForObject,
        onRetakeCapture: () => widget.controller.reportCountMismatch(),
        onContinue: () => widget.controller.continueToOrderReview(),
      ),
      CheckoutPhase.orderReview => OrderReviewView(
        state: state,
        selectedObjectId: _selectedObjectId,
        onSelectObject: _selectObject,
        onSetQuantity: (productId, quantity) =>
            widget.controller.setQuantity(productId, quantity),
        onAddProduct: _showAddCatalog,
        onOverrideObject: _showCatalogForObject,
        onCountMismatch: () => widget.controller.restartCapture(),
        onPay: () => widget.controller.pay(),
        onRemoveProduct: (productId) =>
            widget.controller.removeProduct(productId),
      ),
      CheckoutPhase.paying => PaymentView(state: state),
      CheckoutPhase.paymentComplete => PaymentCompleteView(
        state: state,
        policy: widget.controller.completionPolicy,
        onNext: () async {
          await widget.controller.startNextCustomer();
          widget.onPaymentCompleted?.call();
        },
      ),
      CheckoutPhase.recoverableFailure => _FailureView(
        state: state,
        onRetry: () => widget.controller.retryFailure(),
      ),
      CheckoutPhase.terminalFailure => _UnavailableView(
        onNext: () => widget.controller.startNextCustomer(),
      ),
    };
    final request = _catalogRequest;
    final layeredContent = Stack(
      children: [
        content,
        if (request != null)
          _OrderReviewCatalogPanel(
            discovery: widget.controller.customerCatalogDiscovery,
            search: widget.controller.searchSessionCatalog,
            onSelected: (product) => _selectCatalog(product.productId),
            onClose: _closeCatalog,
            saving: request.saving,
            errorText: request.errorText,
          ),
      ],
    );
    final scopedContent = KioskDisplayNameScope(
      displayName: widget.controller.kioskDisplayName,
      child: layeredContent,
    );
    if (widget.onEnterAdmin == null ||
        state.phase != CheckoutPhase.ready ||
        _catalogRequest != null) {
      return scopedContent;
    }
    return KioskHeaderActionScope(
      action: CustomerAdminEntryControl(
        requiresAdminEntryConfirmation: widget.requiresAdminEntryConfirmation,
        onEnterAdmin: widget.onEnterAdmin!,
      ),
      child: scopedContent,
    );
  }
}

final class _CatalogRequest {
  const _CatalogRequest({
    required this.objectId,
    required this.invokingFocus,
    this.saving = false,
    this.errorText,
  });

  final String? objectId;
  final FocusNode? invokingFocus;
  final bool saving;
  final String? errorText;

  _CatalogRequest savingSelection() => _CatalogRequest(
    objectId: objectId,
    invokingFocus: invokingFocus,
    saving: true,
  );

  _CatalogRequest withError(String message) => _CatalogRequest(
    objectId: objectId,
    invokingFocus: invokingFocus,
    errorText: message,
  );
}

class _CloseCatalogIntent extends Intent {
  const _CloseCatalogIntent();
}

class _OrderReviewCatalogPanel extends StatefulWidget {
  const _OrderReviewCatalogPanel({
    required this.discovery,
    required this.search,
    required this.onSelected,
    required this.onClose,
    required this.saving,
    required this.errorText,
  });

  final CustomerCatalogDiscovery discovery;
  final Future<List<Product>> Function(String query) search;
  final ValueChanged<Product> onSelected;
  final VoidCallback onClose;
  final bool saving;
  final String? errorText;

  @override
  State<_OrderReviewCatalogPanel> createState() =>
      _OrderReviewCatalogPanelState();
}

class _OrderReviewCatalogPanelState extends State<_OrderReviewCatalogPanel> {
  final _scopeNode = FocusScopeNode(debugLabel: 'catalog-panel');
  final _closeFocusNode = FocusNode(debugLabel: 'catalog-panel-close');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _closeFocusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _closeFocusNode.dispose();
    _scopeNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = BixolonThemeExtension.of(context);
    final width = (MediaQuery.sizeOf(context).width - 32)
        .clamp(0.0, 480.0)
        .toDouble();
    return Positioned.fill(
      child: FocusTraversalGroup(
        child: Shortcuts(
          shortcuts: const {
            SingleActivator(LogicalKeyboardKey.escape): _CloseCatalogIntent(),
          },
          child: Actions(
            actions: {
              _CloseCatalogIntent: CallbackAction<_CloseCatalogIntent>(
                onInvoke: (_) {
                  if (!widget.saving) widget.onClose();
                  return null;
                },
              ),
            },
            child: FocusScope(
              node: _scopeNode,
              child: Stack(
                children: [
                  ModalBarrier(
                    color: Colors.black.withValues(alpha: 0.14),
                    dismissible: !widget.saving,
                    semanticsLabel: '상품 변경 닫기',
                    onDismiss: widget.onClose,
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: SafeArea(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: SizedBox(
                          key: const Key('order-review-catalog-panel'),
                          width: width,
                          child: Material(
                            elevation: 2,
                            clipBehavior: Clip.antiAlias,
                            borderRadius: BorderRadius.circular(
                              tokens.modalRadius,
                            ),
                            child: DecoratedBox(
                              decoration: BoxDecoration(
                                border: Border.all(
                                  color: Theme.of(context).dividerColor,
                                ),
                                borderRadius: BorderRadius.circular(
                                  tokens.modalRadius,
                                ),
                              ),
                              child: SingleChildScrollView(
                                padding: const EdgeInsets.all(16),
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    if (widget.errorText case final error?) ...[
                                      Semantics(
                                        liveRegion: true,
                                        child: Text(
                                          error,
                                          style: TextStyle(
                                            color: Theme.of(
                                              context,
                                            ).colorScheme.error,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(height: 12),
                                    ],
                                    IgnorePointer(
                                      ignoring: widget.saving,
                                      child: CatalogPicker(
                                        discovery: widget.discovery,
                                        search: widget.search,
                                        onSelected: widget.onSelected,
                                        onClose: widget.onClose,
                                        closeFocusNode: _closeFocusNode,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Customer-surface entry point for the prototype administrator console.
///
/// It is deliberately independent of camera, inference, and audit runtime so
/// the mandatory abandonment confirmation remains directly testable.
class CustomerAdminEntryControl extends StatelessWidget {
  const CustomerAdminEntryControl({
    required this.requiresAdminEntryConfirmation,
    required this.onEnterAdmin,
    super.key,
  });

  final bool requiresAdminEntryConfirmation;
  final Future<bool> Function({required bool abandonConfirmed}) onEnterAdmin;

  Future<void> _requestAdminEntry(BuildContext context) async {
    var confirmed = true;
    if (requiresAdminEntryConfirmation) {
      confirmed =
          await showModalBottomSheet<bool>(
            context: context,
            builder: (context) => AdminEntryConfirmationSheet(
              onCancel: () => Navigator.of(context).pop(false),
              onConfirm: () => Navigator.of(context).pop(true),
            ),
          ) ??
          false;
    }
    if (!confirmed || !context.mounted) return;
    await onEnterAdmin(abandonConfirmed: true);
  }

  @override
  Widget build(BuildContext context) => TextButton(
    onPressed: () => _requestAdminEntry(context),
    child: const Text('관리자'),
  );
}

/// Confirmation shown before the prototype abandons an unfinished checkout.
///
/// This remains usable as a standalone sheet so the safety-critical copy and
/// choice can be tested without booting camera, worker, or audit runtime.
class AdminEntryConfirmationSheet extends StatelessWidget {
  const AdminEntryConfirmationSheet({
    required this.onCancel,
    required this.onConfirm,
    super.key,
  });

  final VoidCallback onCancel;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('관리자 모드로 이동할까요?', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          const Text('진행 중인 고객 계산은 취소되고 기록으로 남습니다.'),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: onConfirm,
            child: const Text('계산을 취소하고 관리자 모드로 이동'),
          ),
          const SizedBox(height: 8),
          TextButton(onPressed: onCancel, child: const Text('계속 계산하기')),
        ],
      ),
    ),
  );
}

class PaymentCompleteView extends StatefulWidget {
  const PaymentCompleteView({
    required this.state,
    required this.policy,
    required this.onNext,
    super.key,
  });

  final CheckoutState state;
  final CustomerCompletionPolicy policy;
  final Future<void> Function() onNext;

  @override
  State<PaymentCompleteView> createState() => _PaymentCompleteViewState();
}

class _PaymentCompleteViewState extends State<PaymentCompleteView> {
  Timer? _timer;
  bool _startingNextCustomer = false;

  @override
  void initState() {
    super.initState();
    if (widget.policy.autoReset) {
      _timer = Timer(widget.policy.duration, () {
        unawaited(_startNextCustomer());
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _startNextCustomer() async {
    if (_startingNextCustomer) return;
    _timer?.cancel();
    setState(() => _startingNextCustomer = true);
    try {
      await widget.onNext();
    } on StateError {
      // The competing terminal reset owns the transition; never surface a
      // technical state race to the customer.
    } finally {
      if (mounted) setState(() => _startingNextCustomer = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final receipt = widget.state.paymentReceipt;
    return CheckoutScaffold(
      title: '결제 완료',
      scrollable: false,
      primaryAction: BakeryPrimaryButton(
        label: '다음 고객 시작',
        onPressed: _startingNextCustomer ? null : _startNextCustomer,
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Column(
            key: const Key('payment-complete-summary'),
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Center(child: PaymentCompleteIllustration()),
              const SizedBox(height: 12),
              const BakeryStatusBanner(
                status: BakeryStatus.ready,
                title: '결제가 완료됐어요',
                message: '이용해 주셔서 감사합니다.',
              ),
              const SizedBox(height: 16),
              Text('결제 금액', style: Theme.of(context).textTheme.titleMedium),
              PriceText(
                amount: receipt?.amount ?? 0,
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FailureView extends StatelessWidget {
  const _FailureView({required this.state, required this.onRetry});

  final CheckoutState state;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => CheckoutScaffold(
    title: '다시 확인',
    primaryAction: BakeryPrimaryButton(label: '다시 시도', onPressed: onRetry),
    child: const Padding(
      padding: EdgeInsets.only(top: 24),
      child: BakeryStatusBanner(
        status: BakeryStatus.error,
        title: '처리를 이어갈 수 없어요',
        message: '다시 시도해 주세요.',
      ),
    ),
  );
}

class _UnavailableView extends StatelessWidget {
  const _UnavailableView({required this.onNext});

  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) => CheckoutScaffold(
    title: '셀프 계산',
    primaryAction: BakeryPrimaryButton(label: '처음으로', onPressed: onNext),
    child: const Padding(
      padding: EdgeInsets.only(top: 24),
      child: BakeryStatusBanner(
        status: BakeryStatus.error,
        title: '계산대를 준비하지 못했어요',
        message: '직원에게 알려주세요.',
      ),
    ),
  );
}
