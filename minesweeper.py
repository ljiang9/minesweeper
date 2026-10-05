"""扫雷 (Minesweeper) —— 终端版经典小游戏.

玩法说明:
  python -m minesweeper            # 默认 9x9, 10 颗雷
  python -m minesweeper --size 16 --mines 40
  python -m minesweeper --seed 42  # 可复现的棋盘(用于复盘)

命令:
  r C3   # 翻开 C3
  f C3   # 标记/取消标记 C3
  q      # 退出

规则:
  - 第一次点击永远安全:如果首次翻开的位置恰好是雷,会把那颗雷搬到
    棋盘上的另一处空位,保证新手第一步不会被炸死.
  - 翻开数字 0 的格子会自动"洪水填充",连带翻开相连的空白区域.
  - 翻开全部安全格子即获胜;点到雷即失败.
  - (已知限制)不支持"双击数字展开(chording)"操作.
"""
from __future__ import annotations

import argparse
import random
import secrets
import sys

# 格子状态
HIDDEN = 0
REVEALED = 1
FLAGGED = 2


class Minefield:
    """扫雷棋盘.

    board[r][c]: 该格周围的雷数,-1 表示本身是雷.
    state[r][c]: HIDDEN / REVEALED / FLAGGED.
    """

    def __init__(self, size: int, mines: int, seed: int | None = None,
                 board: list[list[int]] | None = None):
        if size < 2:
            raise ValueError("棋盘太小啦")
        if mines < 1 or mines >= size * size:
            raise ValueError("雷的数量必须在 1 和 size*size-1 之间")
        self.size = size
        self.mines = mines
        self.first_click_done = False
        if board is not None:
            self.board = [row[:] for row in board]
            self._compute_neighbors()  # 由雷位重算邻雷数,手写棋盘也正确
        else:
            rng = random.Random(seed)
            self.board = [[0] * size for _ in range(size)]
            cells = [(r, c) for r in range(size) for c in range(size)]
            rng.shuffle(cells)
            for r, c in cells[:mines]:
                self.board[r][c] = -1
            self._compute_neighbors()
        self.state = [[HIDDEN] * size for _ in range(size)]
        self.revealed_safe = 0

    # ---------- 内部 ----------
    def _compute_neighbors(self) -> None:
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == -1:
                    continue
                self.board[r][c] = sum(
                    1 for nr, nc in self._neighbors(r, c)
                    if self.board[nr][nc] == -1
                )

    def _neighbors(self, r: int, c: int):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size:
                    yield nr, nc

    # ---------- 玩法 ----------
    def reveal(self, r: int, c: int) -> str:
        """翻开一格. 返回 'boom' / 'ok' / 'won' / 'invalid' / 'already'.

        第一次点击安全:如果该格是雷,先把雷搬到别处再翻开.
        """
        if not (0 <= r < self.size and 0 <= c < self.size):
            return "invalid"
        if self.state[r][c] == FLAGGED:
            return "invalid"          # 已标记的格子不能翻
        if self.state[r][c] == REVEALED:
            return "already"
        if not self.first_click_done:
            self._ensure_first_click_safe(r, c)
            self.first_click_done = True
        if self.board[r][c] == -1:
            self.state[r][c] = REVEALED
            return "boom"
        self._flood(r, c)
        if self.revealed_safe == self.size * self.size - self.mines:
            return "won"
        return "ok"

    def _ensure_first_click_safe(self, r: int, c: int) -> None:
        """首次点击落雷时,把这颗雷搬到棋盘上第一块不是雷的格子."""
        if self.board[r][c] != -1:
            return
        self.board[r][c] = 0
        for rr in range(self.size):
            for cc in range(self.size):
                if (rr, cc) != (r, c) and self.board[rr][cc] != -1:
                    self.board[rr][cc] = -1
                    break
            else:
                continue
            break
        self._compute_neighbors()

    def _flood(self, r: int, c: int) -> None:
        """洪水填充:翻开 (r,c) 及与之连通的所有 0 区域."""
        stack = [(r, c)]
        while stack:
            cr, cc = stack.pop()
            if self.state[cr][cc] == REVEALED:
                continue
            if self.state[cr][cc] == FLAGGED:
                continue
            self.state[cr][cc] = REVEALED
            self.revealed_safe += 1
            if self.board[cr][cc] == 0:
                for nr, nc in self._neighbors(cr, cc):
                    if self.state[nr][nc] == HIDDEN:
                        stack.append((nr, nc))

    def toggle_flag(self, r: int, c: int) -> str:
        """标记/取消标记. 返回 'flagged' / 'unflagged' / 'invalid'."""
        if not (0 <= r < self.size and 0 <= c < self.size):
            return "invalid"
        if self.state[r][c] == REVEALED:
            return "invalid"
        self.state[r][c] = (FLAGGED if self.state[r][c] == HIDDEN else HIDDEN)
        return "flagged" if self.state[r][c] == FLAGGED else "unflagged"

    @property
    def flags_used(self) -> int:
        return sum(row.count(FLAGGED) for row in self.state)

    # ---------- 渲染 ----------
    def render(self, reveal_all: bool = False) -> str:
        lines = []
        head = "    " + " ".join(chr(ord("A") + c) for c in range(self.size))
        lines.append(head)
        for r in range(self.size):
            row = [f"{r + 1:>2} "]
            for c in range(self.size):
                st = self.state[r][c]
                if reveal_all and self.board[r][c] == -1:
                    row.append("*" if st != FLAGGED else "⚑")
                elif st == FLAGGED:
                    row.append("⚑")
                elif st == HIDDEN:
                    row.append("·")
                else:
                    v = self.board[r][c]
                    row.append(" " if v == 0 else str(v))
            lines.append(" ".join(row))
        return "\n".join(lines)


