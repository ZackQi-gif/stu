"""A simple Snake game implemented with tkinter.

Run:
    python src/snake.py
"""

from __future__ import annotations

import random
import tkinter as tk
from dataclasses import dataclass


GRID_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 20
UPDATE_DELAY_MS = 120


@dataclass(frozen=True)
class Point:
    x: int
    y: int


class SnakeGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("贪吃蛇 Snake")

        self.canvas = tk.Canvas(
            root,
            width=GRID_WIDTH * GRID_SIZE,
            height=GRID_HEIGHT * GRID_SIZE,
            bg="#111111",
            highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=10)

        self.score_label = tk.Label(root, text="得分: 0", font=("Arial", 13))
        self.score_label.pack(pady=(0, 8))

        self.root.bind("<KeyPress>", self.on_key_press)

        self.restart()

    def restart(self) -> None:
        center = Point(GRID_WIDTH // 2, GRID_HEIGHT // 2)
        self.snake: list[Point] = [
            center,
            Point(center.x - 1, center.y),
            Point(center.x - 2, center.y),
        ]
        self.direction = Point(1, 0)
        self.next_direction = self.direction
        self.game_over = False
        self.score = 0
        self.food = self._spawn_food()
        self.score_label.config(text="得分: 0")
        self._draw()
        self._tick()

    def _spawn_food(self) -> Point:
        occupied = set(self.snake)
        choices = [
            Point(x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if Point(x, y) not in occupied
        ]
        return random.choice(choices)

    def on_key_press(self, event: tk.Event) -> None:
        if self.game_over and event.keysym.lower() in {"r", "space"}:
            self.restart()
            return

        mapping = {
            "Up": Point(0, -1),
            "Down": Point(0, 1),
            "Left": Point(-1, 0),
            "Right": Point(1, 0),
            "w": Point(0, -1),
            "s": Point(0, 1),
            "a": Point(-1, 0),
            "d": Point(1, 0),
        }

        if event.keysym not in mapping:
            return

        candidate = mapping[event.keysym]
        if candidate.x == -self.direction.x and candidate.y == -self.direction.y:
            return
        self.next_direction = candidate

    def _tick(self) -> None:
        if self.game_over:
            return

        self.direction = self.next_direction
        new_head = Point(
            self.snake[0].x + self.direction.x,
            self.snake[0].y + self.direction.y,
        )

        hit_wall = (
            new_head.x < 0
            or new_head.x >= GRID_WIDTH
            or new_head.y < 0
            or new_head.y >= GRID_HEIGHT
        )
        hit_self = new_head in self.snake[:-1]

        if hit_wall or hit_self:
            self.game_over = True
            self._draw()
            return

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self.score_label.config(text=f"得分: {self.score}")
            self.food = self._spawn_food()
        else:
            self.snake.pop()

        self._draw()
        self.root.after(UPDATE_DELAY_MS, self._tick)

    def _draw_cell(self, point: Point, color: str) -> None:
        x1 = point.x * GRID_SIZE
        y1 = point.y * GRID_SIZE
        x2 = x1 + GRID_SIZE
        y2 = y1 + GRID_SIZE
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#222222")

    def _draw(self) -> None:
        self.canvas.delete("all")

        self._draw_cell(self.food, "#ff5c5c")

        for idx, segment in enumerate(self.snake):
            color = "#29c26a" if idx else "#5ce1a1"
            self._draw_cell(segment, color)

        if self.game_over:
            self.canvas.create_text(
                GRID_WIDTH * GRID_SIZE // 2,
                GRID_HEIGHT * GRID_SIZE // 2,
                text="游戏结束\n按 R 或 Space 重新开始",
                fill="white",
                font=("Arial", 20, "bold"),
                justify="center",
            )


def main() -> None:
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
