#!/usr/bin/env python3
"""Tests for the opt-out block. Run: python -m unittest scripts/test_opt_outs.py"""
import copy, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opt_outs

ENTRY = {"name": "Acme Farm", "aliases": ["Acme Stand"], "ids": ["co-p-9"], "slugs": ["acme-farm"],
         "urls": ["acmefarm.com", "facebook.com/acmefarm"], "emails": ["hi@acmefarm.com"],
         "recorded_on": "2026-11-03", "recorded_by": "test", "note": "test"}


def rec(**kw):
    base = {"id": "x-1", "slug": "other", "name": "Other Farm", "website": None, "facebook": None, "instagram": None,
            "email": None}
    base.update(kw)
    return base


def export():
    loc = {"pin": True}
    return {"export": {"counts": {"pins": 0}},
            "producers": [rec(id="co-p-9", slug="acme-farm", name="Acme Farm", locations=[dict(loc)], offerings=[]),
                          rec(id="co-p-1", locations=[dict(loc)], offerings=[{"market": {"id": "co-m-1"}}])],
            "markets": [{"id": "co-m-1", "slug": "m", "name": "Market", "vendors": ["co-p-9", "co-p-1"],
                         "location": dict(loc)}],
            "access_points": [], "outlets": [rec(id="co-o-3", slug="acme-farm-store-outlet", name="Acme Farm Store",
                                                 location=dict(loc))]}


class Matching(unittest.TestCase):
    def test_each_kind_of_match(self):
        for r in (rec(id="co-p-9"), rec(slug="acme-farm"), rec(slug="acme-farm-outlet"), rec(name="Acme Stand"),
                  rec(name="The Acme Farm"), rec(name="Market (Acme Farm LLC)"), rec(website="https://www.acmefarm.com/"),
                  rec(website="http://shop.acmefarm.com"), rec(facebook="https://facebook.com/acmefarm/"),
                  rec(email="HI@acmefarm.com")):
            self.assertTrue(opt_outs.matches(ENTRY, r), r)

    def test_unrelated_records_are_kept(self):
        for r in (rec(), rec(name="Acme Farmstead"), rec(website="https://notacmefarm.org"),
                  rec(facebook="https://facebook.com/acmefarmers")):
            self.assertFalse(opt_outs.matches(ENTRY, r), r)


class Scrub(unittest.TestCase):
    def test_removes_business_shop_and_vendor_links(self):
        d = export()
        removed = opt_outs.scrub(d, [ENTRY])
        self.assertEqual({(k, n) for k, n, _ in removed}, {("producers", "Acme Farm"), ("outlets", "Acme Farm Store")})
        self.assertEqual([p["id"] for p in d["producers"]], ["co-p-1"])
        self.assertEqual(d["markets"][0]["vendors"], ["co-p-1"])
        self.assertEqual(d["outlets"], [])
        self.assertEqual(d["export"]["counts"]["producers"], 1)
        self.assertEqual(d["export"]["counts"]["market_links"], 1)

    def test_nothing_left_after_scrub(self):
        d = export()
        opt_outs.scrub(d, [ENTRY])
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "out.json")
            with open(p, "w") as f:
                json.dump(d, f)
            self.assertEqual(opt_outs.violations([ENTRY], [p]), [])


class Detection(unittest.TestCase):
    def found(self, text):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "f.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            return opt_outs.violations([ENTRY], [p])

    def test_traces_are_found_anywhere(self):
        for text in ("Visit ACME FARM today", "see co-p-9 here", "https://www.acmefarm.com/shop", "mail hi@acmefarm.com",
                     '{"note": "buys from acme  stand"}', "slug acme-farm"):
            self.assertTrue(self.found(text), text)

    def test_clean_text_passes(self):
        self.assertEqual(self.found("Acme Farmstead sells carrots; ids co-p-90"), [])

    def test_empty_file_list_checks_nothing_not_everything(self):
        self.assertEqual(opt_outs.violations([ENTRY], []), [])


class Table(unittest.TestCase):
    def load(self, entries):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "t.json")
            with open(p, "w") as f:
                json.dump({"opted_out": entries}, f)
            return opt_outs.load_table(p)

    def test_valid(self):
        self.assertEqual(len(self.load([ENTRY])), 1)

    def test_malformed_entries_stop_the_build(self):
        for bad in ({**ENTRY, "note": ""}, {**ENTRY, "recorded_on": "Nov 3"}, {**ENTRY, "ids": [], "slugs": [], "urls": [],
                    "emails": []}, {**ENTRY, "ids": "co-p-9"}):
            with self.assertRaises(SystemExit):
                self.load([bad])
        with self.assertRaises(SystemExit):
            self.load([ENTRY, copy.deepcopy(ENTRY)])

    def test_the_real_table_loads_and_blocks_triangle_oasis(self):
        names = {e["name"] for e in opt_outs.load_table()}
        self.assertIn("The Triangle Oasis", names)


class Published(unittest.TestCase):
    def test_site_is_clean_today(self):
        self.assertEqual(opt_outs.violations(), [])
        self.assertEqual(opt_outs.photo_assets(opt_outs.load_table()), [])


if __name__ == "__main__":
    unittest.main()
