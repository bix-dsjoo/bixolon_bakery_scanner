import 'dart:async';

import 'package:flutter/material.dart';

import '../../checkout/checkout_controller.dart';
import '../../checkout/checkout_models.dart';
import '../../checkout/checkout_state.dart';
import '../components/bakery_primary_button.dart';
import '../components/bakery_status_banner.dart';
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
  const CustomerCheckoutScreen({required this.controller, super.key});

  final CheckoutController controller;

  @override
  State<CustomerCheckoutScreen> createState() => _CustomerCheckoutScreenState();
}

class _CustomerCheckoutScreenState extends State<CustomerCheckoutScreen> {
  String? _catalogObjectId;
  bool _catalogAddsProduct = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_changed);
  }

  @override
  void didUpdateWidget(CustomerCheckoutScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_changed);
      widget.controller.addListener(_changed);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  void _showCatalogForObject(String objectId) => setState(() {
    _catalogObjectId = objectId;
    _catalogAddsProduct = false;
  });

  void _showAddCatalog() => setState(() {
    _catalogObjectId = null;
    _catalogAddsProduct = true;
  });

  Future<void> _selectCatalog(String productId) async {
    final objectId = _catalogObjectId;
    setState(() {
      _catalogObjectId = null;
      _catalogAddsProduct = false;
    });
    if (objectId != null) {
      if (widget.controller.state.phase == CheckoutPhase.orderReview) {
        await widget.controller.overrideResolvedProduct(objectId, productId);
      } else {
        await widget.controller.chooseCatalog(objectId, productId);
      }
    } else {
      await widget.controller.addManualProduct(productId);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_catalogObjectId != null || _catalogAddsProduct) {
      return CheckoutScaffold(
        title: '상품 찾기',
        primaryAction: const SizedBox(height: 56),
        child: Padding(
          padding: const EdgeInsets.only(top: 16),
          child: CatalogPicker(
            catalog: widget.controller.catalogRepository,
            onSelected: (product) => _selectCatalog(product.productId),
          ),
        ),
      );
    }
    final state = widget.controller.state;
    return switch (state.phase) {
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
        productForCandidate: widget.controller.productForCandidate,
        onChooseTop3: (objectId, skuId) =>
            widget.controller.chooseTop3(objectId, skuId),
        onOpenCatalog: _showCatalogForObject,
        onContinue: () => widget.controller.continueToOrderReview(),
      ),
      CheckoutPhase.orderReview => OrderReviewView(
        state: state,
        onSetQuantity: (productId, quantity) =>
            widget.controller.setQuantity(productId, quantity),
        onAddProduct: _showAddCatalog,
        onOverrideObject: _showCatalogForObject,
        onCountMismatch: () => widget.controller.reportCountMismatch(),
        onPay: () => widget.controller.pay(),
        onRemoveProduct: (productId) =>
            widget.controller.removeProduct(productId),
      ),
      CheckoutPhase.paying => PaymentView(state: state),
      CheckoutPhase.paymentComplete => PaymentCompleteView(
        state: state,
        policy: widget.controller.completionPolicy,
        onNext: () => unawaited(widget.controller.startNextCustomer()),
      ),
      CheckoutPhase.recoverableFailure => _FailureView(
        state: state,
        onRetry: () => widget.controller.retryFailure(),
      ),
      CheckoutPhase.terminalFailure => _UnavailableView(
        onNext: () => widget.controller.startNextCustomer(),
      ),
    };
  }
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
  final VoidCallback onNext;

  @override
  State<PaymentCompleteView> createState() => _PaymentCompleteViewState();
}

class _PaymentCompleteViewState extends State<PaymentCompleteView> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    if (widget.policy.autoReset) {
      _timer = Timer(widget.policy.duration, widget.onNext);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final receipt = widget.state.paymentReceipt;
    return CheckoutScaffold(
      title: '결제 완료',
      primaryAction: BakeryPrimaryButton(
        label: '다음 고객 시작',
        onPressed: widget.onNext,
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const BakeryStatusBanner(
              status: BakeryStatus.ready,
              title: '결제가 완료됐어요',
              message: '이용해 주셔서 감사합니다.',
            ),
            const SizedBox(height: 20),
            Text('결제 금액', style: Theme.of(context).textTheme.titleMedium),
            PriceText(
              amount: receipt?.amount ?? 0,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
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
