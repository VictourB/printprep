from pathlib import Path

# Partner List
PARTNERS = {
    "pepsi_titan",
    "pepsi_zero",
    "drpepper",
    "cocacola_script"
}


# Job Type Suffixes (ABXXXZZ)
TYPE_SUFFIXES = {
    "digital_print": "DP",
    "proof": "PR",
    "sample": "SA"
}
# The Master Preset List
# Dimensions in inches | case_size in units
CUP_PRESETS = {
    "12oz": {
        "top_dia": 3.5,
        "bottom_dia": 2.125,
        "length": 4.25,
        "logo_size": 2.5,
        "case_size": 72
    },
    "16oz": {
        "top_dia": 3.75,
        "bottom_dia": 2.25,
        "length": 5.0,
        "logo_size": 2.75,
        "case_size": 72
    },
    "20oz": {
        "top_dia": 3.875,
        "bottom_dia": 2.375,
        "length": 5.75,
        "logo_size": 3.0,
        "case_size": 72
    },
    "24oz": {
        "top_dia": 4.0,
        "bottom_dia": 2.5,
        "length": 6.5,
        "logo_size": 3.0,
        "case_size": 72
    },
    "32oz": {
        "top_dia": 4.25,
        "bottom_dia": 2.75,
        "length": 7.0,
        "logo_size": 3.0,
        "case_size": 24
    },
    "wine": {
        "top_dia": 3.0,
        "bottom_dia": 2.0,
        "length": 4.0,
        "logo_size": 2.0,
        "case_size": 4
    },
    "shot": {
        "top_dia": 2.0,
        "bottom_dia": 1.5,
        "length": 2.25,
        "logo_size": 1.25,
        "case_size": 200
    }
}

DEFAULT_SIZE = "20oz"