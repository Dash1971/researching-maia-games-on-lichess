#!/usr/bin/env python3
"""Replay supplied custom boards, flagging basic invalidity (chess==1.11.2).

SAN replay and checkmate detection on a custom board do not establish that
the initial position is valid or historically reachable in orthodox chess.
"""

import gzip
import json
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "account-cases" / "top1mostplayedgames.ndjson.gz"


def main(verbose=True):
    games = mates = one_ply = invalid_initial_boards = 0
    invalid_fens = {}
    with gzip.open(SOURCE, "rt", encoding="utf-8") as source:
        for line in source:
            game = json.loads(line)
            assert game["variant"] == "fromPosition"
            board = chess.Board(game["initialFen"])
            if not board.is_valid():
                invalid_initial_boards += 1
                entry = invalid_fens.setdefault(game["initialFen"], {"games": 0, "status": int(board.status()),
                                                                     "reason": "too many white pieces"})
                entry["games"] += 1
            moves = game["moves"].split()
            for san in moves:
                board.push_san(san)
            is_mate = board.is_checkmate()
            assert is_mate == (game["status"] == "mate"), game["id"]
            games += 1
            mates += is_mate
            one_ply += len(moves) == 1
    assert (games, mates, one_ply) == (27506, 27505, 27504)
    assert invalid_initial_boards == 10052
    assert len(invalid_fens) == 1
    assert {entry["status"] for entry in invalid_fens.values()} == {int(chess.STATUS_TOO_MANY_WHITE_PIECES)}
    result = {"chess_version": chess.__version__,
                      "games_replayed": games, "checkmates_on_supplied_boards": mates,
                      "one_ply": one_ply, "invalid_initial_boards": invalid_initial_boards,
                      "invalid_initial_fens_status": invalid_fens,
                      "validity_limit": "Basic validity checks do not prove historical reachability."}
    (SOURCE.parent / "replay_verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if verbose:
        print(json.dumps(result))
    return result


if __name__ == "__main__":
    main()
