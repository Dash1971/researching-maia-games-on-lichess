#!/usr/bin/env python3
"""Independently replay the custom-position games (requires chess==1.11.2)."""

import gzip
import json
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "account-cases" / "top1mostplayedgames.ndjson.gz"


def main():
    games = mates = one_ply = 0
    with gzip.open(SOURCE, "rt", encoding="utf-8") as source:
        for line in source:
            game = json.loads(line)
            assert game["variant"] == "fromPosition"
            board = chess.Board(game["initialFen"])
            moves = game["moves"].split()
            for san in moves:
                board.push_san(san)
            is_mate = board.is_checkmate()
            assert is_mate == (game["status"] == "mate"), game["id"]
            games += 1
            mates += is_mate
            one_ply += len(moves) == 1
    assert (games, mates, one_ply) == (27506, 27505, 27504)
    print(json.dumps({"games_replayed": games, "legal_mates": mates, "one_ply": one_ply}))


if __name__ == "__main__":
    main()
