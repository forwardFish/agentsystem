from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from agentsystem.dashboard import main as dashboard_main
from agentsystem.dashboard.snake import SnakeCell, SnakeGameState, advance_game, create_new_game


class SnakeGameTestCase(unittest.TestCase):
    def test_create_new_game_is_deterministic_for_seed(self) -> None:
        left = create_new_game(width=10, height=10, seed=7)
        right = create_new_game(width=10, height=10, seed=7)

        self.assertEqual(left.model_dump(), right.model_dump())
        self.assertEqual(len(left.snake), 3)
        self.assertNotIn((left.food.x, left.food.y), {(cell.x, cell.y) for cell in left.snake})

    def test_advance_game_moves_forward_and_ignores_reverse_input(self) -> None:
        state = create_new_game(width=10, height=10, seed=3)

        next_state = advance_game(state, requested_direction="left")

        self.assertEqual(next_state.direction, "right")
        self.assertEqual((next_state.snake[0].x, next_state.snake[0].y), (state.snake[0].x + 1, state.snake[0].y))
        self.assertEqual(len(next_state.snake), len(state.snake))

    def test_eating_food_increases_score_and_length(self) -> None:
        state = SnakeGameState(
            width=6,
            height=6,
            snake=[SnakeCell(x=2, y=2), SnakeCell(x=1, y=2), SnakeCell(x=0, y=2)],
            direction="right",
            food=SnakeCell(x=3, y=2),
            score=0,
            status="running",
            seed=9,
        )

        next_state = advance_game(state)

        self.assertEqual(next_state.score, 1)
        self.assertEqual(len(next_state.snake), 4)
        self.assertEqual((next_state.snake[0].x, next_state.snake[0].y), (3, 2))
        self.assertNotIn((next_state.food.x, next_state.food.y), {(cell.x, cell.y) for cell in next_state.snake})

    def test_wall_collision_ends_the_game(self) -> None:
        state = SnakeGameState(
            width=6,
            height=6,
            snake=[SnakeCell(x=0, y=2), SnakeCell(x=1, y=2), SnakeCell(x=2, y=2)],
            direction="left",
            food=SnakeCell(x=5, y=5),
            score=4,
            status="running",
            seed=11,
        )

        next_state = advance_game(state)

        self.assertEqual(next_state.status, "game_over")
        self.assertEqual(next_state.message, "Hit the wall.")

    def test_self_collision_ends_the_game(self) -> None:
        state = SnakeGameState(
            width=6,
            height=6,
            snake=[
                SnakeCell(x=2, y=2),
                SnakeCell(x=2, y=3),
                SnakeCell(x=1, y=3),
                SnakeCell(x=1, y=2),
            ],
            direction="down",
            food=SnakeCell(x=5, y=5),
            score=2,
            status="running",
            seed=13,
        )

        next_state = advance_game(state)

        self.assertEqual(next_state.status, "game_over")
        self.assertEqual(next_state.message, "Ran into yourself.")

    def test_snake_routes_return_html_and_json(self) -> None:
        client = TestClient(dashboard_main.app)

        page_response = client.get("/snake")
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("Snake", page_response.text)

        new_response = client.post("/api/snake/new", json={"width": 8, "height": 8, "seed": 21})
        self.assertEqual(new_response.status_code, 200)
        payload = new_response.json()
        self.assertEqual(payload["status"], "running")
        self.assertEqual(len(payload["snake"]), 3)

        tick_response = client.post("/api/snake/tick", json={"state": payload, "requested_direction": "down"})
        self.assertEqual(tick_response.status_code, 200)
        tick_payload = tick_response.json()
        self.assertEqual(tick_payload["direction"], "down")
        self.assertEqual(tick_payload["status"], "running")


if __name__ == "__main__":
    unittest.main()
