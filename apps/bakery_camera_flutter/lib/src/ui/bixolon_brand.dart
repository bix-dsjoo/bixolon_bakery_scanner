import 'package:flutter/material.dart';

const bixolonOrange = Color(0xFFEE7203);
const bixolonCanvas = Color(0xFFF7F7F5);
const bixolonInk = Color(0xFF171717);
const bixolonMutedInk = Color(0xFF626262);
const bixolonDivider = Color(0xFFE5E3E0);

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
        fontWeight: FontWeight.w800,
        letterSpacing: 0.4,
      ),
    );
  }
}

class BixolonBrandDecoration extends StatelessWidget {
  const BixolonBrandDecoration({super.key, this.size = 64});

  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox.square(
      dimension: size,
      child: CustomPaint(painter: _BixolonXMotifPainter()),
    ),
  );
}

class _BixolonXMotifPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = bixolonOrange.withValues(alpha: 0.10)
      ..strokeWidth = size.width * 0.18
      ..strokeCap = StrokeCap.square;
    canvas.drawLine(Offset.zero, Offset(size.width, size.height), paint);
    canvas.drawLine(Offset(0, size.height), Offset(size.width, 0), paint);
  }

  @override
  bool shouldRepaint(covariant _BixolonXMotifPainter oldDelegate) => false;
}
