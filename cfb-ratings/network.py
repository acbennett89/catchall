"""+2 head-to-head network: primary / secondary / tertiary win values.

When team A beats team B, the win is valued by B's network strength:

    P = B's record                                   (games vs A removed)
    S = mean record of B's FBS opponents C           (games vs A and B removed)
    T = mean over C of mean record of C's opponents D (games vs A, B and C
        removed; D is never A or B)  -- the "path" exclusion rule
    NS = wP*P + wS*S + wT*T
    WinValue  = NS / NS_win      NS_win  = mean NS of every beaten FBS opponent
    LossCost  = (1 - NS) / (1 - NS_loss)   NS_loss = mean NS of every FBS team that won

So the average FBS win is worth exactly 1.00 and the average FBS loss costs
exactly 1.00. Schedule strength is the mean opponent NS (FCS opponents = 0)
divided by NS_all, the mean over every FBS game side.

Records are FBS-only: FBS wins over FCS teams are ignored entirely, losses to
FCS teams count as losses (config: fcs_losses_count). FCS teams are never
nodes, so their branches are never traversed. Every number is returned with
the tree that produced it.
"""
from collections import defaultdict


class Network:
    def __init__(self, games, teams, cfg):
        self.fbs = {t for t, v in teams.items() if v["division"] == "FBS"}
        self.names = {t: v.get("name", t) for t, v in teams.items()}
        w = cfg["net_weights"]
        self.wP, self.wS, self.wT = w["primary"], w["secondary"], w["tertiary"]
        self.prior_w = cfg["record_prior"]["wins"]
        self.prior_l = cfg["record_prior"]["losses"]
        self.fcs_losses_count = cfg["fcs_losses_count"]
        # Variants exist so the backtest can test the alternatives against the default:
        #   layer_mode "rate":  layers are mean win rates (default)
        #   layer_mode "count": layers are summed raw win counts (literal reading)
        #   exclusion "path":   a node's record drops games vs every ancestor on its
        #                       path (A, B, C), so B's own results never leak into
        #                       B's secondary or tertiary layers (default)
        #   exclusion "parent": drop games vs the parent only (RPI convention)
        #   exclusion "none":   only "A removed"; B can reappear as its own tertiary
        self.mode = cfg.get("layer_mode", "rate")
        self.exclusion = cfg.get("exclusion", "path")
        # FBS team -> list of (opponent, won, game_id) against FBS opponents
        self.fbs_games = defaultdict(list)
        # FBS team -> list of (opponent, won, game_id) against non-FBS opponents
        self.other_games = defaultdict(list)
        for g in games:
            if g["home_pts"] == g["away_pts"]:
                continue  # ties can't happen in modern CFB; ratings.py skips them too
            for me, opp, won in ((g["home"], g["away"], g["home_pts"] > g["away_pts"]),
                                 (g["away"], g["home"], g["away_pts"] > g["home_pts"])):
                if me not in self.fbs:
                    continue
                bucket = self.fbs_games if opp in self.fbs else self.other_games
                bucket[me].append((opp, won, g["id"]))
        self._rec = {}
        self._ns = {}
        self._refs = None

    # ---- records -------------------------------------------------------
    def record(self, x, excl=frozenset()):
        """FBS record of x ignoring games against teams in excl. Returns (W, L, wp)."""
        key = (x, excl)
        if key not in self._rec:
            w = sum(1 for o, won, _ in self.fbs_games[x] if won and o not in excl)
            l = sum(1 for o, won, _ in self.fbs_games[x] if not won and o not in excl)
            if self.fcs_losses_count:
                l += sum(1 for o, won, _ in self.other_games[x] if not won)
            if self.mode == "count":
                wp = float(w)
            else:
                den = w + l + self.prior_w + self.prior_l
                wp = (w + self.prior_w) / den if den else 0.5
            self._rec[key] = (w, l, wp)
        return self._rec[key]

    def opponents(self, x):
        return [o for o, _, _ in self.fbs_games[x]]

    # ---- network strength ---------------------------------------------
    def strength(self, b, a=None, tree=False):
        """NS of team b as an opponent of team a (a=None: no team removed)."""
        key = (b, a)
        if key in self._ns and not tree:
            return self._ns[key]
        ex_a = frozenset([a]) if a else frozenset()
        mode = self.exclusion
        agg = (lambda v: sum(v)) if self.mode == "count" else (lambda v: sum(v) / len(v))
        w, l, p = self.record(b, ex_a)
        sec, s_vals, t_vals = [], [], []
        for c in self.opponents(b):
            if c == a:
                continue
            cw, cl, cwp = self.record(c, ex_a | {b} if mode != "none" else ex_a)
            ter = []
            for d in self.opponents(c):
                if d == a or (mode != "none" and d == b):
                    continue
                d_ex = {"path": ex_a | {b, c}, "parent": ex_a | {c}, "none": ex_a}[mode]
                dw, dl, dwp = self.record(d, d_ex)
                ter.append({"team": d, "W": dw, "L": dl, "wp": dwp})
            t_c = agg([x["wp"] for x in ter]) if ter else None
            s_vals.append(cwp)
            if t_c is not None:
                t_vals.append(t_c)
            sec.append({"team": c, "W": cw, "L": cl, "wp": cwp,
                        "tertiary_mean": t_c, "tertiary": ter})
        # A layer with no teams (very early season) falls back to .500 and says so.
        empty = 0.0 if self.mode == "count" else 0.5
        s = agg(s_vals) if s_vals else empty
        t = agg(t_vals) if t_vals else empty
        ns = self.wP * p + self.wS * s + self.wT * t
        out = {"ns": ns, "P": p, "S": s, "T": t}
        self._ns[key] = out
        if not tree:
            return out
        return {**out, "opponent": b, "removed": a,
                "primary": {"team": b, "W": w, "L": l, "wp": p,
                            "games": self.record_games(b, ex_a)},
                "secondary": sec,
                "fallbacks": [n for n, v in (("S", s_vals), ("T", t_vals)) if not v],
                "weights": {"P": self.wP, "S": self.wS, "T": self.wT}}

    def record_games(self, x, excl):
        rows = [{"opp": o, "won": won, "game": gid, "counted": o not in excl}
                for o, won, gid in self.fbs_games[x]]
        rows += [{"opp": o, "won": won, "game": gid,
                  "counted": (not won) and self.fcs_losses_count,
                  "note": "FCS loss counts as a loss" if not won else "FCS win ignored"}
                 for o, won, gid in self.other_games[x]]
        return rows

    def references(self):
        """The three anchors, each a plain mean over FBS-vs-FBS game sides.

        win:  NS of the beaten team, over every FBS win   -> average win = 1.00
        loss: NS of the winning team, over every FBS loss -> average loss = 1.00
        all:  NS of the opponent, over every game side     -> average schedule = 1.00
        """
        if self._refs is None:
            won, lost = [], []
            for a in self.fbs:
                for b, w, _ in self.fbs_games[a]:
                    (won if w else lost).append(self.strength(b, a)["ns"])
            mean = lambda v: sum(v) / len(v) if v else 0.5
            self._refs = {"win": mean(won), "loss": mean(lost), "all": mean(won + lost),
                          "n_wins": len(won), "n_losses": len(lost)}
        return self._refs

    def reference(self):
        return self.references()["all"]

    # ---- per-team resume ------------------------------------------------
    def resume(self, a, with_trees=True):
        refs = self.references()
        wins, losses, sched = [], [], []
        for b, won, gid in self.fbs_games[a]:
            st = self.strength(b, a, tree=with_trees)
            ns = st["ns"]
            sched.append(ns)
            row = {"game": gid, "opp": b, "ns": ns, "P": st["P"], "S": st["S"], "T": st["T"]}
            if with_trees:
                row["tree"] = st
            if won:
                row["value"] = ns / refs["win"]
                wins.append(row)
            else:
                row["cost"] = (1 - ns) / (1 - refs["loss"])
                losses.append(row)
        for b, won, gid in self.other_games[a]:
            row = {"game": gid, "opp": b, "ns": 0.0, "fcs": True}
            sched.append(0.0)
            if won:
                row["value"] = 0.0
                row["note"] = "win over FCS: worth 0, branches not traversed"
                wins.append(row)
            else:
                row["cost"] = 1 / (1 - refs["loss"])
                row["note"] = "loss to FCS: opponent strength treated as 0 (maximum cost)"
                losses.append(row)
        wvt = sum(r["value"] for r in wins)
        lct = sum(r["cost"] for r in losses)
        fbs_wins = [r for r in wins if not r.get("fcs")]
        return {
            "wins": wins, "losses": losses,
            "win_value_total": wvt,
            "avg_win_value": wvt / len(fbs_wins) if fbs_wins else None,
            "loss_cost_total": lct,
            "net_resume": wvt - lct,
            "schedule_ns": sum(sched) / len(sched) if sched else None,
            "schedule_ratio": (sum(sched) / len(sched)) / refs["all"] if sched else None,
            "best_win": max(fbs_wins, key=lambda r: r["value"], default=None),
            "worst_loss": max(losses, key=lambda r: r["cost"], default=None),
            "refs": refs,
        }
