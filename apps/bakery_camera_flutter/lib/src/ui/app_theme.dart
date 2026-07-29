import 'package:flutter/material.dart';

const counterCanvas = Color(0xFFEEF1F4);
const cameraInk = Color(0xFF111417);
const resultPaper = Color(0xFFFFFFFF);
const actionBlue = Color(0xFF176BFF);
const confirmedTeal = Color(0xFF0E8A72);
const unknownAmber = Color(0xFFC76B00);
const failureRed = Color(0xFFC43A3A);

const tabularFigures = <FontFeature>[FontFeature.tabularFigures()];

ThemeData buildBakeryTheme() {
  const textTheme = TextTheme(
    headlineSmall: TextStyle(
      fontSize: 24,
      height: 1.25,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.5,
    ),
    titleLarge: TextStyle(
      fontSize: 19,
      height: 1.3,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.25,
    ),
    titleMedium: TextStyle(
      fontSize: 16,
      height: 1.4,
      fontWeight: FontWeight.w600,
    ),
    bodyLarge: TextStyle(fontSize: 15, height: 1.45),
    bodyMedium: TextStyle(fontSize: 13, height: 1.45),
    labelLarge: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
    labelMedium: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
  );

  return ThemeData(
    useMaterial3: true,
    fontFamily: 'Segoe UI Variable',
    fontFamilyFallback: const ['Malgun Gothic', 'Segoe UI', 'sans-serif'],
    scaffoldBackgroundColor: counterCanvas,
    colorScheme: const ColorScheme.light(
      primary: actionBlue,
      onPrimary: Colors.white,
      surface: resultPaper,
      onSurface: cameraInk,
      error: failureRed,
      onError: Colors.white,
    ),
    textTheme: textTheme,
    dividerColor: const Color(0xFFDCE1E6),
    focusColor: actionBlue.withValues(alpha: 0.14),
    filledButtonTheme: FilledButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, 52)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
        side: WidgetStateProperty.resolveWith(
          (states) => BorderSide(
            color: states.contains(WidgetState.focused)
                ? actionBlue
                : Colors.transparent,
            width: states.contains(WidgetState.focused) ? 3 : 0,
          ),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, 44)),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
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
