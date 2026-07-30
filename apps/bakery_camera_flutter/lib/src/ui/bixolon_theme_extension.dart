import 'package:flutter/material.dart';

/// Immutable BIXOLON visual tokens shared by customer-facing surfaces.
@immutable
class BixolonThemeExtension extends ThemeExtension<BixolonThemeExtension> {
  const BixolonThemeExtension({
    required this.canvas,
    required this.paper,
    required this.ink,
    required this.mutedInk,
    required this.divider,
    required this.action,
    required this.focus,
    required this.confirmed,
    required this.uncertainty,
    required this.error,
    required this.controlRadius,
    required this.surfaceRadius,
  });

  static const bixolon = BixolonThemeExtension(
    canvas: Color(0xFFF7F7F5),
    paper: Color(0xFFFFFFFF),
    ink: Color(0xFF171717),
    mutedInk: Color(0xFF626262),
    divider: Color(0xFFE5E3E0),
    action: Color(0xFFEE7203),
    focus: Color(0xFF176BFF),
    confirmed: Color(0xFF0E8A72),
    uncertainty: Color(0xFFC76B00),
    error: Color(0xFFC43A3A),
    controlRadius: 6,
    surfaceRadius: 12,
  );

  final Color canvas;
  final Color paper;
  final Color ink;
  final Color mutedInk;
  final Color divider;
  final Color action;
  final Color focus;
  final Color confirmed;
  final Color uncertainty;
  final Color error;
  final double controlRadius;
  final double surfaceRadius;

  static BixolonThemeExtension of(BuildContext context) =>
      Theme.of(context).extension<BixolonThemeExtension>() ?? bixolon;

  @override
  BixolonThemeExtension copyWith({
    Color? canvas,
    Color? paper,
    Color? ink,
    Color? mutedInk,
    Color? divider,
    Color? action,
    Color? focus,
    Color? confirmed,
    Color? uncertainty,
    Color? error,
    double? controlRadius,
    double? surfaceRadius,
  }) => BixolonThemeExtension(
    canvas: canvas ?? this.canvas,
    paper: paper ?? this.paper,
    ink: ink ?? this.ink,
    mutedInk: mutedInk ?? this.mutedInk,
    divider: divider ?? this.divider,
    action: action ?? this.action,
    focus: focus ?? this.focus,
    confirmed: confirmed ?? this.confirmed,
    uncertainty: uncertainty ?? this.uncertainty,
    error: error ?? this.error,
    controlRadius: controlRadius ?? this.controlRadius,
    surfaceRadius: surfaceRadius ?? this.surfaceRadius,
  );

  @override
  BixolonThemeExtension lerp(covariant BixolonThemeExtension? other, double t) {
    if (other is! BixolonThemeExtension) return this;
    return BixolonThemeExtension(
      canvas: Color.lerp(canvas, other.canvas, t)!,
      paper: Color.lerp(paper, other.paper, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      mutedInk: Color.lerp(mutedInk, other.mutedInk, t)!,
      divider: Color.lerp(divider, other.divider, t)!,
      action: Color.lerp(action, other.action, t)!,
      focus: Color.lerp(focus, other.focus, t)!,
      confirmed: Color.lerp(confirmed, other.confirmed, t)!,
      uncertainty: Color.lerp(uncertainty, other.uncertainty, t)!,
      error: Color.lerp(error, other.error, t)!,
      controlRadius: controlRadius + (other.controlRadius - controlRadius) * t,
      surfaceRadius: surfaceRadius + (other.surfaceRadius - surfaceRadius) * t,
    );
  }
}
