import unittest

from board_generator import BoardOptions, generate_board, validate_progression_path


class ProgressionFeaturesTest(unittest.TestCase):
    def test_auto_start_end_places_required_tiles(self) -> None:
        board = generate_board(
            BoardOptions(width=12, height=12, seed=7, auto_place_start_end=True)
        )
        flat = [cell for row in board for cell in row]
        self.assertEqual(flat.count("S"), 1)
        self.assertEqual(flat.count("E"), 1)

    def test_checkpoints_are_placed_when_interval_is_set(self) -> None:
        board = generate_board(
            BoardOptions(
                width=12,
                height=12,
                seed=11,
                auto_place_start_end=True,
                checkpoint_interval=4,
            )
        )
        checkpoint_count = sum(cell == "C" for row in board for cell in row)
        self.assertGreaterEqual(checkpoint_count, 1)

    def test_validate_progression_path_accepts_generated_board(self) -> None:
        board = generate_board(
            BoardOptions(width=12, height=12, seed=13, auto_place_start_end=True)
        )
        valid, _ = validate_progression_path(board)
        self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
