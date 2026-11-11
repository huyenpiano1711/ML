"""
history_dao.py - Analyses a user ran (history) and cars a user saved (favorites), plus the statistics
read by the admin dashboard.
"""
import json
from dataclasses import asdict, is_dataclass

import pandas as pd

from desktop_app.dal.user_dao import UserDao


def toJson(value):
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, default=str)


class SearchDao:
    @staticmethod
    def save(user_id, vehicle, result):
        """Store one analysis. vehicle: VehicleInput, result: AnalysisResult. Returns the new id."""
        price = result.price
        payload = {"vehicle_title": result.vehicle_title,
                   "price": asdict(price) if price is not None else None,
                   "top_matches": [asdict(c) for c in result.top_matches],
                   "similar_price": [asdict(c) for c in result.similar_price],
                   "errors": list(result.errors), "warnings": list(result.warnings)}
        sql = """insert into searches(user_id, manufacturer, model_base, year, odometer, budget_max_usd,
                     predicted_price, price_low, price_high, n_matches, success, elapsed_ms, input_json, result_json)
                 values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        val = (user_id, vehicle.manufacturer, vehicle.model_base, int(vehicle.year), float(vehicle.odometer),
               float(vehicle.budget_max_usd), None if price is None else price.predicted_price,
               None if price is None else price.price_low, None if price is None else price.price_high,
               len(result.top_matches), int(bool(result.success)), result.elapsed_ms,
               toJson(vehicle.to_dict()), toJson(payload))
        return UserDao.execute(sql, val)

    @staticmethod
    def listForUser(user_id, keyword=""):
        sql = """select id, created_at, manufacturer, model_base, year, odometer, budget_max_usd, predicted_price,
                        price_low, price_high, n_matches from searches where user_id=?"""
        val = [user_id]
        if keyword.strip():
            sql += " and (manufacturer like ? or model_base like ?)"
            val += [f"%{keyword.strip()}%"] * 2
        return UserDao.query(sql + " order by id desc", tuple(val))

    @staticmethod
    def get(search_id, user_id=None):
        sql, val = "select * from searches where id=?", [search_id]
        if user_id is not None:                 # a user can only open his own analyses
            sql += " and user_id=?"
            val.append(user_id)
        df = UserDao.query(sql, tuple(val))
        return None if df is None or len(df) == 0 else df.iloc[0].to_dict()

    @staticmethod
    def delete(search_id, user_id):
        return UserDao.execute("delete from searches where id=? and user_id=?", (search_id, user_id))

    @staticmethod
    def clear(user_id):
        return UserDao.execute("delete from searches where user_id=?", (user_id,))


class FavoriteDao:
    @staticmethod
    def add(user_id, card, note=""):
        """Save a car (CarCard). Returns False when it is already saved."""
        if FavoriteDao.isSaved(user_id, card.id):
            return False
        UserDao.execute("insert into favorites(user_id, listing_id, car_json, note) values (?, ?, ?, ?)",
                        (user_id, int(card.id), toJson(card), note))
        return True

    @staticmethod
    def remove(user_id, listing_id):
        return UserDao.execute("delete from favorites where user_id=? and listing_id=?", (user_id, int(listing_id)))

    @staticmethod
    def isSaved(user_id, listing_id):
        df = UserDao.query("select 1 from favorites where user_id=? and listing_id=?", (user_id, int(listing_id)))
        return df is not None and len(df) > 0

    @staticmethod
    def listForUser(user_id):
        """DataFrame with one row per saved car: the card fields + saved_at + note."""
        df = UserDao.query("select listing_id, car_json, note, created_at from favorites where user_id=? order by id desc",
                           (user_id,))
        if df is None or len(df) == 0:
            return pd.DataFrame()
        rows = []
        for r in df.itertuples():
            car = json.loads(r.car_json)
            car.update({"saved_at": r.created_at, "note": r.note or ""})
            rows.append(car)
        return pd.DataFrame(rows)


class StatsDao:
    """Numbers for the admin dashboard (all from the app database)."""

    @staticmethod
    def kpis():
        q = UserDao.query("""select
            (select count(*) from users) as users,
            (select count(*) from users where role='admin') as admins,
            (select count(*) from users where is_banned=1) as banned,
            (select count(*) from users where date(created_at) >= date('now','localtime','-6 day')) as new_users_7d,
            (select count(*) from searches) as searches,
            (select count(*) from searches where date(created_at) >= date('now','localtime','-6 day')) as searches_7d,
            (select count(distinct user_id) from searches where date(created_at) >= date('now','localtime','-6 day')) as active_users_7d,
            (select count(*) from login_history where success=0 and date(created_at) >= date('now','localtime','-6 day')) as failed_logins_7d,
            (select count(*) from favorites) as favorites,
            (select avg(elapsed_ms) from searches where elapsed_ms is not null) as avg_ms""")
        return {} if q is None or len(q) == 0 else {k: (None if pd.isna(v) else v) for k, v in q.iloc[0].items()}

    @staticmethod
    def searchesPerDay(days=14):
        return UserDao.query("""select date(created_at) as day, count(*) as n from searches
                                where date(created_at) >= date('now','localtime', ?) group by day order by day""",
                             (f"-{days - 1} day",))

    @staticmethod
    def topMakes(limit=10):
        return UserDao.query("""select manufacturer, count(*) as n, avg(predicted_price) as avg_pred, avg(budget_max_usd) as avg_budget
                                from searches group by manufacturer order by n desc limit ?""", (limit,))

    @staticmethod
    def overBudgetShare():
        df = UserDao.query("""select sum(case when predicted_price > budget_max_usd then 1 else 0 end) as over_n,
                                     count(*) as n from searches where predicted_price is not null""")
        if df is None or len(df) == 0 or not df.iloc[0]["n"]:
            return None
        return float(df.iloc[0]["over_n"]) / float(df.iloc[0]["n"])

    @staticmethod
    def loginsPerDay(days=14):
        return UserDao.query("""select date(created_at) as day, sum(success) as ok, sum(1 - success) as failed
                                from login_history where date(created_at) >= date('now','localtime', ?)
                                group by day order by day""", (f"-{days - 1} day",))

    @staticmethod
    def searchesOfUser(user_id):
        return SearchDao.listForUser(user_id)
