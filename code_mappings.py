DIAGNOSIS_MAP = {
    41: "Ingested foreign object",
    42: "Aspirated foreign object",
    46: "Burns, electrical",
    47: "Burns, not specified",
    48: "Burns, scald",
    49: "Burns, chemical",
    50: "Amputation",
    51: "Burns, thermal",
    52: "Concussion",
    53: "Contusion/abrasion",
    54: "Crushing",
    55: "Dislocation",
    56: "Electric shock",
    57: "Fracture",
    58: "Hematoma",
    59: "Laceration",
    60: "Dental injury",
    61: "Nerve damage",
    62: "Internal organ injury",
    63: "Puncture",
    64: "Sprain/strain",
    65: "Anoxia",
    66: "Hemorrhage",
    67: "Poisoning",
    68: "Dermatitis/conjunctivitis",
    69: "Submersion",
    71: "Other/not stated",
    72: "Avulsion",
    73: "Radiation",
    74: "Strain/sprain",
}

BODY_PART_MAP = {
    0: "Internal",
    30: "Shoulder",
    31: "Upper trunk",
    32: "Elbow",
    33: "Lower arm",
    34: "Wrist",
    35: "Knee",
    36: "Lower leg",
    37: "Ankle",
    38: "Pubic region",
    75: "Head",
    76: "Face",
    77: "Eyeball",
    79: "Lower trunk",
    80: "Upper arm",
    81: "Upper leg",
    82: "Hand",
    83: "Foot",
    84: "25-50% of body",
    85: "All parts of body",
    87: "Not recorded",
    88: "Mouth",
    89: "Neck",
    92: "Finger",
    93: "Toe",
    94: "Ear",
}

DISPOSITION_MAP = {
    1: "Treated/released",
    2: "Treated/transferred",
    4: "Treated/admitted",
    5: "Held for observation",
    6: "Left without being seen",
    8: "Fatality",
    9: "Unknown/not recorded",
}


def label_code(value, mapping):
    """
    Convert a numeric NEISS code to a readable label.
    Keeps the original code visible for transparency.
    """
    try:
        code = int(value)
    except Exception:
        return str(value)

    label = mapping.get(code)

    if label:
        return f"{code} - {label}"

    return str(code)
