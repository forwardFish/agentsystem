from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["up", "down", "left", "right"]
GameStatus = Literal["running", "game_over"]

DEFAULT_GRID_WIDTH = 16
DEFAULT_GRID_HEIGHT = 16
DEFAULT_SEED = 1

_DIRECTION_VECTORS: dict[Direction, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
_OPPOSITE_DIRECTIONS: dict[Direction, Direction] = {
    "up": "down",
    "down": "up",
    "left": "right",
    "right": "left",
}


class SnakeCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)


class SnakeGameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=6, le=32)
    height: int = Field(ge=6, le=32)
    snake: list[SnakeCell] = Field(min_length=1)
    direction: Direction
    food: SnakeCell | None = None
    score: int = Field(default=0, ge=0)
    status: GameStatus = "running"
    seed: int = Field(default=DEFAULT_SEED, ge=0)
    message: str | None = None


class SnakeNewGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(default=DEFAULT_GRID_WIDTH, ge=6, le=32)
    height: int = Field(default=DEFAULT_GRID_HEIGHT, ge=6, le=32)
    seed: int = Field(default=DEFAULT_SEED, ge=0)


class SnakeAdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: SnakeGameState
    requested_direction: Direction | None = None


def create_new_game(
    width: int = DEFAULT_GRID_WIDTH,
    height: int = DEFAULT_GRID_HEIGHT,
    seed: int = DEFAULT_SEED,
) -> SnakeGameState:
    center_x = width // 2
    center_y = height // 2
    snake = [
        SnakeCell(x=center_x, y=center_y),
        SnakeCell(x=center_x - 1, y=center_y),
        SnakeCell(x=center_x - 2, y=center_y),
    ]
    food, next_seed = spawn_food(width=width, height=height, occupied=snake, seed=seed)
    return SnakeGameState(
        width=width,
        height=height,
        snake=snake,
        direction="right",
        food=food,
        score=0,
        status="running",
        seed=next_seed,
        message=None,
    )


def advance_game(state: SnakeGameState, requested_direction: Direction | None = None) -> SnakeGameState:
    if state.status != "running":
        return state

    direction = _resolve_direction(state.direction, requested_direction)
    dx, dy = _DIRECTION_VECTORS[direction]
    head = state.snake[0]
    next_x = head.x + dx
    next_y = head.y + dy

    if not _is_inside_board(next_x, next_y, state.width, state.height):
        return state.model_copy(update={"direction": direction, "status": "game_over", "message": "Hit the wall."})

    next_head = SnakeCell(x=next_x, y=next_y)

    will_eat = state.food is not None and _same_cell(next_head, state.food)
    blocking_cells = state.snake if will_eat else state.snake[:-1]
    if any(_same_cell(next_head, cell) for cell in blocking_cells):
        return state.model_copy(update={"direction": direction, "status": "game_over", "message": "Ran into yourself."})

    next_snake = [next_head, *state.snake] if will_eat else [next_head, *state.snake[:-1]]
    if not will_eat:
        return state.model_copy(update={"snake": next_snake, "direction": direction, "message": None})

    next_food, next_seed = spawn_food(width=state.width, height=state.height, occupied=next_snake, seed=state.seed)
    if next_food is None:
        return state.model_copy(
            update={
                "snake": next_snake,
                "direction": direction,
                "food": None,
                "score": state.score + 1,
                "seed": next_seed,
                "status": "game_over",
                "message": "Board cleared.",
            }
        )

    return state.model_copy(
        update={
            "snake": next_snake,
            "direction": direction,
            "food": next_food,
            "score": state.score + 1,
            "seed": next_seed,
            "message": None,
        }
    )


def spawn_food(width: int, height: int, occupied: list[SnakeCell], seed: int) -> tuple[SnakeCell | None, int]:
    cell_count = width * height
    occupied_positions = {(cell.x, cell.y) for cell in occupied}
    if len(occupied_positions) >= cell_count:
        return None, seed

    next_seed = seed
    for _ in range(cell_count):
        next_seed = _next_seed(next_seed)
        candidate = _cell_from_index(width, next_seed % cell_count)
        if (candidate.x, candidate.y) not in occupied_positions:
            return candidate, next_seed

    start_index = next_seed % cell_count
    for offset in range(cell_count):
        candidate = _cell_from_index(width, (start_index + offset) % cell_count)
        if (candidate.x, candidate.y) not in occupied_positions:
            return candidate, next_seed

    return None, next_seed


def _resolve_direction(current: Direction, requested: Direction | None) -> Direction:
    if requested is None or requested == current:
        return current
    if _OPPOSITE_DIRECTIONS[current] == requested:
        return current
    return requested


def _is_inside_board(x: int, y: int, width: int, height: int) -> bool:
    return 0 <= x < width and 0 <= y < height


def _same_cell(left: SnakeCell, right: SnakeCell) -> bool:
    return left.x == right.x and left.y == right.y


def _cell_from_index(width: int, index: int) -> SnakeCell:
    return SnakeCell(x=index % width, y=index // width)


def _next_seed(seed: int) -> int:
    return (seed * 1_664_525 + 1_013_904_223) % (2**32)
