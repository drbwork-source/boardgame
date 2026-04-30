import unittest

from board_core import BoardOptions, check_pathability, generate_board, validate_progression_path


class ProgressionFeaturesTest(unittest.TestCase):
    def test_pathboard_places_goal_and_starts_and_is_reachable(self) -> None:
        board = generate_board(
            BoardOptions(width=20, height=14, seed=7, generation_mode="pathboard", num_starts=2)
        )
        ok, _ = check_pathability(board)
        self.assertTrue(ok)

    def test_pathboard_with_checkpoints_reachable(self) -> None:
        board = generate_board(
            BoardOptions(
                width=22,
                height=16,
                seed=11,
                generation_mode="pathboard",
                num_starts=2,
                num_checkpoints=2,
            )
        )
        ok, unreachable = check_pathability(board)
        self.assertTrue(ok)
        self.assertEqual(unreachable, [])

    def test_validate_progression_path_accepts_simple_route(self) -> None:
        board = [
            [".", ".", "."],
            [".", ".", "."],
            ["S", ".", "E"],
        ]
        valid, msg = validate_progression_path(board)
        self.assertTrue(valid, msg)

    def test_validate_progression_path_rejects_blocked_route(self) -> None:
        board = [
            ["S", "W", "E"],
        ]
        valid, _ = validate_progression_path(board)
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
