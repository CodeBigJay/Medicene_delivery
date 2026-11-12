"""Shared look and feel: one place to change colours and spacing."""
import flet as ft

SEED = ft.Colors.TEAL
PAD = 20
GAP = 12
BODY_SIZE = 16      # readable body text (accessibility)
TITLE_SIZE = 24

STATUS_COLORS = {
    "Ready": ft.Colors.ORANGE_700,
    "Collected": ft.Colors.BLUE_700,
    "Delivered": ft.Colors.GREEN_700,
    "Returned": ft.Colors.RED_700,
}


def make_theme():
    return ft.Theme(color_scheme_seed=SEED)
