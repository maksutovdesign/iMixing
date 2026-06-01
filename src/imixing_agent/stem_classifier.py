from __future__ import annotations

from pathlib import Path


ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kick": ("kick", "bd", "бочка"),
    "snare": ("snare", "sd", "clap", "снейр", "малый"),
    "drums": ("drum", "drums", "perc", "percussion", "hat", "cymbal", "барабан"),
    "bass": ("bass", "sub", "808", "бас"),
    "backing_vocals": ("backing", "bvox", "choir", "harmony", "бек"),
    "lead_vocal": ("lead vocal", "lead_vocal", "vocal", "vox", "voice", "вокал"),
    "guitar": ("guitar", "gtr", "гитара"),
    "keys": ("piano", "keys", "keyboard", "rhodes", "organ", "melody", "melodic", "пиано", "клав", "мелод"),
    "synth": ("synth", "pad", "lead", "arp", "синт"),
    "fx": ("fx", "sfx", "riser", "impact", "noise", "эффект"),
}


def classify_stem(path: Path) -> str:
    normalized = path.stem.lower().replace("-", " ").replace("_", " ")

    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return role

    return "other"
