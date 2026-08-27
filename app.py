from flask import Flask, jsonify, request
from endplay.types import Deal, Player, Denom
from endplay.dds import calc_dd_table

app = Flask(__name__)

SEATS_CLOCKWISE = ["N", "E", "S", "W"]
RANKS = set("AKQJT98765432")

PLAYERS = [
    ("N", Player.north),
    ("S", Player.south),
    ("E", Player.east),
    ("W", Player.west),
]

# Use Denom.find(...) instead of enum attribute names.
# This is more robust across endplay builds where the public enum aliases can differ.
DENOMS = [
    ("NT", Denom.find("NT")),
    ("S", Denom.find("S")),
    ("H", Denom.find("H")),
    ("D", Denom.find("D")),
    ("C", Denom.find("C")),
]


def validate_full_deal(dealstr: str):
    if not isinstance(dealstr, str) or ":" not in dealstr:
        raise ValueError("dealstr must be a full PBN-style deal such as N:...")

    start_raw, hands_raw = dealstr.split(":", 1)
    start = start_raw.strip().upper()

    if start not in SEATS_CLOCKWISE:
        raise ValueError("Starting seat must be N, E, S or W.")

    hands = hands_raw.strip().split()
    if len(hands) != 4:
        raise ValueError("Exactly four hands are required.")

    start_index = SEATS_CLOCKWISE.index(start)
    seat_hands = {
        SEATS_CLOCKWISE[(start_index + i) % 4]: hands[i]
        for i in range(4)
    }

    seen = set()
    suit_names = ["S", "H", "D", "C"]

    for seat in SEATS_CLOCKWISE:
        suits = seat_hands[seat].split(".")
        if len(suits) != 4:
            raise ValueError(f"{seat}: hand must contain S.H.D.C.")

        count = 0
        for suit_index, holding in enumerate(suits):
            for rank in holding.upper():
                if rank not in RANKS:
                    raise ValueError(f"{seat}: invalid rank {rank}.")
                card_id = f"{suit_names[suit_index]}{rank}"
                if card_id in seen:
                    raise ValueError(f"Duplicate card detected: {card_id}.")
                seen.add(card_id)
                count += 1

        if count != 13:
            raise ValueError(f"{seat}: hand contains {count} cards, not 13.")

    if len(seen) != 52:
        raise ValueError(f"Deal contains {len(seen)} unique cards, not 52.")

    return seat_hands


def direct_dd_table(table):
    rows = []
    for declarer_label, player in PLAYERS:
        for denom_label, denom in DENOMS:
            rows.append(
                {
                    "declarer": declarer_label,
                    "denomination": denom_label,
                    "result": int(table[player, denom]),
                }
            )
    return rows


@app.get("/")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "bridge-dds-native",
            "engine": "Bo Haglund DDS via endplay",
            "endpoint": "POST /dd",
            "qa": (
                "Direct DDS table calculation only. "
                "Final DD validation requires OptimumResultTable."
            ),
        }
    )


@app.post("/dd")
def solve_dd():
    try:
        payload = request.get_json(silent=True) or {}
        dealstr = payload.get("dealstr")

        if not dealstr:
            return jsonify(
                {
                    "ok": False,
                    "stage": "input",
                    "error": "JSON body must contain dealstr.",
                }
            ), 400

        validate_full_deal(dealstr)

        deal = Deal(dealstr)
        table = calc_dd_table(deal)
        rows = direct_dd_table(table)

        return jsonify(
            {
                "ok": True,
                "dealstr": dealstr,
                "validation": {
                    "full_deal": "PASS",
                    "cards": 52,
                    "duplicates": 0,
                },
                "solver": {
                    "engine": "Bo Haglund DDS",
                    "interface": "endplay.calc_dd_table",
                    "source_type": "direct_dd_table",
                },
                "direct_dd_table": {
                    "headers": ["Declarer", "Denomination", "Result"],
                    "rows": rows,
                    "row_count": len(rows),
                },
                "dd_qa": {
                    "status": "OPEN / NOT VALIDATED",
                    "authoritative_field_required": "OptimumResultTable",
                    "authoritative_field_present": False,
                    "final_dd_claim_allowed": False,
                    "note": (
                        "Results come directly from DDS CalcDDtable via endplay. "
                        "They are computational evidence and are NOT the PBN "
                        "OptimumResultTable field. Final DD tricks/results require "
                        "verification of the exact declarer + denomination against "
                        "trusted OptimumResultTable evidence."
                    ),
                },
            }
        )

    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "stage": "validation_or_solver",
                "error": str(exc),
            }
        ), 400
