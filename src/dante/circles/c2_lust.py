"""II · Lust — the same customer, five times over.

Four sources, no shared key. Every sales rep kept their own list, so one
company arrives as "Vanacker BVBA", "Vanacker b.v.b.a." and "VANACKER", each
with its own credit limit. Matching is the easy part. Deciding which record
survives is a business decision disguised as a technical one, which is why the
grey band goes to sales instead of to a threshold.

The engine blocks on postcode plus the first letters of the normalised name,
then scores inside the block. Deterministic and explainable on purpose: a
probabilistic matcher scores better on paper and cannot be defended in a room
with the sales manager who lost a credit history.

The scorer is token_sort_ratio, not token_set_ratio, and the difference is the
whole circle. token_set_ratio returns 100 whenever one name's tokens are a
subset of the other's, so "Deveux Bouw" and "Deveux Bouw Zonen" score a perfect
match and get merged automatically. They are a parent and its subsidiary with
separate credit limits. token_sort_ratio scores that pair 79, which lands it in
the grey band where a human belongs.

Two records carrying the same customer number are not a duplicate: they are one
record arriving from two files. Those pairs are skipped, so the findings here
are only about entities the sources failed to agree on.
"""

from __future__ import annotations

from collections import defaultdict

from rapidfuzz import fuzz

from ..normalise import norm_name, vat_status
from ..pipeline import Context

AUTO_MERGE = 92
GREY_BAND = 75
ADDRESS_BOOST = 10
BOOST_FLOOR = 85   # an address never merges two records the names do not support


class Union:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def run(ctx: Context) -> None:
    df = ctx.candidates["customer"]
    df["_match_name"] = df["name"].fillna("").map(norm_name)

    blocks: dict[str, list[int]] = defaultdict(list)
    for idx, row in df.iterrows():
        pc = str(row.get("postcode") or "").strip()
        head = row["_match_name"][:4]
        blocks[f"{pc}|{head}" if pc else f"*|{head}"].append(idx)

    union = Union()
    grey_pairs: list[tuple[int, int, float]] = []
    comparisons = 0

    for members in blocks.values():
        if len(members) < 2:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                na, nb = df.at[a, "_match_name"], df.at[b, "_match_name"]
                if not na or not nb:
                    continue
                ka, kb = _explicit_key(df, a), _explicit_key(df, b)
                if ka and kb and ka == kb:
                    continue  # one record, two files
                comparisons += 1
                score = float(fuzz.token_sort_ratio(na, nb))
                if score >= BOOST_FLOOR and _same_address(df, a, b):
                    score = min(100.0, score + ADDRESS_BOOST)
                if score >= AUTO_MERGE:
                    union.union(a, b)
                    ctx.finding(
                        "R-II-01", "customer", _key(df, a), "name", df.at[b, "_source"],
                        raw=df.at[b, "name"], repaired=df.at[a, "name"],
                        message=f"merged at score {score:.0f}",
                        score=float(score), other_row=int(df.at[b, "_row"]),
                    )
                elif score >= GREY_BAND:
                    grey_pairs.append((a, b, float(score)))

    # clusters, so survivorship can be judged per group rather than per pair
    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in df.index:
        clusters[union.find(idx)].append(idx)
    ctx.stats["customer_clusters"] = sum(1 for v in clusters.values() if len(v) > 1)
    ctx.stats["customer_comparisons"] = comparisons
    df["_cluster"] = [union.find(i) for i in df.index]

    # R-II-02 · the grey band. A parent and its subsidiary score here, and so do
    # two spellings of one company. Nothing in the data separates them.
    for a, b, score in grey_pairs:
        if union.find(a) == union.find(b):
            continue
        ctx.finding("R-II-02", "customer", _key(df, b), "name", df.at[b, "_source"],
                    raw=df.at[b, "name"], repaired=None,
                    message=f"score {score:.0f} sits between {GREY_BAND} and {AUTO_MERGE}",
                    score=score, candidate=str(df.at[a, "name"]),
                    candidate_row=int(df.at[a, "_row"]))

    # R-II-03 · survivorship. Completeness cannot pick a winner when the records
    # disagree on what the customer is allowed to owe us.
    for members in clusters.values():
        if len(members) < 2:
            continue
        for fieldname in ("payment_terms", "credit_limit"):
            values = {str(df.at[i, fieldname]).strip() for i in members
                      if str(df.at[i, fieldname] or "").strip() not in ("", "None", "nan")}
            if len(values) > 1:
                ctx.finding("R-II-03", "customer", _key(df, members[0]), fieldname,
                            "+".join(sorted({str(df.at[i, "_feed"]) for i in members})),
                            raw=" vs ".join(sorted(values)), repaired=None,
                            message=f"{len(values)} values for {fieldname} in one cluster",
                            values=sorted(values))

    # R-II-04 · one VAT number, two names. Strong evidence of one entity, and
    # also how a trading name appears next to its legal entity.
    by_vat: dict[str, set[str]] = defaultdict(set)
    rows_by_vat: dict[str, list[int]] = defaultdict(list)
    for idx, row in df.iterrows():
        v, status = vat_status(row["vat"])
        if status == "ok" and v:
            by_vat[v].add(row["_match_name"])
            rows_by_vat[v].append(idx)
    for vat, names in by_vat.items():
        if len(names) > 1:
            idx = rows_by_vat[vat][0]
            ctx.finding("R-II-04", "customer", _key(df, idx), "vat", df.at[idx, "_source"],
                        raw=vat, repaired=None,
                        message=f"{len(names)} different names on one VAT number",
                        names=sorted(names))

    ctx.candidates["customer"] = df


def _explicit_key(df, idx: int) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    return "" if k in ("", "None", "nan") else k


def _same_address(df, a: int, b: int) -> bool:
    """Only ever confirms a name match. It never creates one."""
    def addr(i: int) -> tuple[str, str]:
        return (str(df.at[i, "street"] or "").strip().lower(),
                str(df.at[i, "house_no"] or "").strip().lower())
    aa, ab = addr(a), addr(b)
    return all(aa) and aa == ab


def _key(df, idx: int) -> str:
    k = str(df.at[idx, "key"] or "").strip()
    return k if k and k != "None" else f"{df.at[idx, '_feed']}#{df.at[idx, '_row']}"
