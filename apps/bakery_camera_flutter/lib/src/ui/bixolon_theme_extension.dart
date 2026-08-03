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
    required this.selectedSurface,
    required this.controlBorder,
    required this.disabledAction,
    required this.focus,
    required this.confirmed,
    required this.uncertainty,
    required this.error,
    required this.controlRadius,
    required this.surfaceRadius,
    required this.modalRadius,
  });

  static const bixolon = BixolonThemeExtension(
    canvas: Color(0xFFFFFFFF),
    paper: Color(0xFFFFFFFF),
    ink: Color(0xFF000000),
    mutedInk: Color(0xFF5C5C5C),
    divider: Color(0xFFE8E8E8),
    action: Color(0xFFEE7203),
    selectedSurface: Color(0xFFFCEAD9),
    controlBorder: Color(0xFFD8D8D8),
    disabledAction: Color(0xFFFAD5B3),
    focus: Color(0xFF184C9F),
    confirmed: Color(0xFF268B20),
    uncertainty: Color(0xFFC76B00),
    error: Color(0xFFCC2427),
    controlRadius: 5,
    surfaceRadius: 5,
    modalRadius: 10,
  );

  final Color canvas;
  final Color paper;
  final Color ink;
  final Color mutedInk;
  final Color divider;
  final Color action;
  final Color selectedSurface;
  final Color controlBorder;
  final Color disabledAction;
  final Color focus;
  final Color confirmed;
  final Color uncertainty;
  final Color error;
  final double controlRadius;
  final double surfaceRadius;
  final double modalRadius;

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
    Color? selectedSurface,
    Color? controlBorder,
    Color? disabledAction,
    Color? focus,
    Color? confirmed,
    Color? uncertainty,
    Color? error,
    double? controlRadius,
    double? surfaceRadius,
    double? modalRadius,
  }) => BixolonThemeExtension(
    canvas: canvas ?? this.canvas,
    paper: paper ?? this.paper,
    ink: ink ?? this.ink,
    mutedInk: mutedInk ?? this.mutedInk,
    divider: divider ?? this.divider,
    action: action ?? this.action,
    selectedSurface: selectedSurface ?? this.selectedSurface,
    controlBorder: controlBorder ?? this.controlBorder,
    disabledAction: disabledAction ?? this.disabledAction,
    focus: focus ?? this.focus,
    confirmed: confirmed ?? this.confirmed,
    uncertainty: uncertainty ?? this.uncertainty,
    error: error ?? this.error,
    controlRadius: controlRadius ?? this.controlRadius,
    surfaceRadius: surfaceRadius ?? this.surfaceRadius,
    modalRadius: modalRadius ?? this.modalRadius,
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
      selectedSurface: Color.lerp(selectedSurface, other.selectedSurface, t)!,
      controlBorder: Color.lerp(controlBorder, other.controlBorder, t)!,
      disabledAction: Color.lerp(disabledAction, other.disabledAction, t)!,
      focus: Color.lerp(focus, other.focus, t)!,
      confirmed: Color.lerp(confirmed, other.confirmed, t)!,
      uncertainty: Color.lerp(uncertainty, other.uncertainty, t)!,
      error: Color.lerp(error, other.error, t)!,
      controlRadius: controlRadius + (other.controlRadius - controlRadius) * t,
      surfaceRadius: surfaceRadius + (other.surfaceRadius - surfaceRadius) * t,
      modalRadius: modalRadius + (other.modalRadius - modalRadius) * t,
    );
  }
}
