import 'package:flutter/material.dart';

import 'bixolon_brand.dart';
import 'bixolon_theme_extension.dart';

const counterCanvas = bixolonCanvas;
const cameraInk = bixolonInk;
const resultPaper = Color(0xFFFFFFFF);
const actionBlue = Color(0xFF176BFF);
const confirmedTeal = Color(0xFF0E8A72);
const unknownAmber = Color(0xFFC76B00);
const failureRed = Color(0xFFC43A3A);

const tabularFigures = <FontFeature>[FontFeature.tabularFigures()];

ThemeData buildBakeryTheme() {
  const tokens = BixolonThemeExtension.bixolon;
  const textTheme = TextTheme(
    headlineSmall: TextStyle(
      fontSize: 24,
      height: 1.35,
      fontWeight: FontWeight.w500,
    ),
    titleLarge: TextStyle(
      fontSize: 18,
      height: 1.35,
      fontWeight: FontWeight.w600,
      fontFeatures: tabularFigures,
    ),
    titleMedium: TextStyle(
      fontSize: 15,
      height: 1.35,
      fontWeight: FontWeight.w600,
    ),
    bodyLarge: TextStyle(
      fontSize: 14,
      height: 1.4,
      fontWeight: FontWeight.w500,
    ),
    bodyMedium: TextStyle(
      fontSize: 13,
      height: 1.35,
      fontWeight: FontWeight.w400,
    ),
    labelLarge: TextStyle(
      fontSize: 16,
      height: 1.35,
      fontWeight: FontWeight.w600,
    ),
    labelMedium: TextStyle(
      fontSize: 12,
      height: 1.4,
      fontWeight: FontWeight.w500,
    ),
  );

  return ThemeData(
    useMaterial3: true,
    fontFamily: 'Pretendard',
    fontFamilyFallback: const ['Pretendard', 'Malgun Gothic', 'Segoe UI'],
    scaffoldBackgroundColor: tokens.canvas,
    colorScheme: ColorScheme.light(
      primary: tokens.action,
      onPrimary: Colors.white,
      surface: tokens.paper,
      onSurface: tokens.ink,
      error: tokens.error,
      onError: Colors.white,
    ),
    extensions: [tokens],
    textTheme: textTheme,
    dividerColor: tokens.divider,
    dividerTheme: const DividerThemeData(
      color: Color(0xFFE8E8E8),
      thickness: 1,
      space: 1,
    ),
    cardTheme: CardThemeData(
      color: tokens.paper,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: tokens.divider),
        borderRadius: BorderRadius.circular(tokens.surfaceRadius),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: false,
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 12),
      enabledBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: tokens.divider),
      ),
      focusedBorder: UnderlineInputBorder(
        borderSide: BorderSide(color: tokens.focus, width: 2),
      ),
    ),
    listTileTheme: ListTileThemeData(
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      minTileHeight: 48,
      shape: const RoundedRectangleBorder(),
      iconColor: tokens.mutedInk,
      textColor: tokens.ink,
    ),
    focusColor: tokens.focus.withValues(alpha: 0.14),
    filledButtonTheme: FilledButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, 52)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(tokens.controlRadius),
          ),
        ),
        side: WidgetStateProperty.resolveWith(
          (states) => BorderSide(
            color: states.contains(WidgetState.focused)
                ? tokens.focus
                : Colors.transparent,
            width: states.contains(WidgetState.focused)
                ? bixolonControlBorderWidth
                : 0,
          ),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, 44)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(tokens.controlRadius),
          ),
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, 44)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(tokens.controlRadius),
          ),
        ),
        side: WidgetStatePropertyAll(
          BorderSide(
            color: tokens.controlBorder,
            width: bixolonControlBorderWidth,
          ),
        ),
      ),
    ),
    expansionTileTheme: const ExpansionTileThemeData(
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.only(bottom: 12),
      shape: Border(),
      collapsedShape: Border(),
      iconColor: Color(0xFF5A6470),
      collapsedIconColor: Color(0xFF5A6470),
    ),
  );
}
