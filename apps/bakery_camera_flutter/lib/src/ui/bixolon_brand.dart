import 'package:flutter/material.dart';

const bixolonOrange = Color(0xFFEE7203);
const bixolonCanvas = Color(0xFFF7F7F5);
const bixolonInk = Color(0xFF171717);
const bixolonMutedInk = Color(0xFF626262);
const bixolonDivider = Color(0xFFE5E3E0);
const double bixolonControlBorderWidth = 1;
const double bixolonControlRadius = 6;
const double bixolonStatusDotSize = 8;

class BixolonWordmark extends StatelessWidget {
  const BixolonWordmark({super.key, this.style});

  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final textStyle =
        style ?? Theme.of(context).textTheme.titleLarge ?? const TextStyle();
    return Text(
      'BIXOLON',
      style: textStyle.copyWith(
        color: bixolonOrange,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.4,
      ),
    );
  }
}

class BixolonStatusDot extends StatelessWidget {
  const BixolonStatusDot({
    required this.label,
    super.key,
    this.color = bixolonOrange,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Semantics(
    label: label,
    child: ExcludeSemantics(
      child: SizedBox.square(
        dimension: bixolonStatusDotSize,
        child: DecoratedBox(
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
      ),
    ),
  );
}

/// Temporary source-compatible placeholder while the screen shell migrates.
///
/// The former X motif has intentionally been removed; this emits no visual
/// decoration and will be removed with its remaining screen call sites.
@Deprecated('The X motif was removed. Do not add this to new UI.')
class BixolonBrandDecoration extends StatelessWidget {
  const BixolonBrandDecoration({super.key, this.size = 0});

  final double size;

  @override
  Widget build(BuildContext context) =>
      const ExcludeSemantics(child: SizedBox.shrink());
}