def parse_coord(text: str, size: int) -> tuple[int, int] | None:
    """解析 C3 这样的坐标,返回 (row, col),非法返回 None."""
    t = text.strip().upper()
    if len(t) < 2 or not t[0].isalpha():
        return None
    c = ord(t[0]) - ord("A")
    rest = t[1:]
    if not rest.isdigit():
        return None
    r = int(rest) - 1
    if 0 <= r < size and 0 <= c < size:
        return r, c
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="扫雷 (Minesweeper) —— 终端版经典小游戏")
    parser.add_argument("--size", type=int, default=9,
                        help="棋盘边长 (默认 9)")
    parser.add_argument("--mines", type=int, default=10,
                        help="雷的数量 (默认 10)")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子,用于复现棋盘")
    args = parser.parse_args(argv)

    try:
        field = Minefield(args.size, args.mines,
                          args.seed if args.seed is not None
                          else secrets.randbits(63))
    except ValueError as e:
        print(f"参数错误:{e}", file=sys.stderr)
        return 2

    print(f"扫雷 {args.size}x{args.size}, {args.mines} 颗雷")
    print("命令: r C3 翻开 | f C3 标记 | q 退出")
    over = False
    while not over:
        print()
        print(field.render())
        print(f"剩余雷(估计): {field.mines - field.flags_used}")
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            return 0
        if not cmd:
            continue
        parts = cmd.split()
        op = parts[0].lower()
        if op in ("q", "quit", "exit"):
            print("再见!")
            return 0
        if op not in ("r", "f") or len(parts) != 2:
            print("用法: r C3 (翻开) | f C3 (标记) | q (退出)")
            continue
        coord = parse_coord(parts[1], field.size)
        if coord is None:
            print(f"坐标无效.列用 A~{chr(ord('A') + field.size - 1)},"
                  f"行用 1~{field.size}.")
            continue
        r, c = coord
        if op == "f":
            res = field.toggle_flag(r, c)
            if res == "invalid":
                print("这个格子不能标记.")
            continue
        res = field.reveal(r, c)
        if res == "boom":
            print()
            print(field.render(reveal_all=True))
            print("💥 踩雷了!游戏结束.")
            over = True
        elif res == "won":
            print()
            print(field.render(reveal_all=True))
            print("🎉 全部扫清!你赢了!")
            over = True
        elif res == "invalid":
            print("这个格子翻不了(已标记或越界).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
